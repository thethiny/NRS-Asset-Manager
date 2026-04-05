"""
IJ2-specific UE3 common structures.

Field names and layout verified against IJ2 PDB (IDA decompilation).

Key differences from MK11:
- Header is 100 bytes (vs 104): ShaderVersion/BranchVersion after GUID, no extra before FourCC
- FObjectExport: ClassIndex, SuperIndex, OuterIndex, ObjectName(FName), ArchetypeIndex,
  ReferencedObjects, ObjectFlags, ObjectGuid, SerialSize, SerialOffset, ComponentMap, ExportFlags
  (variable size due to ComponentMap; typically 72 bytes when ComponentMap is empty)
- FObjectImport: ClassPackage(FName), ClassName(FName), OuterIndex(i32), ObjectName(FName)
  = 28 bytes (three FNames + one i32)
- FCompressedChunk: UncompressedOffset(u64), UncompressedSize(u32), CompressedOffset(u64),
  CompressedSize(u32) = 24 bytes
"""

from ctypes import c_byte, c_char, c_int32, c_uint32, c_uint16, c_uint64
from typing import Any, Union

from mk_utils.nrs.compression.base import CompressionBase
from mk_utils.nrs.compression.oodle import OodleV4
from mk_utils.nrs.ij2.enums import ECompressionFlags
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


# ── Asset Header (FPackageFileSummary) ───────────────────────────────────────

class IJ2AssetHeader(Struct):
    """IJ2 file header - 100 bytes (0x64).

    Serialization order from PDB FPackageFileSummary::operator<< for FileVersion=0x2DC:
    Tag, FileVersion, TotalHeaderSize, MidwayTeamFourCC, MidwayTeamVersion,
    ShaderVersion (>=0x29C), BranchVersion (>=0x2C2), PackageFlags,
    NameCount+NameOffset, ExportCount+ExportOffset, ImportCount+ImportOffset,
    GameThreadExportCount, Guid, EngineVersion, CookedContentVersion, CompressionFlags
    """
    _fields_ = [
        ("magic", c_uint32),                      # 0x00 Tag
        ("file_version", c_uint16),                # 0x04 FileVersion (lo)
        ("licensee_version", c_uint16),            # 0x06 FileVersion (hi)
        ("total_header_size", c_uint32),            # 0x08 TotalHeaderSize (exports_location)
        ("midway_team_four_cc", c_char * 4),       # 0x0C MidwayTeamFourCC = "DCF2"
        ("midway_team_version", c_uint32),         # 0x10 MidwayTeamVersion
        ("shader_version", c_uint32),              # 0x14 ShaderVersion
        ("branch_version", c_char * 4),            # 0x18 BranchVersion = "DDEV" (package type FourCC)
        ("package_flags", c_uint32),               # 0x1C PackageFlags
        ("name_table", IJ2TableMeta),              # 0x24 NameCount + NameOffset
        ("export_table", IJ2TableMeta),            # 0x30 ExportCount + ExportOffset
        ("import_table", IJ2TableMeta),            # 0x3C ImportCount + ImportOffset
        ("game_thread_export_count", c_uint32),    # 0x48 GameThreadExportCount
        ("guid", GUID),                           # 0x4C Guid
        ("engine_version", c_uint32),              # 0x5C EngineVersion
        ("cooked_content_version", c_uint32),      # 0x60 CookedContentVersion (only on load)
        ("compression_flag", c_uint32),            # 0x64 CompressionFlags
    ]


# ── FCompressedChunk ─────────────────────────────────────────────────────────

