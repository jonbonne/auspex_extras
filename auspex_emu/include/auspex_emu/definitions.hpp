#pragma once

#include <auspex_interfaces/srv/snes_emu_state.hpp>
#include <auspex_interfaces/srv/snes_mem_state.hpp>

namespace auspex
{
namespace emu
{
static constexpr unsigned OAM_SIZE = 544;
static constexpr unsigned CGRAM_SIZE = 512;
static constexpr unsigned VRAM_SIZE = 65536;
static constexpr unsigned MAX_SPRITES = 128;
static constexpr unsigned MAX_BACKGROUNDS = 4;

static constexpr uint8_t CARTRIDGE_RAM = auspex_interfaces::srv::SnesMemState_Request::CARTRIDGE_RAM;
static constexpr uint8_t CARTRIDGE_RTC = auspex_interfaces::srv::SnesMemState_Request::CARTRIDGE_RTC;
static constexpr uint8_t GAME_BOY_RAM = auspex_interfaces::srv::SnesMemState_Request::GAME_BOY_RAM;
static constexpr uint8_t GAME_BOY_RTC = auspex_interfaces::srv::SnesMemState_Request::GAME_BOY_RTC;
static constexpr uint8_t SYSTEM_VRAM = auspex_interfaces::srv::SnesMemState_Request::SYSTEM_VRAM;
static constexpr uint8_t SYSTEM_PPU = auspex_interfaces::srv::SnesMemState_Request::SYSTEM_PPU;

static constexpr uint8_t RUNNING = auspex_interfaces::srv::SnesEmuState_Request::RUNNING;
static constexpr uint8_t POWER = auspex_interfaces::srv::SnesEmuState_Request::POWER;
static constexpr uint8_t RESET = auspex_interfaces::srv::SnesEmuState_Request::RESET;
static constexpr uint8_t SAVE = auspex_interfaces::srv::SnesEmuState_Request::SAVE;
static constexpr uint8_t LOAD = auspex_interfaces::srv::SnesEmuState_Request::LOAD;

typedef unsigned char bool8;

struct SOBJ
{
    int16_t   HPos;
    uint16_t  VPos;
    uint8_t   HFlip;
    uint8_t   VFlip;
    uint16_t  Name;
    uint8_t   Priority;
    uint8_t   Palette;
    uint8_t   Size;
};

struct SPPU
{
    struct
    {
        bool8   High;
        uint8_t   Increment;
        uint16_t  Address;
        uint16_t  Mask1;
        uint16_t  FullGraphicCount;
        uint16_t  Shift;
    }   VMA;

    uint32_t  WRAM;

    struct
    {
        uint16_t  SCBase;
        uint16_t  HOffset;
        uint16_t  VOffset;
        uint8_t   BGSize;
        uint16_t  NameBase;
        uint16_t  SCSize;
    }   BG[4];

    uint8_t   BGMode;
    uint8_t   BG3Priority;

    bool8   CGFLIP;
    uint8_t   CGFLIPRead;
    uint8_t   CGADD;
    uint16_t  CGDATA[256];

    struct SOBJ OBJ[128];
    bool8   OBJThroughMain;
    bool8   OBJThroughSub;
    bool8   OBJAddition;
    uint16_t  OBJNameBase;
    uint16_t  OBJNameSelect;
    uint8_t   OBJSizeSelect;

    uint16_t  OAMAddr;
    uint16_t  SavedOAMAddr;
    uint8_t   OAMPriorityRotation;
    uint8_t   OAMFlip;
    uint8_t   OAMReadFlip;
    uint16_t  OAMTileAddress;
    uint16_t  OAMWriteRegister;
    uint8_t   OAMData[512 + 32];

    uint8_t   FirstSprite;
    uint8_t   LastSprite;
    uint8_t   RangeTimeOver;

    bool8   HTimerEnabled;
    bool8   VTimerEnabled;
    short   HTimerPosition;
    short   VTimerPosition;
    uint16_t  IRQHBeamPos;
    uint16_t  IRQVBeamPos;

    uint8_t   HBeamFlip;
    uint8_t   VBeamFlip;
    uint16_t  HBeamPosLatched;
    uint16_t  VBeamPosLatched;
    uint16_t  GunHLatch;
    uint16_t  GunVLatch;
    uint8_t   HVBeamCounterLatched;

    bool8   Mode7HFlip;
    bool8   Mode7VFlip;
    uint8_t   Mode7Repeat;
    short   MatrixA;
    short   MatrixB;
    short   MatrixC;
    short   MatrixD;
    short   CentreX;
    short   CentreY;
    short   M7HOFS;
    short   M7VOFS;

    uint8_t   Mosaic;
    uint8_t   MosaicStart;
    bool8   BGMosaic[4];

    uint8_t   Window1Left;
    uint8_t   Window1Right;
    uint8_t   Window2Left;
    uint8_t   Window2Right;
    bool8   RecomputeClipWindows;
    uint8_t   ClipCounts[6];
    uint8_t   ClipWindowOverlapLogic[6];
    uint8_t   ClipWindow1Enable[6];
    uint8_t   ClipWindow2Enable[6];
    bool8   ClipWindow1Inside[6];
    bool8   ClipWindow2Inside[6];

    bool8   ForcedBlanking;

    uint8_t   FixedColourRed;
    uint8_t   FixedColourGreen;
    uint8_t   FixedColourBlue;
    uint8_t   Brightness;
    uint16_t  ScreenHeight;

    bool8   Need16x8Mulitply;
    uint8_t   BGnxOFSbyte;
    uint8_t   M7byte;

    uint8_t   HDMA;
    uint8_t   HDMAEnded;

    uint8_t   OpenBus1;
    uint8_t   OpenBus2;
};

}  // namespace emu
}  // namespace auspex
