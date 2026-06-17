"""
MKO file parser.

Parses compiled MKScript bytecode files (.mko) used by NRS games.
Extracts function definitions, variable tables, extern references,
asset references, and string tables.

Usage:
    parser = MKOParser("path/to/file.mko")
    parser.parse()
    print(parser)
"""

import logging
from ctypes import sizeof, c_uint32, c_uint64
from typing import List, Optional

from mk_utils.nrs.mkscript.mko_common import (
    MKOHeader,
    ScriptFunctionHeader,
    ScriptVariableHeader,
    ScriptExternHeader,
    ScriptAssetHeader,
    FixupHeader,
    FIXUP_TYPE_NAMES,
    ASSET_TYPE_NAMES,
)
from mk_utils.nrs.mkscript.mko_mk11 import MK11ScriptFunctionHeader, MK11TweakvarHeader
from mk_utils.utils.filereader import FileReader
from mk_utils.utils.structs import Struct

KNOWN_GLUE_HASHES = {
    0xDC1113E5: "IJ2",
    0x3055F8D9: "MK11",
}

# MK11 function header layout differs from IJ2 and is not fully reverse-engineered.
# The field at +0x00 is NOT name_offset in MK11 — the struct layout needs further RE.
# For now, MK11 parsing is best-effort: header and section counts are correct,
# but function/extern name resolution may be wrong.

logger = logging.getLogger("MKOParser")


class MKOFunction:
    """Parsed function with resolved name and metadata."""
    def __init__(self, header: ScriptFunctionHeader, name: str, local_fixups: List[FixupHeader]):
        self.header = header
        self.name = name
        self.local_fixups = local_fixups

    def __str__(self):
        h = self.header
        return (
            f"{self.name}  "
            f"args={h.num_args} stack={h.stack_size} scratch={h.scratch_size} "
            f"bytecode={h.bytecode_size}B fixups={h.local_fixup_count}"
        )


class MKOVariable:
    """Parsed variable with resolved name hash."""
    def __init__(self, header: ScriptVariableHeader):
        self.header = header
        self.name_hash = header.name_hash
        self.data_size = header.data_size
        self.stride = header.stride

    def __str__(self):
        return f"hash=0x{self.name_hash:08X} size={self.data_size} stride={self.stride}"


class MKOExtern:
    """Parsed external script reference."""
    def __init__(self, header: ScriptExternHeader, file_name: str, name: str):
        self.header = header
        self.file_name = file_name
        self.name = name

    def __str__(self):
        return f"{self.file_name}::{self.name}"


class MKOAsset:
    """Parsed asset reference."""
    def __init__(self, header: ScriptAssetHeader, name: str):
        self.header = header
        self.name = name
        self.asset_type = ASSET_TYPE_NAMES.get(header.asset_type, f"Unknown({header.asset_type})")

    def __str__(self):
        return f"{self.name} ({self.asset_type})"


