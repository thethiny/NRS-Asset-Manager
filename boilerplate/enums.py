"""
TODO: Game-specific enums.

Source these from reverse engineering, dumped SDK, or by comparing binary data
with known formats (IJ2, MK11).
"""

from enum import IntEnum
from typing import Dict


class ECompressionFlags(IntEnum):
    """Compression flags for this game. Values from FPackageFileSummary."""
    NONE = 0x0000
    # TODO: Add game-specific compression values
    # Example: OODLE = 0x0004 (IJ2), XBX = 0x40 (MK11)


class EPixelFormat(IntEnum):
    """Pixel formats for texture data. Order matches UE3 EPixelFormat."""
    PF_Unknown = 0x0
    PF_A32B32G32R32F = 0x1
    PF_A8R8G8B8 = 0x2
    PF_G8 = 0x3
    PF_DXT1 = 0x5
    PF_DXT5 = 0x7
    PF_BC5 = 0x1B
    PF_BC7 = 0x16
    # TODO: Fill in remaining formats from RE or by testing


# Property enum maps: maps property key_name -> enum class for EnumProperty parsing
enumMaps: Dict[str, type] = {}
