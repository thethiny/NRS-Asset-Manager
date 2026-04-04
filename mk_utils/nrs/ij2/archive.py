"""
IJ2 Archive (.xxx) parser and Midway format converter.

IJ2 .xxx file structure:
1. IJ2AssetHeader (100 bytes)
2. packages_count (u32)
3. IJ2PackageEntry[packages_count] (24 bytes each, flat array)
4. 0x18 bytes padding (zeros)
5. filename_length (u32) + filename (null-terminated)
6. Compressed blocks (Oodle)
"""

from ctypes import c_char, c_uint32
from logging import getLogger
import logging
import os

from mk_utils.nrs.ij2.ue3_common import (
    IJ2Archive, IJ2AssetHeader, IJ2PackageEntry,
    IJ2ExportTableEntry, IJ2ImportTableEntry, IJ2TableMeta,
)
from mk_utils.nrs.compression.oodle import Oodle
from mk_utils.utils.structs import Struct

from pathlib import Path


class IJ2UE3Asset(IJ2Archive):
    """Parser for IJ2 .xxx compressed archive files."""

    def __init__(self, path: str, extra_path: str = "", oodle_dll: str = ""):
        super().__init__(path, extra_path)
        self.oodle_dll = oodle_dll

    def parse_header(self):
        header = IJ2AssetHeader.read(self.mm)
        return header

    def parse(self, skip_bulk: bool = False):
        self.header = self.parse_header()
        self.compression_mode = self.header.compression_flag
        self.compressor = Oodle(self.oodle_dll)

        # IJ2 has a flat package array (no named packages)
        self.packages_count = Struct.read_buffer(self.mm, c_uint32)
        self.package_entries = list(self._parse_package_entries(self.packages_count))

        # No extra packages in IJ2
        self.packages_extra = []

        # Skip padding
        self.skip(0x18)

        # Filename
        self.file_name = self.parse_file_name()

        # IJ2 has NO PSF/bulk file tables between filename and blocks
        self.psf_tables = []
        self.bulk_tables = []

        self.parsed = True

    def _parse_package_entries(self, count):
        for _ in range(count):
            yield IJ2PackageEntry.read(self.mm)

    def deserialize_block(self):
        return super().deserialize_block(self.mm, self.compressor)

    def to_midway(self, skip_bulk: bool = False):
        buffer = self._IJ2MidwayBuilder.from_ij2(self, skip_bulk)
        return IJ2MidwayAsset(buffer, self.psf_source)

    class _IJ2MidwayBuilder:
        @classmethod
        def from_ij2(cls, ij2: "IJ2UE3Asset", skip_bulk: bool = False):
            if not ij2.parsed:
                logging.getLogger("IJ2Archive").warning("IJ2 Asset was not parsed. Parsing first.")
                ij2.parse(skip_bulk=skip_bulk)

            buffer = bytearray()

            # Build header with compression reset to 0
            buffer += cls._build_header(ij2.header)

            # IJ2 midway format: packages_count only (no extra count, no file tables)
            buffer += (0).to_bytes(4, "little")  # packages_count

            # Padding
            buffer += b"\x00" * 0x18

            # Filename
            buffer += cls._build_filename_section(ij2.file_name)

            # Decompress all blocks and place at correct offsets
            for entry in ij2.package_entries:
                ij2.mm.seek(entry.compressed_offset)
                data = ij2.deserialize_block()
                if len(data) != entry.decompressed_size:
                    getLogger("IJ2Archive").warning(
                        f"Decompressed size mismatch: got {len(data)}, expected {entry.decompressed_size}"
                    )
                cls._place_data(buffer, entry.decompressed_offset, data)

            return buffer

        @classmethod
        def _build_header(cls, header: IJ2AssetHeader) -> bytes:
            # Serialize header but set compression_flag to 0
            base = header.serialize()[:-4]  # Everything except compression_flag
            return base + (0).to_bytes(4, "little")

        @classmethod
        def _build_filename_section(cls, file_name: str) -> bytes:
            return (len(file_name) + 1).to_bytes(4, "little") + file_name.encode("ascii") + b"\x00"

        @classmethod
        def _place_data(cls, buffer: bytearray, offset: int, data: bytes):
            end = offset + len(data)
            buf_len = len(buffer)

            if offset > buf_len:
                buffer += b"\x00" * (offset - buf_len)
            elif offset < buf_len:
                if not any(buffer[offset:end]):
                    pass  # Zero-filled area, OK to overwrite
                else:
                    raise ValueError(f"Data already exists at offset 0x{offset:X}!")

            buffer[offset:end] = data

    def dump(self, save_path: str):
        save_path = os.path.join(save_path, self.file_name)
        os.makedirs(save_path, exist_ok=True)

        # Dump individual package blocks
        pkg_dir = os.path.join(save_path, "packages")
        os.makedirs(pkg_dir, exist_ok=True)

        for i, entry in enumerate(self.package_entries):
            self.mm.seek(entry.compressed_offset)
            data = self.deserialize_block()
            with open(os.path.join(pkg_dir, f"block_{i}.bin"), "wb") as f:
                f.write(data)

    def parse_all(self, save_path: str = "", skip_bulk: bool = False):
        self.parse(skip_bulk=skip_bulk)

        if save_path:
            self.dump(save_path)

        midway_file = self.to_midway(skip_bulk=skip_bulk)

        if save_path:
            midway_file.to_file(save_path, self.file_name)

        midway_file.parse(resolve=True, skip_bulk=skip_bulk)
        logging.getLogger("Main").debug("%r", midway_file)

        if save_path:
            midway_file.dump(save_path, "both")

        return midway_file