class MKOParser(FileReader):
    """Parser for MKO (MKScript) bytecode files."""

    def __init__(self, source):
        super().__init__(source)
        self.header: Optional[MKOHeader] = None
        self.game: str = "Unknown"
        self.functions: List[MKOFunction] = []
        self.static_variables: List[MKOVariable] = []
        self.dynamic_variables: List[MKOVariable] = []
        self.externs: List[MKOExtern] = []
        self.assets: List[MKOAsset] = []
        self.global_fixups: List[FixupHeader] = []
        self.string_table: bytes = b""
        self.tweak_string_table: bytes = b""
        self.bytecode: bytes = b""
        self.source_files: List[str] = []
        self.parsed = False

    def parse(self):
        self.header = MKOHeader.read(self.mm)

        if self.header.endian_flag != 1:
            raise ValueError(
                f"Big-endian MKO files are not supported (endian_flag={self.header.endian_flag}). "
                f"Only little-endian (PC) files are supported."
            )

        self.game = KNOWN_GLUE_HASHES.get(self.header.glue_hash, "Unknown")
        self._func_header_type = MK11ScriptFunctionHeader if self.game == "MK11" else ScriptFunctionHeader

        h = self.header
        data_start = sizeof(MKOHeader)

        # Bytecode section
        self.bytecode = bytes(self.mm[data_start:data_start + h.bytecode_data_len])
        self.mm.seek(data_start + h.bytecode_data_len)

        # Function pointer table (8 bytes per entry — file offsets, not used for parsing)
        self.mm.seek(8 * h.num_functions, 1)

        # Function headers (variable size: header + 16 * local_fixup_count each)
        self.functions = self._parse_functions(h.num_functions)

        # Static variable pointer table + headers
        self.mm.seek(8 * h.num_static_variables, 1)
        self.static_variables = self._parse_variables(h.num_static_variables)

        # Dynamic variable pointer table + headers
        self.mm.seek(8 * h.num_dynamic_variables, 1)
        self.dynamic_variables = self._parse_variables(h.num_dynamic_variables)

        # Extern pointer table + headers
        self.mm.seek(8 * h.num_externs, 1)
        self.externs = self._parse_externs_deferred(h.num_externs)

        # Extern variable headers
        self._skip_extern_variables(h.num_extern_variables)

        # Source file name pointers
        self.mm.seek(8 * h.num_source_files, 1)

        # Checked pointer list
        self.mm.seek(8 * h.num_total_checked_pointers, 1)

        # Asset pointer table + headers
        self.mm.seek(8 * h.num_assets, 1)
        self.assets = self._parse_assets_deferred(h.num_assets)

        # String table location: compute from file end backwards
        # file = ... + string_table + tweak_string_table + stack_data + fixups + tweakvars
        # We know the sizes of all trailing sections, so we can find the string table
        self._locate_and_read_tables(h)

        # Now resolve names from string tables
        self._resolve_function_names()
        self._resolve_extern_names()
        self._resolve_asset_names()

        self.parsed = True
        logger.info(f"Parsed MKO: {len(self.functions)} functions, "
                     f"{len(self.static_variables)}+{len(self.dynamic_variables)} variables, "
                     f"{len(self.externs)} externs, {len(self.assets)} assets")

    def _locate_and_read_tables(self, h):
        """Locate string table and other trailing sections.

        The string table position can vary between games due to section ordering
        differences. We locate it by searching for the `__global__` marker string
        which is always present as the first function's name, or by using the
        current position if sequential walking succeeded.
        """
        # Try sequential position first
        current_pos = self.mm.tell()
        probe = bytes(self.mm[current_pos:current_pos + min(16, h.string_argument_table_len)])

        # Check if the current position looks like string data
        if h.string_argument_table_len > 0 and probe and probe[0:1] != b'\x00' and all(
            (32 <= b < 127 or b == 0) for b in probe[:min(len(probe), 16)]
        ):
            str_start = current_pos
        else:
            # Search for __global__ in the file to find string table
            idx = self.mm[:].find(b'__global__')
            if idx >= 0:
                str_start = idx
            else:
                str_start = current_pos
                logger.warning("Could not locate string table, using current position")

        self.string_table = bytes(self.mm[str_start:str_start + h.string_argument_table_len])

        # Tweak string table follows string table
        tweak_start = str_start + h.string_argument_table_len
        self.tweak_string_table = bytes(self.mm[tweak_start:tweak_start + h.tweak_string_table_len])

        # Stack initializer data
        stack_start = tweak_start + h.tweak_string_table_len

        # Global fixup list follows stack data
        fixup_start = stack_start + h.stack_data_len
        self.mm.seek(fixup_start)
        self.global_fixups = [
            Struct.read_buffer(self.mm, FixupHeader) for _ in range(h.global_fixup_list_len)
        ]

    def _parse_functions(self, count: int) -> List[MKOFunction]:
        functions = []
        for _ in range(count):
            fh = Struct.read_buffer(self.mm, self._func_header_type)
            local_fixups = [
                Struct.read_buffer(self.mm, FixupHeader)
                for _ in range(fh.local_fixup_count)
            ]
            functions.append(MKOFunction(fh, "", local_fixups))
        return functions

    def _parse_variables(self, count: int) -> List[MKOVariable]:
        return [MKOVariable(Struct.read_buffer(self.mm, ScriptVariableHeader)) for _ in range(count)]

    def _parse_externs_deferred(self, count: int) -> List[MKOExtern]:
        externs = []
        for _ in range(count):
            eh = Struct.read_buffer(self.mm, ScriptExternHeader)
            externs.append(MKOExtern(eh, "", ""))
        return externs

    def _skip_extern_variables(self, count: int):
        # ScriptExternVariableHeader size is 24 bytes (FName(8) + ptr(8) + flags(4) + name_offset(4))
        self.mm.seek(24 * count, 1)

    def _parse_assets_deferred(self, count: int) -> List[MKOAsset]:
        assets = []
        for _ in range(count):
            ah = Struct.read_buffer(self.mm, ScriptAssetHeader)
            assets.append(MKOAsset(ah, ""))
        return assets

    def _read_string_at(self, table: bytes, offset: int) -> str:
        # Offsets are 1-based in the file format
        offset -= 1
        if offset < 0 or offset >= len(table):
            return f"<invalid_offset_0x{offset+1:X}>"
        end = table.index(0, offset) if 0 in table[offset:] else len(table)
        return table[offset:end].decode("ascii", errors="replace")

    def _resolve_function_names(self):
        for func in self.functions:
            func.name = self._read_string_at(self.string_table, func.header.name_offset)

    def _resolve_extern_names(self):
        for ext in self.externs:
            ext.file_name = self._read_string_at(self.string_table, ext.header.file_name_offset)
            ext.name = self._read_string_at(self.string_table, ext.header.name_offset)

    def _resolve_asset_names(self):
        for asset in self.assets:
            asset.name = self._read_string_at(self.string_table, asset.header.name_offset)

    def __str__(self):
        if not self.parsed or self.header is None:
            return "MKO (not parsed)"
        h = self.header
        lines = [
            f"MKO File",
            f"  Endian: {'LE' if h.endian_flag == 1 else 'BE'}",
            f"  Glue Hash: 0x{h.glue_hash:08X}",
            f"  Functions: {h.num_functions}",
            f"  Static Variables: {h.num_static_variables}",
            f"  Dynamic Variables: {h.num_dynamic_variables}",
            f"  Externs: {h.num_externs}",
            f"  Extern Variables: {h.num_extern_variables}",
            f"  Assets: {h.num_assets}",
            f"  Bytecode: {h.bytecode_data_len} bytes",
            f"  String Table: {h.string_argument_table_len} bytes",
            f"  Stack Data: {h.stack_data_len} bytes",
            f"  Global Fixups: {h.global_fixup_list_len}",
            f"  Tweakvars: {h.num_tweakvars}",
            f"  Source Files: {h.num_source_files}",
        ]
        return "\n".join(lines)
