from enum import IntEnum
from typing import Dict, Type


class IJ2CompressionType(IntEnum):
    NONE = 0x0000
    ZLIB = 0x0001
    LZO  = 0x0002
    LZX  = 0x0004
    OODLE = 0x0004  # IJ2 uses value 4 for Oodle compression


class EPixelFormat(IntEnum):
    PF_Unknown = 0
    PF_A32B32G32R32F = 1
    PF_A8R8G8B8 = 2
    PF_G8 = 3
    PF_G16 = 4
    PF_DXT1 = 5
    PF_DXT3 = 6
    PF_DXT5 = 7
    PF_UYVY = 8
    PF_FloatRGB = 9
    PF_FloatRGBA = 10
    PF_DepthStencil = 11
    PF_ShadowDepth = 12
    PF_FilteredShadowDepth = 13
    PF_R32F = 14
    PF_FloatRGBA_Full = 15
    PF_R16G16_UNORM = 16
    PF_R16G16_SNORM = 17
    PF_R16G16_FLOAT = 18
    PF_G32R32F = 19
    PF_A2B10G10R10 = 20
    PF_BC6 = 21
    PF_BC7 = 22
    PF_A16B16G16R16 = 23
    PF_D24 = 24
    PF_R16F = 25
    PF_R16_UNORM = 26
    PF_BC5 = 27
    PF_V8U8 = 28
    PF_A1 = 29
    PF_FloatR11G11B10 = 30
    PF_X24S8 = 31
    PF_R8 = 32
    PF_R8_UInt = 33
    PF_G8R8 = 34
    PF_R32G32B32A32 = 35
    PF_R8G8B8A8_Signed = 36
    PF_S8 = 37
    PF_FloatR9G9B9E5 = 38
    PF_A8R8G8B8_SRGB = 39
    PF_Depth16Stencil = 40
    PF_R32_UInt = 41
    PF_BC4 = 42
    PF_B4G4R4A4 = 43
    PF_R16_UInt = 44
    PF_R16G16B16A16_UInt = 45
    PF_R32G32_UInt = 46
    PF_D32 = 47
    PF_FloatRGB_Full = 48
    PF_R16G16_UInt = 49
    PF_COUNT = 50


# IJ2 enum maps for property parsing
enumMaps: Dict[str, type] = {}
