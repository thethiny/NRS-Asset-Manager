"""
TODO: Game-specific UE3 common structures.

Each struct must match the binary layout EXACTLY. Use a hex editor or dumped SDK
to verify field order, sizes, and types. Struct field order IS the serialization
order — no manual seeking or byte swapping.

Reference:
- IJ2: mk_utils/nrs/ij2/ue3_common.py (verified via reverse engineering)
- MK11: mk_utils/nrs/mk11/ue3_common.py
"""

from ctypes import c_byte, c_char, c_int32, c_uint32, c_uint16, c_uint64
from typing import Any, Union

from mk_utils.nrs.compression.base import CompressionBase
# TODO: Import the correct Oodle version for this game
# from mk_utils.nrs.compression.oodle import OodleV4  # IJ2
# from mk_utils.nrs.compression.oodle import OodleV5  # MK11
from mk_utils.nrs.GAME.enums import ECompressionFlags  # TODO: rename GAME
from mk_utils.nrs.ue3_common import GUID, UETableEntryBase
from mk_utils.utils.filereader import FileReader
from mk_utils.utils.structs import Struct, hex_s


# ── Block Headers (Oodle compression framing) ────────────────────────────────
# These are typically identical across all NRS games.

class BlockHeader(Struct):
    __slots__ = ()
    _fields_ = [
        ("magic", c_uint32),
        ("padding", c_uint32),
        ("chunk_size", c_uint64),
        ("compressed_size", c_uint64),
        ("decompressed_size", c_uint64),
    ]


class BlockChunkHeader(Struct):
    __slots__ = ()
    _fields_ = [
        ("compressed_size", c_uint64),
        ("decompressed_size", c_uint64),
    ]


# ── Table Meta (entries count + offset) ──────────────────────────────────────

class TableMeta(Struct):
    _fields_ = [
        ("entries", c_uint32),
        ("offset", c_uint64),
    ]


# ── Asset Header (FPackageFileSummary) ───────────────────────────────────────
# TODO: This is the MOST IMPORTANT struct. Get it right by comparing with hex dumps.
# The field order varies between games. Use a dumped SDK or reverse engineering if available.

class AssetHeader(Struct):
    """TODO: Game file header.

    Compare hex dump at offset 0x00 with known games to determine field order.
    Common pattern: Tag, FileVersion, TotalHeaderSize, FourCC, ...
    """
    _fields_ = [
        ("magic", c_uint32),                      # 0x00 Tag = 0x9E2A83C1
        ("file_version", c_uint16),                # 0x04
        ("licensee_version", c_uint16),            # 0x06
        ("total_header_size", c_uint32),           # 0x08
        # TODO: Remaining fields depend on game version.
        # Use the game's FPackageFileSummary::operator<< (from dumped SDK or RE) to determine order.
        # Key fields to find: FourCC, tables (name/export/import), GUID, compression_flag
        ("compression_flag", c_uint32),            # Last field before compressed chunks
    ]


# ── FCompressedChunk ─────────────────────────────────────────────────────────
# TODO: Verify field sizes (u32 vs u64) from dumped SDK or hex comparison.

class CompressedChunk(Struct):
    __slots__ = ()
    _fields_ = [
        ("uncompressed_offset", c_uint64),
        ("uncompressed_size", c_uint32),    # Could be u64 in some games
        ("compressed_offset", c_uint64),
        ("compressed_size", c_uint32),      # Could be u64 in some games
    ]


# ── Base Archive ─────────────────────────────────────────────────────────────

class GameArchive(FileReader):
    """Base archive reader. Provides block decompression and file name parsing."""

    def __init__(self, source: Any, extra_source: Any = ""):
        super().__init__(source)
        self.psf_source = extra_source
        self.parsed = False

    def read_buffer(self, size):
        return Struct.read_buffer(self.mm, size)

    def parse_file_name(self) -> str:
        file_name_length = Struct.read_buffer(self.mm, c_uint32)
        file_name = Struct.read_buffer(
            self.mm, c_char * file_name_length
        ).decode()
        return file_name

    @classmethod
    def deserialize_block(cls, mm, compression):
        block = BlockHeader.read(mm)
        decompressed_data = cls.decompress_block(block, compression, mm)
        return decompressed_data

    @classmethod
    def decompress_block(cls, block, compression, mm):
        data = b""
        if isinstance(compression, CompressionBase):
            compressor = compression
        else:
            compressor = cls.get_compressor(compression)
        for chunk_header, chunk_data in cls.parse_blocks_chunk(block, mm):
            decompressed_chunk = compressor.decompress(
                chunk_data, chunk_header.decompressed_size
            )
            data += decompressed_chunk
        return data

    @classmethod
    def get_compressor(cls, compression):
        """TODO: Return the correct Oodle instance for this game's compression flag."""
        if isinstance(compression, int):
            compression = ECompressionFlags(compression)
        # TODO: Uncomment the correct version:
        # return OodleV4()  # IJ2
        # return OodleV5()  # MK11
        raise NotImplementedError(f"Implement get_compressor for this game")

    @classmethod
    def parse_blocks_chunk(cls, block, mm):
        total_read = 0
        chunk_headers = []
        while total_read < block.compressed_size:
            chunk_header = BlockChunkHeader.read(mm)
            chunk_headers.append(chunk_header)
            total_read += chunk_header.compressed_size

        for chunk_header in chunk_headers:
            chunk_data = Struct.read_buffer(
                mm, c_byte * chunk_header.compressed_size
            )
            yield chunk_header, chunk_data


