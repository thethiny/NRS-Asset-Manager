"""
MKO (MKScript) common structures.

MKO files are compiled bytecode for NRS's proprietary MKScript scripting language.
Format is game-specific (incremental engine updates may change struct sizes),
but the overall layout is consistent: a flat 18-field header followed by
contiguous data sections.

IJ2 glue_hash: 0xDC1113E5
"""

from ctypes import c_uint32, c_uint64, c_int32, c_char
from mk_utils.utils.structs import Struct


class MKOHeader(Struct):
    """MKO file header — 18 x u32 = 72 bytes."""
    _fields_ = [
        ("endian_flag", c_uint32),
        ("glue_hash", c_uint32),
        ("num_functions", c_uint32),
        ("num_static_variables", c_uint32),
        ("num_dynamic_variables", c_uint32),
        ("num_externs", c_uint32),
        ("num_extern_variables", c_uint32),
        ("num_assets", c_uint32),
        ("num_global_checked_pointers", c_uint32),
        ("num_total_checked_pointers", c_uint32),
        ("bytecode_data_len", c_uint32),
        ("string_argument_table_len", c_uint32),
        ("stack_data_len", c_uint32),
        ("global_fixup_list_len", c_uint32),
        ("num_tweakvars", c_uint32),
        ("num_source_files", c_uint32),
        ("tweak_string_table_len", c_uint32),
        ("dynamic_global_stack_usage", c_uint32),
    ]


class ScriptFunctionHeader(Struct):
    """Script function header — 80 bytes fixed + variable trailing fixups.

    In the file, offset fields are raw byte offsets into the MKO data.
    At runtime, the game patches these to absolute pointers.
    """
    _fields_ = [
        ("name_offset", c_uint32),
        ("_pad0", c_uint32),
        ("bytecode_offset", c_uint32),
        ("_pad1", c_uint32),
        ("stack_offset", c_uint32),
        ("_pad2", c_uint32),
        ("pack_attributes", c_uint64),
        ("checked_pointer_offset", c_uint32),
        ("_pad3", c_uint32),
        ("name_hash", c_uint32),
        ("bytecode_size", c_uint32),
        ("stack_size", c_uint32),
        ("scratch_size", c_uint32),
        ("num_args", c_uint32),
        ("function_index", c_uint32),
        ("local_fixup_count", c_uint32),
        ("checked_object_count", c_uint32),
        ("arg_string_hash", c_uint32),
        ("_unused", c_uint32),
    ]


class ScriptVariableHeader(Struct):
    """Script variable header — 24 bytes."""
    _fields_ = [
        ("stack_offset", c_uint32),
        ("_pad0", c_uint32),
        ("name_hash", c_uint32),
        ("data_size", c_uint32),
        ("stride", c_uint32),
        ("_pad1", c_uint32),
    ]


class ScriptExternHeader(Struct):
    """External script reference — 24 bytes (3 fields, each u32 + u32 padding for 8-byte alignment)."""
    _fields_ = [
        ("file_name_offset", c_uint32),
        ("_pad0", c_uint32),
        ("name_offset", c_uint32),
        ("_pad1", c_uint32),
        ("name_hash", c_uint32),
        ("_pad2", c_uint32),
    ]


class ScriptAssetHeader(Struct):
    """Asset reference header — 32 bytes."""
    _fields_ = [
        ("name_offset", c_uint32),
        ("_pad0", c_uint32),
        ("hash", c_uint32),
        ("_pad1", c_uint32),
        ("asset_ptr", c_uint64),
        ("asset_type", c_uint32),
        ("_pad2", c_uint32),
    ]


class FixupHeader(Struct):
    """Fixup entry — 16 bytes."""
    _fields_ = [
        ("fixup_type", c_int32),
        ("offset", c_uint32),
        ("src_value", c_uint32),
        ("extra", c_uint32),
    ]


FIXUP_TYPE_NAMES = {
    0: "FT_STRING",
    1: "FT_STRING_BC",
    2: "FT_ASSET",
    3: "FT_ASSET_BC",
    4: "FT_PFUNC",
    5: "FT_PFUNC_BC",
}

ASSET_TYPE_NAMES = {
    0: "Animation",
    1: "Generic",
    2: "SkeletalMesh",
    3: "StaticMesh",
    4: "Texture",
    5: "Undefined",
}
