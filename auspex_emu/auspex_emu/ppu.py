#!/usr/bin/env python3
import os
import sys
import time
import math
import ctypes
import struct
import pygame
import numpy as np
import traceback
import tabulate

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from ament_index_python.packages import get_package_share_directory

from auspex_interfaces.msg import AudioChunk, VideoChunk, InputChunk
from auspex_interfaces.srv import SnesGraphics, SnesEmuState

# joypad: xinput (x360) layout by default.
#             BYet^v<>AXLR
joymap_arg = '0267----1345'


def convert_15bit_to_24bit(color):
    # Extract 5-bit values for R, G, and B
    r = (color >> 10) & 0x1F
    g = (color >> 5) & 0x1F
    b = color & 0x1F

    # Scale 5-bit values to 8-bit values
    r = (r << 3) | (r >> 2)  # Scale from 5 bits to 8 bits
    g = (g << 3) | (g >> 2)  # Scale from 5 bits to 8 bits
    b = (b << 3) | (b >> 2)  # Scale from 5 bits to 8 bits

    return (r, g, b)


def vectorized_char_to_24bit_surface(char_data, palette):
    # Create meshgrid for indices
    char_size = len(char_data) # 16 bit char_data
    bitplane_context = char_size // 2
    i, j = np.meshgrid(np.arange(8), np.arange(8), indexing='ij')

    # Extract relevant bits from char_data using numpy operations
    pidx = (
        (((char_data[2*i] >> j) & 0x1) << 0) |                          # bitplane 1
        (((char_data[2*i + 1] >> j) & 0x1) << 1) |                      # bitplane 2
        (((char_data[bitplane_context + 2*i] >> j) & 0x1) << 2) |       # bitplane 3
        (((char_data[bitplane_context + 2*i + 1] >> j) & 0x1) << 3)     # bitplane 4
    )

    # Map pidx to 15-bit colors using the palette
    color_15bit = palette[pidx]

    # Convert 15-bit colors to 24-bit colors using vectorized operations
    color_24bit = np.array([convert_15bit_to_24bit(color) for color in color_15bit.flat]).reshape(8, 8, 3)

    return color_24bit.tobytes()


def get_color_depth(bg_idx, bg_mode):
    depth = 0
    if bg_mode == 0: # 4 backgrounds
        depth = 2
    elif bg_mode == 1: # 3 backgrounds, 16 colors for bg1&2, 4 colors for bg3. 32 colors total
        if bg_idx in [0, 1]:
            depth = 4
        elif bg_idx == 2:
            depth = 2
    elif bg_mode == 2: # 2 backgrounds, up to 32 colors
        depth = 4
    elif bg_mode == 3: # 2 backgrounds, up to 272 colors
        if bg_idx == 0:
            depth = 8
        elif bg_idx == 1:
            depth = 4
    elif bg_mode == 4: # 2 backgrounds, up to 260 colors
        if bg_idx == 0:
            depth = 8
        elif bg_idx == 1:
            depth = 2
    elif bg_mode == 5: # 2 backgrounds higher 512x480 resolution w/ lower bit depth
        if bg_idx == 0:
            depth = 4
        elif bg_idx == 1:
            depth = 2
    elif bg_mode == 6: # 1 background, like mode5 w/ special effects e.g. flipping
        if bg_idx == 0:
            depth = 4
    elif bg_mode == 7: # 1 background w/ rotate and scale
        if bg_idx == 0:
            depth = 8
    return depth


