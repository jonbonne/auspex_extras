import numpy as np
import pygame

class PsychedelicBackground:
    """
    A background generator with multiple animation "modes" inspired by EarthBound's groovy, wavy effects.

    Modes:
    1 - Horizontal+Vertical wave (original)
    2 - Swirl vortex
    3 - Perspective stripe (Mode7-like)
    4 - Radial ripples
    5 - Starfield
    6 - Circuit flow
    7 - Max Headroom glitch effect
    """
    def __init__(self, w, h, mode=5,
                 star_count=200, seed=42,
                 sparkle_count=100, pan_speed=0.2,
                 # circuit flow tunables:
                 line_opacity=0.85,
                 circuit_speed=1.5,
                 line_thickness=3.0,
                 grid_spread=80):
        self.w, self.h = w, h
        x = np.linspace(0, w, w)
        y = np.linspace(0, h, h)
        self.xv, self.yv = np.meshgrid(x, y)
        self.cx, self.cy = w / 2, h / 2
        self.mode = mode
        self.counter = 0
        # For starfield mode
        rng = np.random.RandomState(seed)
        self.star_x = rng.rand(star_count) * w  # float positions
        self.star_y = rng.rand(star_count) * h
        self.star_phase = rng.rand(star_count) * 2 * np.pi
        # assign sizes: 70% small, 20% medium, 10% large
        self.star_sizes = rng.choice([1, 2, 3], size=star_count, p=[0.7, 0.2, 0.1])
        # generate static haze mask
        haze = rng.rand(h, w) * 0.6 + 0.4  # values in [0.4,1.0]
        self.haze_mask = haze.astype(np.float32)
        # sparkles for circuit mode
        self.sparkle_x = rng.rand(sparkle_count) * w
        self.sparkle_y = rng.rand(sparkle_count) * h
        self.sparkle_phase = rng.rand(sparkle_count) * 2 * np.pi
        self.pan_speed = pan_speed
        # circuit flow parameters
        self.line_opacity = np.clip(line_opacity, 0.0, 1.0)
        self.circuit_speed = circuit_speed
        self.line_thickness = line_thickness
        self.grid_spread = grid_spread

    def set_mode(self, mode: int):
        """Switch animation mode at runtime."""
        if mode not in (1, 2, 3, 4, 5, 6, 7):
            raise ValueError(f"Invalid mode: {mode}")
        self.mode = mode
        self.counter = 0

    def render(self) -> pygame.Surface:
        t = self.counter
        self.counter += 1
        if self.mode == 1:
            return self._mode_wave(t)
        elif self.mode == 2:
            return self._mode_swirl(t)
        elif self.mode == 3:
            return self._mode_perspective(t)
        elif self.mode == 4:
            return self._mode_ripples(t)
        elif self.mode == 5:
            return self._mode_starfield(t)
        elif self.mode == 6:
            return self._mode_circuit_flow(t)
        elif self.mode == 7:
            return self._mode_maxheadroom(t)

    def _mode_wave(self, t):
        # Original wavy handler
        lw = np.sin(self.yv * 0.08 + t * 0.2) * 40
        xw = self.xv + lw
        wave = 128 + 127 * np.sin(
            xw * 0.02 + t * 0.015 + np.sin(self.yv * 0.02 + t * 0.01)
        )
        return self._colorize(wave, t)

    def _mode_swirl(self, t):
        # Slow, gentle swirl
        dx = self.xv - self.cx
        dy = self.yv - self.cy
        r = np.sqrt(dx**2 + dy**2)
        theta = np.arctan2(dy, dx) + t * 0.0005  # much slower rotation
        sx = r * np.cos(theta) + self.cx
        sy = r * np.sin(theta) + self.cy
        wave = 128 + 127 * np.sin(
            (sx + sy) * 0.015 + t * 0.005  # slower wave motion
        )
        return self._colorize(wave, t)

    def _mode_perspective(self, t):
        # Calm Mode7-like perspective stripes
        depth = (self.h - self.yv) / self.h
        freq = 0.02 + depth * 0.1
        offset = np.sin(t * 0.02) * 100 * depth  # slower offset
        xw = self.xv * freq + offset
        wave = 128 + 127 * np.sin(
            xw + t * 0.01  # gentle phase shift
        )
        return self._colorize(wave, t)

    def _mode_ripples(self, t):
        # Multi-ring tessellated ripples of varying sizes
        dx = self.xv - self.cx
        dy = self.yv - self.cy
        r = np.sqrt(dx**2 + dy**2)
        # define multiple ring frequencies and speeds
        rings = [
            (0.05, 0.04),
            (0.1, 0.02),
            (0.02, 0.06),
        ]
        accum = np.zeros_like(r)
        for freq, speed in rings:
            accum += np.sin(r * freq - t * speed)
        wave = 128 + 127 * (accum / len(rings))
        return self._colorize(wave, t)

    def _mode_starfield(self, t):
        # base black canvas
        rgb = np.zeros((self.h, self.w, 3), dtype=np.float32)
        # compute pan offsets
        xs = (self.star_x + t * self.pan_speed * self.w * 0.02) % self.w
        ys = self.star_y  # static vertical
        # twinkle brightness
        phases = self.star_phase + t * (self.pan_speed * 2)
        brightness = ((np.sin(phases) + 1) / 2) * 155 + 100
        for x_f, y_f, size, v in zip(xs, ys, self.star_sizes, brightness):
            x0 = int(x_f)
            y0 = int(y_f)
            v_f = v
            # draw square star
            x1 = x0 + size
            y1 = y0 + size
            # handle horizontal wrap
            if x1 <= self.w:
                rgb[y0:y1, x0:x1] = v_f
            else:
                overlap = x1 - self.w
                rgb[y0:y1, x0:self.w] = v_f
                rgb[y0:y1, 0:overlap] = v_f
        # apply haze overlay
        haze_alpha = (self.haze_mask * 0.2)[..., np.newaxis]
        haze_color = np.array([50, 0, 80], dtype=np.float32)
        rgb = rgb * (1 - haze_alpha) + haze_color * haze_alpha
        # clamp and convert
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        return pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))

    def _mode_circuit_flow(self, t):
        # Dark background
        rgb = np.zeros((self.h, self.w, 3), dtype=np.float32)
        try:
            # compute flowing offsets
            dx = np.mod(self.xv + t * self.circuit_speed, self.grid_spread)
            dy = np.mod(self.yv + t * self.circuit_speed, self.grid_spread)
            # thicker, adjustable lines
            mask = ((dx < self.line_thickness) | (dy < self.line_thickness)).astype(np.float32)
            # glow around lines
            gt = self.line_thickness / 2
            glow = np.exp(-((dx-gt)**2 + (dy-gt)**2) / (gt*gt)).astype(np.float32)
            # global cyclical pulse (alpha-like)
            pulse = 0.8 + 0.2 * np.sin(t * self.pan_speed)
            # combine with adjustable line_opacity
            weight_line = self.line_opacity
            weight_glow = 1.0 - weight_line
            intensity = (mask * weight_line + glow * weight_glow) * pulse
            # neon-cyan coloring
            rgb[...,0] = intensity * 15
            rgb[...,1] = intensity * 200
            rgb[...,2] = intensity * 240
            # sparkles
            phases = self.sparkle_phase + t * self.pan_speed
            sparkle_b = (np.sin(phases) + 1) / 2
            for xs, ys, b in zip(self.sparkle_x, self.sparkle_y, sparkle_b):
                xi, yi = int(xs) % self.w, int(ys) % self.h
                alpha = b * 0.5
                rgb[yi, xi] = np.clip(rgb[yi, xi]*(1-alpha) + 255*alpha, 0, 255)
        except Exception as e:
            pass
        # clamp and surface
        surface = pygame.surfarray.make_surface(
            np.transpose(np.clip(rgb,0,255).astype(np.uint8), (1,0,2))
        )
        return surface

    def _mode_maxheadroom(self, t):
        """Glitchy scanline and color-separation effect inspired by the Max Headroom background."""
        # Sine-based scanline offset
        jitter = np.sin(self.yv * 0.1 + t * 0.5) * 20
        # Time-seeded random noise per frame
        rng = np.random.RandomState(int(t))
        noise = (rng.rand(self.h, self.w) - 0.5) * 10
        offset = jitter + noise
        # Apply horizontal offset
        xw = self.xv + offset
        # Separate channel wave patterns for color split
        r = 128 + 127 * np.sin(xw * 0.05 + t * 0.1)
        g = 128 + 127 * np.sin(xw * 0.04 - t * 0.1)
        b = 128 + 127 * np.sin(xw * 0.06 + t * 0.1)
        # Stack channels and finalize surface
        rgb = np.stack((r, g, b), axis=-1)
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        return pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))

    def _colorize(self, wave, t):
        # Shared color-mixing code
        phase = (np.sin(t * 0.01) + 1) / 2
        # two palettes
        r1 = (wave * 0.2 + 30) % 255
        g1 = (wave * 0.4 + 50) % 255
        b1 = (wave * 0.9 + 200) % 255
        r2 = (wave * 0.9 + 200) % 255
        g2 = (wave * 0.5 + 100) % 255
        b2 = (wave * 0.2 + 30) % 255
        r = ((1 - phase) * r1 + phase * r2).astype(np.uint8)
        g = ((1 - phase) * g1 + phase * g2).astype(np.uint8)
        b = ((1 - phase) * b1 + phase * b2).astype(np.uint8)
        rgb = np.stack((r, g, b), axis=-1)
        # transpose for pygame
        return pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
