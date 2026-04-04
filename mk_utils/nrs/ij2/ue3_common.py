"""
IJ2-specific UE3 common structures.

Key differences from MK11:
- Header is 100 bytes (vs 104): no shader/engine ver before four_cc, bulk_offset is u32
- Import entries are 28 bytes (vs 20): class_package as u64, extra field
- Export entries are 72 bytes (vs 76): name/suffix swapped, no unk_3
- Package entries are flat 24-byte arrays (no named sub-packages)
"""

import logging

from ctypes import c_byte, c_char, c_int32, c_uint32, c_uint16, c_uint64
from typing import Any, Union

from mk_utils.nrs.compression.base import CompressionBase
from mk_utils.nrs.ue3_common import GUID, UETableEntryBase
from mk_utils.utils.filereader import FileReader
from mk_utils.utils.structs import Struct, hex_s


# ── Block Headers (Oodle compression framing) ────────────────────────────────

class IJ2BlockHeader(Struct):
    __slots__ = ()
    _fields_ = [
        ("magic", c_uint32),
        ("padding", c_uint32),
        ("chunk_size", c_uint64),
        ("compressed_size", c_uint64),
        ("decompressed_size", c_uint64),
    ]


class IJ2BlockChunkHeader(Struct):
    __slots__ = ()
    _fields_ = [
        ("compressed_size", c_uint64),
        ("decompressed_size", c_uint64),
    ]


# ── Table Meta (entries count + offset) ──────────────────────────────────────

class IJ2TableMeta(Struct):
    _fields_ = [
        ("entries", c_uint32),
        ("offset", c_uint64),
    ]


# ── Asset Header ─────────────────────────────────────────────────────────────

class IJ2AssetHeader(Struct):
    """IJ2 file header - 100 bytes (0x64).

    Compared to MK11:
    - No shader_version/engine_version before four_cc
    - bulk_data_offset is u32 instead of u64
    - shader_version/engine_version appear after GUID
    """
    _fields_ = [
        ("magic", c_uint32),                      # 0x00
        ("file_version", c_uint16),                # 0x04
        ("licensee_version", c_uint16),            # 0x06
        ("exports_location", c_uint32),            # 0x08
        ("midway_team_four_cc", c_char * 4),       # 0x0C = "DCF2"
        ("midway_team_engine_version", c_uint32),  # 0x10 = 80
        ("cook_version", c_uint32),                # 0x14 = 570
        ("main_package", c_char * 4),              # 0x18 = "DDEV"
        ("package_flags", c_uint32),               # 0x1C
        ("name_table", IJ2TableMeta),              # 0x20
        ("export_table", IJ2TableMeta),            # 0x2C
        ("import_table", IJ2TableMeta),            # 0x38
        ("bulk_data_offset", c_uint32),            # 0x44 (u32, not u64!)
        ("guid", GUID),                           # 0x48
        ("shader_version", c_uint32),              # 0x58
        ("engine_version", c_uint32),              # 0x5C
        ("compression_flag", c_uint32),            # 0x60
    ]


# ── Package Entry ────────────────────────────────────────────────────────────

class IJ2PackageEntry(Struct):
    """IJ2 package entry - 24 bytes (flat, no names).

    MK11 uses named packages (HeaderData, Package, Other) with sub-entries.
    IJ2 uses a flat array of entries.
    """
    __slots__ = ()
    _fields_ = [
        ("decompressed_offset", c_uint64),  # 0x00
        ("decompressed_size", c_uint32),    # 0x08
        ("compressed_offset", c_uint32),    # 0x0C
        ("unknown", c_uint32),              # 0x10 (always 0)
        ("compressed_size", c_uint32),      # 0x14
    ]


# ── Base Archive ─────────────────────────────────────────────────────────────

class IJ2Archive(FileReader):
    """Base archive reader for IJ2 files.

    Provides shared functionality: buffer reading, file name parsing,
    block decompression (Oodle framing).
    """

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
        block = IJ2BlockHeader.read(mm)
        decompressed_data = cls.decompress_block(block, compression, mm)
        return decompressed_data

    @classmethod
    def decompress_block(cls, block: IJ2BlockHeader, compression: Union[int, CompressionBase], mm):
        data = b""
        if isinstance(compression, CompressionBase):
            compressor = compression
        else:
            raise NotImplementedError(f"IJ2 requires a CompressionBase instance, got {type(compression)}")
        for chunk_header, chunk_data in cls.parse_blocks_chunk(block, mm):
            decompressed_chunk = compressor.decompress(
                chunk_data, chunk_header.decompressed_size
            )
            data += decompressed_chunk
        return data

    @classmethod
    def parse_blocks_chunk(cls, block: IJ2BlockHeader, mm):
        total_read = 0
        chunk_headers = []
        while total_read < block.compressed_size:
            chunk_header = IJ2BlockChunkHeader.read(mm)
            chunk_headers.append(chunk_header)
            total_read += chunk_header.compressed_size

        for chunk_header in chunk_headers:
            chunk_data = Struct.read_buffer(
                mm, c_byte * chunk_header.compressed_size
            )
            yield chunk_header, chunk_data


