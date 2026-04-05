from ctypes import c_char, c_uint32
from logging import getLogger
import logging
import os
from pathlib import Path

from mk_utils.nrs.ij2.enums import ECompressionFlags, EPackageFlags
from mk_utils.nrs.ij2.ue3_common import (
    IJ2Archive, IJ2AssetHeader, IJ2ExportTableEntry, IJ2ImportTableEntry, IJ2TableMeta,
)
from mk_utils.nrs.ue3_common import ClassHandler
from mk_utils.utils.filereader import FileReader
from mk_utils.utils.structs import Struct


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

    def get_tfc_reader(self):
        """Get a FileReader for the TFC file, if available.

        psf_source can be:
        - A directory: look for <file_name>.tfc in that directory
        - A file path: use it directly
        - Empty: no TFC available
        """
        if not self.psf_source:
            return None
        if isinstance(self.psf_source, str) and os.path.isdir(self.psf_source):
            tfc_path = os.path.join(self.psf_source, self.file_name + ".tfc")
            if os.path.isfile(tfc_path):
                return FileReader(tfc_path)
            return None
        if isinstance(self.psf_source, str) and os.path.isfile(self.psf_source):
            return FileReader(self.psf_source)
        return None

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

        if self.mm.tell() != self.header.total_header_size:
            getLogger("IJ2Midway").warning(
                f"Position expected to reach Exports but {self.header.total_header_size - self.mm.tell()} bytes remain!"
            )

        if resolve:
            self.resolve_table_info(self.import_table)
            self.resolve_table_info(self.export_table)
            self.print_resolves(self.import_table)
            self.print_resolves(self.export_table)

        # Initialize TFC reader for texture extraction
        if not skip_bulk:
            self.tfc_reader = self.get_tfc_reader()
            if self.tfc_reader:
                getLogger("IJ2Midway").info(f"TFC reader initialized for {self.file_name}")

        self.parsed = True

    def parse_summary(self):
        self.header = IJ2AssetHeader.read(self.mm)
        self.compression_mode = ECompressionFlags(self.header.compression_flag)

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

        if self.header.branch_version != b"DDEV":
            getLogger("IJ2Midway").error(
                f"Package Type is not supported: {self.header.branch_version}"
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
        start = self.header.total_header_size
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

    @staticmethod
    def _decode_package_flags(flags: int) -> str:
        names = [f.name for f in EPackageFlags if flags & f.value]
        return " | ".join(names) if names else "None"

    def __str__(self):
        strings = [
            f"IJ2 Midway Asset File: {self.file_name}",
            f"Compression Mode: {ECompressionFlags(self.header.compression_flag).name}",
            f"Package Flags: {self._decode_package_flags(self.header.package_flags)}",
            f"{self.packages_count} Packages | {self.packages_extra_count} Extra Packages",
            f"{len(self.name_table)} Names",
            f"{len(self.import_table)} Imports",
            f"{len(self.export_table)} Exports",
        ]
        return '\n'.join(strings)
