"""
MK11-specific MKO struct overrides.

MK11 modified the function header layout from IJ2 (88 bytes vs 80 bytes).
The tweakvar header is also different (40 bytes).
"""

from ctypes import c_uint32, c_uint64
from mk_utils.utils.structs import Struct


class MK11ScriptFunctionHeader(Struct):
    """MK11 script function header — 88 bytes.

    Layout differs from IJ2: name_hash moved to +0x08, different field order.
    """
    _fields_ = [
        ("name_offset", c_uint32),       # +00
        ("_pad0", c_uint32),             # +04
        ("name_hash", c_uint32),         # +08
        ("_pad1", c_uint32),             # +0C
        ("num_args", c_uint32),          # +10
        ("arg_string_hash", c_uint32),   # +14
        ("bytecode_offset", c_uint32),   # +18
        ("_pad2", c_uint32),             # +1C
        ("bytecode_size", c_uint32),     # +20
        ("_pad3", c_uint32),             # +24
        ("stack_offset", c_uint32),      # +28
        ("_pad4", c_uint32),             # +2C
        ("stack_size", c_uint32),        # +30
        ("_pad5", c_uint32),             # +34
        ("scratch_size", c_uint32),      # +38
        ("_pad6", c_uint32),             # +3C
        ("checked_pointer_offset", c_uint32),  # +40
        ("_pad7", c_uint32),             # +44
        ("function_index", c_uint32),    # +48
        ("local_fixup_count", c_uint32), # +4C
    ]


class MK11TweakvarHeader(Struct):
    """MK11 tweakvar header — 40 bytes."""
    _fields_ = [
        ("name_offset", c_uint32),
        ("_pad0", c_uint32),
        ("name_hash", c_uint32),
        ("_pad1", c_uint32),
        ("data_offset", c_uint32),
        ("_pad2", c_uint32),
        ("data_size", c_uint32),
        ("_pad3", c_uint32),
        ("flags", c_uint32),
        ("_pad4", c_uint32),
    ]