class IJ2CompressedChunk(Struct):
    """FCompressedChunk - 24 bytes.

    PDB serialization: UncompressedOffset(8), UncompressedSize(4),
    CompressedOffset(8), CompressedSize(4).
    """
    __slots__ = ()
    _fields_ = [
        ("uncompressed_offset", c_uint64),  # 0x00
        ("uncompressed_size", c_uint32),    # 0x08
        ("compressed_offset", c_uint64),    # 0x0C
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
    def decompress_block(cls, block: IJ2BlockHeader, compression: Union[int, ECompressionFlags, CompressionBase], mm):
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
    def get_compressor(cls, compression: Union[int, ECompressionFlags]):
        if isinstance(compression, int):
            compression = ECompressionFlags(compression)
        if compression >= ECompressionFlags.OODLE:
            return OodleV4()
        else:
            raise NotImplementedError(f"Only Oodle Compression is supported")

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


# ── Export Table Entry (FObjectExport) ───────────────────────────────────────

class IJ2ExportTableEntry(IJ2TableEntry, UETableEntryBase):
    """FObjectExport - 72+ bytes (variable due to ComponentMap).

    PDB serialization order:
    ClassIndex(4), SuperIndex(4), OuterIndex(4), ObjectName(FName=4+4),
    ArchetypeIndex(4), ReferencedObjects(4), ObjectFlags(8), ObjectGuid(16),
    SerialSize(4), SerialOffset(8), ComponentMap(TMap, variable), ExportFlags(4)

    When ComponentMap is empty (count=0), total = 4+4+4+8+4+4+8+16+4+8+4+4 = 72 bytes.
    """
    _fields_ = [
        ("class_index", c_int32),          # ClassIndex: resolve_object
        ("super_index", c_int32),          # SuperIndex: resolve_object
        ("outer_index", c_int32),          # OuterIndex: resolve_object
        ("object_name", c_uint32),         # ObjectName.Index (FName part 1)
        ("object_name_suffix", c_uint32),  # ObjectName.Number (FName part 2)
        ("archetype_index", c_int32),      # ArchetypeIndex: resolve_object
        ("referenced_objects", c_int32),   # ReferencedObjects count
        ("object_flags", c_uint64),        # ObjectFlags
        ("object_guid", GUID),             # ObjectGuid (16 bytes)
        ("serial_size", c_uint32),         # SerialSize (object data size)
        ("serial_offset", c_uint64),       # SerialOffset (object data offset)
        ("component_map_count", c_uint32), # ComponentMap entry count (TMap serialization)
        ("export_flags", c_uint32),        # ExportFlags
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
        string += f"{self.serial_offset:0>8X} ({self.serial_size:0>8X}) "
        string += self.path
        string += self.file_name
        if self.class_super:
            string += f' : {self.class_super.name}'
        return string

    def __repr__(self) -> str:
        return (
            f"offset={hex_s(self.serial_offset)} "
            f"size=({hex_s(self.serial_size)}) "
            f"outer={hex_s(self.outer_index)} "
            f"class={hex_s(self.class_index)} "
            f"super={hex_s(self.super_index)} "
            f"archetype={hex_s(self.archetype_index)} "
            f"name={hex_s(self.object_name)}: {self.name}"
        )

    def resolve(self, name_table: list, import_table: list, export_table: list):
        object_class = self.resolve_object(self.class_index, import_table, export_table)
        object_super = self.resolve_object(self.super_index, import_table, export_table)
        object_outer = self.resolve_object(self.outer_index, import_table, export_table)
        name = name_table[self.object_name]

        self.class_ = object_class
        self.class_super = object_super
        self.class_outer = object_outer
        self.name = name
        self.suffix = self.object_name_suffix
        self.package = ""  # IJ2 doesn't use a separate package name index

        self.resolved = True


# ── Import Table Entry (FObjectImport) ───────────────────────────────────────

class IJ2ImportTableEntry(IJ2TableEntry, UETableEntryBase):
    """FObjectImport - 28 bytes.

    PDB serialization order:
    ClassPackage(FName=4+4), ClassName(FName=4+4), OuterIndex(4), ObjectName(FName=4+4)
    """
    _fields_ = [
        ("class_package_name", c_uint32),    # ClassPackage.Index (FName part 1)
        ("class_package_suffix", c_uint32),  # ClassPackage.Number (FName part 2)
        ("class_name", c_uint32),            # ClassName.Index (FName part 1)
        ("class_name_suffix", c_uint32),     # ClassName.Number (FName part 2)
        ("outer_index", c_int32),            # OuterIndex: resolve_object
        ("object_name", c_uint32),           # ObjectName.Index (FName part 1)
        ("object_name_suffix", c_uint32),    # ObjectName.Number (FName part 2)
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
        if self.class_name_resolved:
            string += f" : {self.class_name_resolved}"
        return string

    def __repr__(self) -> str:
        return (
            f"class_pkg={hex_s(self.class_package_name)} "
            f"class={hex_s(self.class_name)} "
            f"outer={hex_s(self.outer_index)} "
            f"{hex_s(self.object_name)}: {self.name}"
        )

    def resolve(self, name_table: list, import_table: list, export_table: list):
        self.class_package_resolved = name_table[self.class_package_name]
        self.class_name_resolved = name_table[self.class_name]
        self.name = name_table[self.object_name]
        self.suffix = self.object_name_suffix
        self.package = self.resolve_object(self.outer_index, import_table, export_table)

        self.resolved = True