# ── Table Entry Base ─────────────────────────────────────────────────────────

class GameTableEntry(Struct):
    """Base class for import/export table entries."""

    @classmethod
    def resolve_object(cls, value, import_table, export_table):
        if value == 0:
            return NoneTableEntry()
        if value < 0:
            value = -(value + 1)
            return import_table[value]
        if value > 0:
            value -= 1
            return export_table[value]
        raise ValueError(f"Impossible Situation")

    def __init__(self, *args: Any, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.name: str = ""
        self.resolved = False

    def __new__(cls):
        obj = super().__new__(cls)
        setattr(obj, "name", "")
        return obj


class NoneTableEntry(GameTableEntry):
    def __bool__(self):
        return False

    def __init__(self, *args: Any, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.name = "None"
        self.resolved = True


# ── Export Table Entry (FObjectExport) ───────────────────────────────────────
# TODO: This is the second most important struct. Field order varies between games.
# Verify with the game's operator<<(FArchive*, FObjectExport*) from dumped SDK or RE.

class ExportTableEntry(GameTableEntry, UETableEntryBase):
    """TODO: FObjectExport for this game.

    MUST verify:
    - Field order (class, super, outer, name — order varies!)
    - FName format (u32+u32 or i32+u32)
    - Which fields exist (ComponentMap? ExportFlags? unk_3?)
    - Total size per entry
    """
    _fields_ = [
        # TODO: Fill in from dumped SDK or hex comparison
        ("class_index", c_int32),
        ("super_index", c_int32),
        ("outer_index", c_int32),
        ("object_name", c_uint32),
        ("object_name_suffix", c_uint32),
        # TODO: Add remaining fields
        ("serial_size", c_uint32),
        ("serial_offset", c_uint64),
    ]

    @property
    def object_size(self):
        return self.serial_size

    @property
    def object_offset(self):
        return self.serial_offset

    @property
    def file_name(self):
        name = self.name
        if self.suffix:
            name += f".{self.suffix}"
        if self.class_:
            name += f".{self.class_.name}"
        return name

    @property
    def file_dir(self):
        return f"/{self.package}/{self.path}" if hasattr(self, "package") else f"/{self.path}"

    @property
    def full_name(self):
        return self.file_dir + self.file_name

    @property
    def path(self):
        path = []
        super_ = self.class_outer
        while super_:
            path.append(super_.name)
            if isinstance(super_, type(self)):
                super_ = super_.class_outer
            else:
                super_ = super_.package
        if not path:
            return ''
        return "/".join(path[::-1]) + '/'

    def __str__(self):
        string = f"{self.serial_offset:0>8X} ({self.serial_size:0>8X}) "
        string += self.path + self.file_name
        return string

    def __repr__(self) -> str:
        return (
            f"offset={hex_s(self.serial_offset)} "
            f"size=({hex_s(self.serial_size)}) "
            f"class={hex_s(self.class_index)} "
            f"name={hex_s(self.object_name)}: {self.name}"
        )

    def resolve(self, name_table, import_table, export_table):
        """TODO: Resolve all resolve_object fields and name indices."""
        object_class = self.resolve_object(self.class_index, import_table, export_table)
        object_super = self.resolve_object(self.super_index, import_table, export_table)
        object_outer = self.resolve_object(self.outer_index, import_table, export_table)
        name = name_table[self.object_name]

        self.class_ = object_class
        self.class_super = object_super
        self.class_outer = object_outer
        self.name = name
        self.suffix = self.object_name_suffix
        self.package = ""

        self.resolved = True


# ── Import Table Entry (FObjectImport) ───────────────────────────────────────
# TODO: Verify with the game's operator<<(FArchive*, FObjectImport*) from dumped SDK or RE.

class ImportTableEntry(GameTableEntry, UETableEntryBase):
    """TODO: FObjectImport for this game.

    MUST verify:
    - Whether fields use FName (u32+u32), resolve_object (i32), or name index (i32)
    - Total size per entry (IJ2=28, MK11=20)
    """
    _fields_ = [
        # TODO: Fill in from dumped SDK or hex comparison
        ("class_package_name", c_uint32),
        ("class_package_suffix", c_uint32),
        ("class_name", c_uint32),
        ("class_name_suffix", c_uint32),
        ("outer_index", c_int32),
        ("object_name", c_uint32),
        ("object_name_suffix", c_uint32),
    ]

    @property
    def full_name(self):
        name = self.path + self.name
        if self.suffix:
            name += f".{self.suffix}"
        return name

    @property
    def path(self):
        path = []
        super_ = self.package
        while super_:
            path.append(super_.name)
            if isinstance(super_, type(self)):
                super_ = super_.package
            else:
                super_ = super_.class_outer
        if not path:
            return '/'
        return '/' + '/'.join(path[::-1]) + '/'

    def __str__(self):
        return self.path + self.name

    def __repr__(self) -> str:
        return (
            f"class_pkg={hex_s(self.class_package_name)} "
            f"outer={hex_s(self.outer_index)} "
            f"{hex_s(self.object_name)}: {self.name}"
        )

    def resolve(self, name_table, import_table, export_table):
        """TODO: Resolve fields. Check whether each field is a name index or resolve_object."""
        self.class_package_resolved = name_table[self.class_package_name]
        self.class_name_resolved = name_table[self.class_name]
        self.name = name_table[self.object_name]
        self.suffix = self.object_name_suffix
        self.package = self.resolve_object(self.outer_index, import_table, export_table)

        self.resolved = True