class IJ2MidwayAsset(IJ2Archive):
    """Parser for IJ2 decompressed Midway format files."""

    def close(self):
        self.mm.close()
        if getattr(self, "owns_file", False) and self.file:
            self.file.close()

    def to_file(self, folder, file_name):
        if not file_name:
            raise ValueError("Please provide a file name without extension")
        path = Path(folder, file_name)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / f"{file_name}.upk", "wb") as f:
            f.write(self.mm[:])

    def get_psf_reader(self):
        return None  # IJ2 doesn't use PSF

    def parse(self, resolve: bool = True, skip_bulk: bool = False):
        self.parse_summary()
        self.file_name = self.parse_file_name()

        # IJ2 has NO PSF/bulk file tables in midway format
        self.psf_tables = []
        self.bulk_tables = []
        self.psf_map = {}
        self.bulk_map = {}

        self.meta_size = self.mm.tell()

        if self.meta_size != self.header.name_table.offset:
            getLogger("IJ2Midway").warning(
                f"Header size mismatch: {self.meta_size} vs expected {self.header.name_table.offset}. "
                f"Seeking to name table offset."
            )
            self.mm.seek(self.header.name_table.offset)

        self.name_table = list(self.parse_name_table())

        if self.mm.tell() != self.header.import_table.offset:
            getLogger("IJ2Midway").warning(
                f"Position expected to reach Import Table but {self.header.import_table.offset - self.mm.tell()} bytes remain!"
            )

        self.import_table = list(self.parse_uobject_table(self.header.import_table, IJ2ImportTableEntry))

        if self.mm.tell() != self.header.export_table.offset:
            getLogger("IJ2Midway").warning(
                f"Position expected to reach Export Table but {self.header.export_table.offset - self.mm.tell()} bytes remain!"
            )

        self.export_table = list(self.parse_uobject_table(self.header.export_table, IJ2ExportTableEntry))

        if self.mm.tell() != self.header.exports_location:
            getLogger("IJ2Midway").warning(
                f"Position expected to reach Exports but {self.header.exports_location - self.mm.tell()} bytes remain!"
            )

        if resolve:
            self.resolve_table_info(self.import_table)
            self.resolve_table_info(self.export_table)
            self.print_resolves(self.import_table)
            self.print_resolves(self.export_table)

        self.parsed = True

    def parse_summary(self):
        self.header = IJ2AssetHeader.read(self.mm)
        self.compression_mode = self.header.compression_flag

        # IJ2 midway format: only one packages count (no extra)
        self.packages_count = Struct.read_buffer(self.mm, c_uint32)
        self.packages_extra_count = 0
        self.skip(0x18)
        self.summary_size = self.mm.tell()
        self.validate_file()

    def validate_file(self):
        if self.header.magic != 0x9E2A83C1:
            getLogger("IJ2Midway").error("File Magic Failed!")
            return False

        if self.header.midway_team_four_cc != b"DCF2":
            getLogger("IJ2Midway").error(
                f"Midway Four CC Failed! Expected 'DCF2', got '{self.header.midway_team_four_cc}'"
            )
            return False

        if self.header.main_package != b"DDEV":
            getLogger("IJ2Midway").error(
                f"Package Type is not supported: {self.header.main_package}"
            )
            return False

        return True

    def parse_name_table(self):
        self.mm.seek(self.header.name_table.offset)
        for i in range(self.header.name_table.entries):
            name_length = self.read_buffer(c_uint32)
            name = self.read_buffer(c_char * name_length)
            yield name.decode('ascii')

    def parse_uobject_table(self, table: IJ2TableMeta, type_):
        self.mm.seek(table.offset)
        for i in range(table.entries):
            entry = Struct.read_buffer(self.mm, type_)
            yield entry

    def resolve_table_info(self, table):
        for entry in table:
            entry.resolve(self.name_table, self.import_table, self.export_table)

    def print_resolves(self, table):
        for entry in table:
            logging.getLogger("Common").debug(f"Resolved {entry.__class__.__name__}: {entry.full_name}")

    def read_export(self, export: IJ2ExportTableEntry):
        self.mm.seek(export.object_offset, 0)
        data = self.mm.read(export.object_size)
        return data

    def validate_exports(self, skip_bulk=False):
        if not self.export_table:
            return []
        start = self.header.exports_location
        end = self.mm.size()
        errors = []
        exports = sorted(
            (e.object_offset, e.object_size, e.full_name) for e in self.export_table
        )
        prev_end = start
        for off, sz, name in exports:
            if not (start <= off < end):
                errors.append(f"{name}: Offset 0x{off:X} out of bounds")
                continue
            if off + sz > end:
                errors.append(f"{name}: Size exceeds file end")
                continue
            if off < prev_end:
                errors.append(f"{name}: Overlap detected")
            elif off > prev_end:
                errors.append(f"Gap before {name}: [0x{prev_end:X}-0x{off:X})")
            prev_end = max(prev_end, off + sz)
        return errors

    def validate_bulks(self):
        return []

    def validate_psfs(self):
        return []

    def dump(self, save_dir, format):
        if not save_dir:
            raise ValueError("save_dir was invalid!")

        logging.getLogger("Main").info(f"Saving {self.file_name}'s data to {save_dir}")

        if format != True:
            self.dump_tables(save_dir)
        if format != False:
            self.dump_tables(save_dir, formatted=True)

        self.dump_exports(save_dir)

    def dump_exports(self, save_dir="extracted"):
        output_dir = os.path.join(save_dir, self.file_name, "exports")
        for export in self.export_table:
            write_path = os.path.join(output_dir, export.file_dir.lstrip("/"))
            os.makedirs(write_path, exist_ok=True)
            data = self.read_export(export)
            file_out = os.path.join(write_path, export.file_name)
            logging.getLogger("IJ2Midway").debug(f"Saving export {export.full_name} to {file_out}")
            with open(file_out, "wb") as f:
                f.write(data)

    def dump_tables(self, location, formatted=False):
        self.dump_names(location)
        self.dump_table(location, self.import_table, formatted)
        self.dump_table(location, self.export_table, formatted)

    def dump_names(self, location):
        location = os.path.join(location, self.file_name)
        os.makedirs(location, exist_ok=True)
        file_out = os.path.join(location, "nametable.txt")
        with open(file_out, "w+", encoding="utf-8") as f:
            for i, name in enumerate(self.name_table):
                f.write(f"{hex(i)[2:].upper()}:\t{name}\n")

    def dump_table(self, location, table, formatted=False):
        if not table:
            return
        location = os.path.join(location, self.file_name)
        os.makedirs(location, exist_ok=True)

        if isinstance(table[0], IJ2ExportTableEntry):
            file = "exporttable"
        elif isinstance(table[0], IJ2ImportTableEntry):
            file = "importtable"
        else:
            raise TypeError(f"Invalid type: {type(table[0])}")

        func = str if formatted else repr
        if formatted:
            file += ".parsed"

        file_out = os.path.join(location, f"{file}.txt")
        with open(file_out, "w+", encoding="utf-8") as f:
            for i, entry in enumerate(table):
                f.write(f"{hex(i)[2:].upper()}:\t{func(entry)}\n")

    def parse_and_save_export(self, export, handler_class, save_dir, overwrite=False):
        if not overwrite:
            out_file = handler_class.make_save_path(export, self.file_name, save_dir)
            if os.path.isfile(out_file):
                logging.getLogger("IJ2Midway").info(f"Skipping {export.file_name}...")
                return out_file

        export_data = self.read_export(export)
        handler_obj = handler_class(export_data, self.name_table)
        parsed = handler_obj.parse()
        saved_file = handler_obj.save(parsed, export, self.file_name, save_dir, self)
        return saved_file

    def __str__(self):
        strings = [
            f"IJ2 Midway Asset File: {self.file_name}",
            f"Compression Mode: {self.header.compression_flag}",
            f"{self.packages_count} Packages | {self.packages_extra_count} Extra Packages",
            f"{len(self.name_table)} Names",
            f"{len(self.import_table)} Imports",
            f"{len(self.export_table)} Exports",
        ]
        return '\n'.join(strings)
