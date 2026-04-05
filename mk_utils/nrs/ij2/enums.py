from enum import IntEnum
from typing import Dict, Type


class ECompressionFlags(IntEnum):
    NONE = 0x0000
    ZLIB = 0x0001
    LZO  = 0x0002
    OODLE = 0x0004
    COMPRESS_PFS = 0x0008
    COMPRESS_BiasMemory = 0x0010
    COMPRESS_BiasSpeed = 0x0020
    COMPRESS_ValidMethods = 0x000F


class EPixelFormat(IntEnum):
    PF_Unknown = 0x0
    PF_A32B32G32R32F = 0x1
    PF_A8R8G8B8 = 0x2
    PF_G8 = 0x3
    PF_G16 = 0x4
    PF_DXT1 = 0x5
    PF_DXT3 = 0x6
    PF_DXT5 = 0x7
    PF_UYVY = 0x8
    PF_FloatRGB = 0x9
    PF_FloatRGBA = 0xA
    PF_DepthStencil = 0xB
    PF_ShadowDepth = 0xC
    PF_FilteredShadowDepth = 0xD
    PF_R32F = 0xE
    PF_FloatRGBA_Full = 0xF
    PF_R16G16_UNORM = 0x10
    PF_R16G16_SNORM = 0x11
    PF_R16G16_FLOAT = 0x12
    PF_G32R32F = 0x13
    PF_A2B10G10R10 = 0x14
    PF_BC6 = 0x15
    PF_BC7 = 0x16
    PF_A16B16G16R16 = 0x17
    PF_D24 = 0x18
    PF_R16F = 0x19
    PF_R16_UNORM = 0x1A
    PF_BC5 = 0x1B
    PF_V8U8 = 0x1C
    PF_A1 = 0x1D
    PF_FloatR11G11B10 = 0x1E
    PF_X24S8 = 0x1F
    PF_R8 = 0x20
    PF_R8_UInt = 0x21
    PF_G8R8 = 0x22
    PF_R32G32B32A32 = 0x23
    PF_R8G8B8A8_Signed = 0x24
    PF_S8 = 0x25
    PF_FloatR9G9B9E5 = 0x26
    PF_A8R8G8B8_SRGB = 0x27
    PF_Depth16Stencil = 0x28
    PF_R32_UInt = 0x29
    PF_BC4 = 0x2A
    PF_B4G4R4A4 = 0x2B
    PF_R16_UInt = 0x2C
    PF_R16G16B16A16_UInt = 0x2D
    PF_R32G32_UInt = 0x2E
    PF_COUNT = 0x2F
    
class EPackageFlags(IntEnum):
    PKG_SavedWithNewerVersion = 0x20
    PKG_ContainsMap           = 0x20000
    PKG_DisallowLazyLoading   = 0x80000
    PKG_CookedForODSC         = 0x800000
    PKG_StoresShaderCaches    = 0x1000000
    PKG_StoreCompressed       = 0x2000000

class EPackageFilefindType(IntEnum):
    Unlocalized = 0
    Localized = 1

# IJ2 enum maps for property parsing
enumMaps: Dict[str, type] = {}