def get_palette(cgram, palette_idx, bg_idx, bg_mode):
    palette = []
    if bg_mode == 0: # 4 backgrounds
        palette = cgram[0x4*palette_idx:0x4*palette_idx + 0x4]
    elif bg_mode == 1: # 3 backgrounds, 16 colors for bg1&2, 4 colors for bg3. 32 colors total
        if bg_idx in [0, 1]:
            palette = cgram[0x10*palette_idx:0x10*palette_idx + 0x10]
        elif bg_idx == 2:
            palette = cgram[0x4*palette_idx:0x4*palette_idx + 0x4]
    elif bg_mode == 2: # 2 backgrounds, up to 32 colors
        palette = cgram[0x10*palette_idx:0x10*palette_idx + 0x10]
    elif bg_mode == 3: # 2 backgrounds, up to 272 colors
        if bg_idx == 0:
            palette = cgram
        elif bg_idx == 1:
            palette = cgram[0x10*palette_idx:0x10*palette_idx + 0x10]
    elif bg_mode == 4: # 2 backgrounds, up to 260 colors
        if bg_idx == 0:
            palette = cgram
        elif bg_idx == 1:
            palette = cgram[0x4*palette_idx:0x4*palette_idx + 0x4]
    elif bg_mode == 5: # 2 backgrounds higher 512x480 resolution w/ lower bit depth
        if bg_idx == 0:
            palette = cgram[0x10*palette_idx:0x10*palette_idx + 0x10]
        elif bg_idx == 1:
            palette = cgram[0x4*palette_idx:0x4*palette_idx + 0x4]
    elif bg_mode == 6: # 1 background, like mode5 w/ special effects e.g. flipping
        if bg_idx == 0:
            palette = cgram[0x10*palette_idx:0x10*palette_idx + 0x10]
    elif bg_mode == 7: # 1 background w/ rotate and scale
        if bg_idx == 0:
            palette = cgram
    return palette