# ── Table Entry Base ─────────────────────────────────────────────────────────

class IJ2TableEntry(Struct):
    """Base class for IJ2 import/export table entries."""

    @classmethod
    def resolve_object(
        cls, value, import_table: list, export_table: list
    ) -> Union["IJ2NoneTableEntry", "IJ2ImportTableEntry", "IJ2ExportTableEntry"]:
        if value == 0:
            return IJ2NoneTableEntry()
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


class IJ2NoneTableEntry(IJ2TableEntry):
    def __bool__(self):
        return False

    def __init__(self, *args: Any, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.name = "None"
        self.resolved = True


# ── Export Table Entry ───────────────────────────────────────────────────────

class IJ2ExportTableEntry(IJ2TableEntry, UETableEntryBase):
    """IJ2 export table entry - 72 bytes.

    Key difference from MK11: name and suffix are SWAPPED,
    and unk_3 field is absent (72 vs 76 bytes).
    """
    _fields_ = [
        ("object_class", c_int32),
        ("object_outer_class", c_int32),
        ("object_name_suffix", c_uint32),   # Swapped with name vs MK11!
        ("object_name", c_int32),           # Swapped with suffix vs MK11!
        ("object_super", c_int32),
        ("object_flags", c_uint64),
        ("object_main_package", c_uint32),
        ("unk_1", c_uint32),
        ("object_guid", GUID),
        ("object_size", c_uint32),
        ("object_offset", c_uint64),
        ("unk_2", c_uint64),
    ]

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
        dir = f"/{self.package}/"
        dir += self.path
        return dir

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
        string = ""
        if self.package:
            string += f"[{self.package}] "
        string += f"{self.object_offset:0>8X} ({self.object_size:0>8X}) "
        string += self.path
        string += self.file_name
        if self.class_super:
            string += f' : {self.class_super.name}'
        return string

    def __repr__(self) -> str:
        return (
            f"offset={hex_s(self.object_offset)} "
            f"size=({hex_s(self.object_size)}) "
            f"package={hex_s(self.object_main_package)} "
            f"folder={hex_s(self.object_outer_class)} "
            f"class={hex_s(self.object_class)} "
            f"super={hex_s(self.object_super)} "
            f"name={hex_s(self.object_name)}: {self.name}"
        )

    def resolve(self, name_table: list, import_table: list, export_table: list):
        object_class = self.resolve_object(self.object_class, import_table, export_table)
        object_outer_class = self.resolve_object(self.object_outer_class, import_table, export_table)
        name = name_table[self.object_name]
        object_super = self.resolve_object(self.object_super, import_table, export_table)
        # IJ2 may not use object_main_package as a name index the same way as MK11
        try:
            package = name_table[self.object_main_package]
        except (IndexError, KeyError):
            package = ""

        self.class_ = object_class
        self.class_outer = object_outer_class
        self.name = name
        self.suffix = self.object_name_suffix
        self.class_super = object_super
        self.package = package

        self.resolved = True


# ── Import Table Entry ───────────────────────────────────────────────────────

class IJ2ImportTableEntry(IJ2TableEntry, UETableEntryBase):
    """IJ2 import table entry - 28 bytes.

    Different from MK11's 20-byte entries.
    Uses u64 for class_package (name index).
    """
    _fields_ = [
        ("import_class_package", c_uint64),   # Name index (not resolve_object)
        ("import_outer_class", c_int32),      # Name index for the class type
        ("import_name_suffix", c_int32),
        ("import_class_reference", c_int32),  # resolve_object -> parent import
        ("import_name", c_int32),             # Name index
        ("unk", c_int32),
    ]

    @property
    def full_name(self):
        name = self.path
        name += self.name
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
        string = ""
        string += self.path
        string += self.name
        if self.outer_class:
            string += f" : {self.outer_class.name}"
        return string

    def __repr__(self) -> str:
        return (
            f"class_pkg={hex_s(self.import_class_package)} "
            f"outer={hex_s(self.import_outer_class)} "
            f"ref={hex_s(self.import_class_reference)} "
            f"{hex_s(self.import_name)}: {self.name}"
        )

    def resolve(self, name_table: list, import_table: list, export_table: list):
        # import_class_package is a name index (e.g., "Core")
        self.class_package_name = name_table[self.import_class_package]
        # import_outer_class is a name index for the class (e.g., "Class", "Package")
        self.outer_class_name = name_table[self.import_outer_class]
        self.name = name_table[self.import_name]
        self.suffix = self.import_name_suffix
        self.package = self.resolve_object(self.import_class_reference, import_table, export_table)
        # Set outer_class as a string for display purposes
        self.outer_class = type('NameHolder', (), {'name': self.outer_class_name})()
        self.unknown = None

        self.resolved = True
