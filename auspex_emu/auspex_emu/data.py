from typing import Tuple

class RomHeader:
    '''
    $FFC0	21	Cartridge title (21 bytes uppercase ASCII. Unused bytes should be spaces.)
    $FFD5	1	ROM speed and memory map mode (LoROM/HiROM/ExHiROM)
    $FFD6	1	Chipset (Indicates if a cartridge contains extra RAM, a battery, and/or a coprocessor)
    $FFD7	1	ROM size: 1<<N kilobytes, rounded up (so 8=256KB, 12=4096KB and so on)
    $FFD8	1	RAM size: 1<<N kilobytes (so 1=2KB, 5=32KB, and so on)
    $FFD9	1	Country (Implies NTSC/PAL)
    $FFDA	1	Developer ID
    $FFDB	1	ROM version (0 = first)
    $FFDC	2	Checksum complement (Checksum ^ $FFFF)
    $FFDE	2	Checksum
    '''

    @staticmethod
    def MemSize(value: int) -> int:
        return (1 << value)

    Speeds = {
        0: 'Slow',
        1: 'Fast'
    }

    Modes = {
        0: 'LoRom',
        1: 'HiRom',
        5: 'ExHiRom'
    }

    LoRom = 0
    HiRom = 1
    ExHiRom = 5

    @staticmethod
    def SpeedAndMode(value: int) -> Tuple[str, str]:

        rom_speed = RomHeader.Speeds[value & 0x10]
        mem_mode = RomHeader.Modes[value & 0x0F]
        return rom_speed, mem_mode

    @staticmethod
    def Region(value: int) -> str:
        return 'NTSC' if value else 'PAL'

    @staticmethod
    def Chipset(value: int) -> str:

        chipset = 'None'
        if value == 0x00:
            chipset = 'ROM only'
        if value == 0x01:
            chipset = 'ROM + RAM'
        if value == 0x02:
            chipset = 'ROM + RAM + battery'
        if value & 0x0F == 0x03:
            chipset = 'ROM + coprocessor'
        if value & 0x0F == 0x04:
            chipset = 'ROM + coprocessor + RAM'
        if value & 0x0F == 0x05:
            chipset = 'ROM + coprocessor + RAM + battery'
        if value & 0x0F == 0x06:
            chipset = 'ROM + coprocessor + battery'
        if value & 0xF0 == 0x00:
            chipset = 'Coprocessor is DSP (DSP-1, 2, 3 or 4)'
        if value & 0xF0 == 0x10:
            chipset = 'Coprocessor is GSU (SuperFX)'
        if value & 0xF0 == 0x20:
            chipset = 'Coprocessor is OBC1'
        if value & 0xF0 == 0x30:
            chipset = 'Coprocessor is SA-1'
        if value & 0xF0 == 0x40:
            chipset = 'Coprocessor is S-DD1'
        if value & 0xF0 == 0x50:
            chipset = 'Coprocessor is S-RTC'
        if value & 0xF0 == 0xE0:
            chipset = 'Coprocessor is Other (Super Game Boy/Satellaview)'
        if value & 0xF0 == 0xF0:
            chipset = 'Coprocessor is Custom (specified with $FFBF)'
        return chipset