class SnesRosPPU():
    """
    Wrap the PPU snapshot processing utils.
    """

    def __init__(self, parent_node, scale, scaler_fn):
        # ros node
        self._node = parent_node

        # video refresh
        self._overlay = None
        self._graphics_group = None
        self._graphics_busy = False
        self._graphics_future = None

        # GUI
        self._width = 0
        self._height = 0
        self._scale = scale
        self._scaler_fn = scaler_fn
        self._top_gui_surf = None
        self._bottom_gui_surf = None
        self._left_gui_surf = None
        self._right_gui_surf = None
        self._left_panel_width = 150
        self._right_panel_width = 150
        self._top_panel_height = 50
        self._bottom_panel_height = 1024

        self._dump_dir = os.path.join(get_package_share_directory("auspex_emu"), "graphics_dump")
        if not os.path.exists(self._dump_dir):
            os.makedirs(self._dump_dir)

        print("[SnesRosPPU] Allocated!")

    def init_overlay(self, parent_surf):
        """
        Initialize overlay segments
        """
        self._overlay = pygame.Surface((parent_surf.get_width(), parent_surf.get_height()), pygame.SRCALPHA)
        self._overlay.fill((0,0,0,0))


    def blit_gui(self, screen):
        screen.blit(self._scaler_fn(self._overlay), (self._left_panel_width, self._top_panel_height))
        # TODO: add debug blits, e.g. tileset display
        screen.blit(self._top_gui_surf, (0, 0))
        screen.blit(self._scaler_fn(self._bottom_gui_surf), (0, self._top_panel_height + self._scale * self._height + 10))
        screen.blit(self._left_gui_surf, (0, self._top_panel_height))
        screen.blit(self._right_gui_surf, (self._left_panel_width + self._scale * self._width, self._top_panel_height))
        self._overlay.fill((0,0,0,0))

    def update_gui(self, pitch, width, height):
        """
        Update the PPU processing gui (frame stats, OAM stats, bg stats, etc)
        """
        if self._top_gui_surf is None or width != self._width:
            self._top_gui_surf = pygame.Surface(
                (pitch * width, self._top_panel_height), depth=15, masks=(0x7c00, 0x03e0, 0x001f, 0)
            )
            self._top_gui_surf.fill((0,0,255))
        if self._bottom_gui_surf is None or width != self._width:
            self._bottom_gui_surf = pygame.Surface(
                (pitch * width, self._bottom_panel_height), depth=15, masks=(0x7c00, 0x03e0, 0x001f, 0)
            )
            self._bottom_gui_surf.fill((0,0,255))
        if self._left_gui_surf is None or height != self._height:
            self._left_gui_surf = pygame.Surface(
                (self._left_panel_width, height), depth=15, masks=(0x7c00, 0x03e0, 0x001f, 0)
            )
            self._left_gui_surf.fill((0,255,127))
        if self._right_gui_surf is None or height != self._height:
            self._right_gui_surf = pygame.Surface(
                (self._right_panel_width, height), depth=15, masks=(0x7c00, 0x03e0, 0x001f, 0)
            )
            self._right_gui_surf.fill((0,255,127))

        self._width = width
        self._height = height

    def locate_sprite(self, sprite):
        """Draw boxes around sprites with graphics data."""
        swidth = 8
        sheight = 8
        if sprite.size:
            swidth = 16
            sheight = 16
        rect_thickness = 1
        rect_color = (0, 255, 0)  # Red color

        # Create a pygame.Rect object for the rectangle
        rect = pygame.Rect((sprite.x, sprite.y), (swidth, sheight))

        # Draw the rectangle on the surface
        if self._overlay:
            pygame.draw.rect(self._overlay, rect_color, rect, rect_thickness)

    def display_tile_character(self, char_data, color_depth, palette):
        char_data = char_data.reshape(color_depth, 8) # color_depth number of bitplanes along axis 1
        #print(f"??? TileChar[{idx}]: {char_data}")
        # draw boxes around sprites
        ret = pygame.Surface((8, 8), depth=15, masks=(0x7c00, 0x03e0, 0x001f, 0))
        # Create meshgrid for indices
        char_size = char_data.size # 16 bit char_data

        # FIXME: make sure this is right
        # Extract relevant bits from char_data using numpy operations
        if color_depth == 2:
            i, j = np.meshgrid(np.arange(8), np.arange(8), indexing='ij')
            pidx = (
                (((char_data[0, i] >> (7 - j)) & 0x1) << 0) |
                (((char_data[1, i] >> (7 - j)) & 0x1) << 1)
            )
        elif color_depth == 4:
            # 8 bytes on i along j are the first bitplane
            # next 8 bytes on i+1 along j are the second bitplane
            i, j = np.meshgrid(np.arange(8), np.arange(8), indexing='ij')
            pidx = (
                (((char_data[0, i] >> (7 - j)) & 0x1) << 0) | # i is row, bp0 forms the LSB
                (((char_data[1, i] >> (7 - j)) & 0x1) << 1) |
                (((char_data[2, i] >> (7 - j)) & 0x1) << 2) |
                (((char_data[3, i] >> (7 - j)) & 0x1) << 3)     # bp3 is the MSB
            )
        elif color_depth == 8:
            i, j = np.meshgrid(np.arange(8), np.arange(8), indexing='ij')
            pidx = (
                char_data[j, i]
            )

        # Map pidx to 15-bit colors using the palette
        color_15bit = palette[pidx].flat #[struct.unpack('<H', p)[0] for p in palette[pidx].flat]
        color_15bit = np.array(color_15bit, dtype='uint16').tobytes()
        ret.get_buffer().write(ctypes.string_at(color_15bit, len(color_15bit)), 0)
        return ret

    def graphics_response(self, future):
        """
        This function takes PPU data returned by the service call and translates it
        into pygame surfaces that can be cached/stored for use in world building.
        This includes: a pygame.Surface for each BG layer, and a pygame.Surface for
        each sprite object encountered in OAM.
        """
        try:
            rep = future.result()
            if not rep.valid:
                self._node.get_logger().error("Invalid Graphics Reply!")
                return
            ctr = 0
            screen_width = self._left_panel_width + self._right_panel_width + self._width
            self._node.get_logger().info(f"OAM tile address: {hex(rep.oam.tile_address)}")
            sprite_data = []
            for i, sp in enumerate(rep.oam.sprites):
                if sp.priority == 0:
                    continue
                color_depth = get_color_depth(0, rep.bgd.bg_mode)
                sprite_data.append([i, (sp.x, sp.y), hex(sp.name), hex(sp.size), sp.priority])
                #palette = rep.cgd.data[0x10*sp.palette:0x10*sp.palette + 0x10]
                #self._node.get_logger().info(f"PALETTE: {len(palette)} | {[hex(p) for p in palette]}")
                self.locate_sprite(sp)

                char_addr = 2 * (rep.oam.tile_address + sp.name)
                #base_location = 0
                #char_addr = (base_location << 13) + (8 * color_depth * sp.name)
                palette = get_palette(rep.cgd.data, sp.palette, 0, rep.bgd.bg_mode)
                #print(f"??? {hex(tile_word)} | {hex(char_addr)} | {hex(palette_idx)} | {palette}")
                if len(palette) <= 0:
                    continue

                char_data = np.frombuffer(bytes(rep.vram[char_addr:char_addr + 8 * color_depth]), dtype='uint8')
                tile_char = self.display_tile_character(char_data, color_depth, palette)
                # TODO: dump tiles in a files
                #self._bottom_gui_surf.blit(tile_char, (ctr*8 % screen_width, ctr)) #, ctr*8 // screen_width))
                pygame.image.save(tile_char, os.path.join(self._dump_dir, f"sprite{i:03d}.png"))
                ctr += 1


            sprite_header = ['idx', 'location', 'name', 'size', 'priority']
            sprite_table = tabulate.tabulate(sprite_data, sprite_header, tablefmt='grid')
            self._node.get_logger().info(f"OAM:\n{sprite_table}")

            self._node.get_logger().info(f"Background mode: {hex(rep.bgd.bg_mode)} | {rep.bgd.bg3_priority}")
            bg_data = []
            for j, bg in enumerate(rep.bgd.backgrounds):
                color_depth = get_color_depth(j, rep.bgd.bg_mode)
                bg_data.append([j, color_depth, hex(bg.name_base), hex(bg.size), hex(bg.sc_size), hex(bg.sc_base), bg.hoffset, bg.voffset])
                # tilemap start: bg.sc_base
                # graphics start: bg.name_base
                # FIXME:
                goffset = 2 * bg.sc_base
                toffset = 2 * bg.name_base
                graphics = rep.vram[goffset:goffset + 1024 * 8 * color_depth]
                for i in range(512):
                    # palette and graphic come from tilemap words
                    tile_word = struct.unpack('<H', rep.vram[toffset + i * 2:toffset + i * 2 + 2])[0]
                    char_addr = tile_word & 0x03FF
                    palette_idx = tile_word & 0x1C00
                    palette = get_palette(rep.cgd.data, palette_idx, j, rep.bgd.bg_mode)
                    #print(f"??? {hex(tile_word)} | {hex(char_addr)} | {hex(palette_idx)} | {palette}")
                    if len(palette) <= 0:
                        continue
                    char_data = np.frombuffer(bytes(graphics[char_addr * 8 * color_depth:(char_addr + 1) * 8 * color_depth]), dtype='uint8')
                    self._bottom_gui_surf.blit(self.display_tile_character(char_data, color_depth, palette), (ctr*8 % screen_width, ctr*64 // screen_width))
                    ctr += 1

                # color depth from bg mode
                ### Summary of Color Depths:
                ### - **2 bits per pixel (4 colors)**: Modes 0, 1 (BG3), and 4 (BG2)
                ### - **4 bits per pixel (16 colors)**: Modes 0, 1 (BG1 and BG2), 2, 3 (BG2), 5 (BG1), and 6
                ### - **8 bits per pixel (256 colors)**: Modes 3 (BG1), 4 (BG1), and 7
            bg_header = ['idx', 'color_depth', 'name_base', 'size', 'sc_size', 'sc_base', 'hoffset', 'voffset']
            bg_table = tabulate.tabulate(bg_data, bg_header, tablefmt='grid')
            self._node.get_logger().info(f"BG:\n{bg_table}")

            # dump tilemap
            #ctr = 0
            #for i in range(2000):
            #    char_data = rep.vram[i*8:i*8 + 8*color_depth]
            #    self._bottom_gui_surf.blit(self.display_tile_character(char_data, palette), (ctr*8 % screen_width, ctr*64 // screen_width))
            #    ctr += 1

            self._graphics_busy = False

        except Exception as e:
            self._node.get_logger().error(f"Error: {e} | {traceback.format_exc()}")

    def process_ppu_snapshot(self):
        """
        """
        # make graphics call
        self._graphics_busy = True
        req = SnesGraphics.Request()
        self._graphics_future = self._graphics_client.call_async(req)
        self._graphics_future.add_done_callback(self.graphics_response)

    def is_busy(self):
        return self._graphics_busy

    def get_offset(self):
        return (self._left_panel_width,self._top_panel_height)

    def gui_width(self):
        return self._left_panel_width + self._right_panel_width

    def gui_height(self):
        return self._top_panel_height + self._bottom_panel_height

    def initialize(self):

        self._graphics_group = MutuallyExclusiveCallbackGroup()
        self._graphics_client = self._node.create_client(SnesGraphics, "/emulators/auspex_emu/vram", callback_group=self._graphics_group)

        if not self._graphics_client.wait_for_service(timeout_sec=5.0):
            self._node.get_logger().info('Emulation instance not available to attach!')
            return False

        print("[SnesRosPygame] Initialized!")
        return True

    def teardown(self):
        pass
