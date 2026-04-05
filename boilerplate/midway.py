"""
TODO: Game Midway Asset parser.

Copy this file to mk_utils/nrs/<game_code>/midway.py and implement.
"""

from ctypes import c_char, c_uint32
from logging import getLogger
import logging
import os
from pathlib import Path

from mk_utils.nrs.GAME.enums import ECompressionFlags  # TODO: rename GAME
from mk_utils.nrs.GAME.ue3_common import (  # TODO: rename GAME
    GameArchive, AssetHeader, ExportTableEntry, ImportTableEntry, TableMeta,
)
from mk_utils.nrs.ue3_common import ClassHandler
from mk_utils.utils.filereader import FileReader
from mk_utils.utils.structs import Struct


class GameMidwayAsset(GameArchive):
    """Parser for decompressed Midway format files."""

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

    # TODO: Implement get_external_reader if this game has external data files.
    # IJ2 example: get_tfc_reader()
    # MK11 example: get_psf_reader()

    def parse(self, resolve: bool = True, skip_bulk: bool = False):
        self.parse_summary()
        self.file_name = self.parse_file_name()

        # TODO: Parse file tables if this game has them
        # IJ2 has none; MK11 has PSF + bulk tables here

        self.meta_size = self.mm.tell()

        if self.meta_size != self.header.name_table.offset:
            getLogger("Midway").warning(
                f"Header size mismatch: {self.meta_size} vs expected {self.header.name_table.offset}. "
                f"Seeking to name table offset."
            )
            self.mm.seek(self.header.name_table.offset)

        self.name_table = list(self.parse_name_table())

        # TODO: Parse order of import/export tables varies by game.
        # MK11: exports first, then imports
        # IJ2: imports first, then exports
        self.import_table = list(self.parse_uobject_table(self.header.import_table, ImportTableEntry))
        self.export_table = list(self.parse_uobject_table(self.header.export_table, ExportTableEntry))

        if resolve:
            self.resolve_table_info(self.import_table)
            self.resolve_table_info(self.export_table)

        # TODO: Initialize external data reader if applicable
        # if not skip_bulk:
        #     self.tfc_reader = self.get_tfc_reader()

        self.parsed = True

    def parse_summary(self):
        self.header = AssetHeader.read(self.mm)
        self.compression_mode = ECompressionFlags(self.header.compression_flag)

        self.packages_count = Struct.read_buffer(self.mm, c_uint32)
        # TODO: If game has extra packages, read that count too
        self.packages_extra_count = 0
        self.skip(0x18)
        self.summary_size = self.mm.tell()
        self.validate_file()

    def validate_file(self):
        if self.header.magic != 0x9E2A83C1:
            getLogger("Midway").error("File Magic Failed!")
            return False

        # TODO: Add game-specific FourCC and package type checks
        # Example (IJ2):
        # if self.header.midway_team_four_cc != b"DCF2":
        #     getLogger("Midway").error("Midway Four CC Failed!")
        #     return False

        return True

    def parse_name_table(self):
        self.mm.seek(self.header.name_table.offset)
        for i in range(self.header.name_table.entries):
            name_length = self.read_buffer(c_uint32)
            name = self.read_buffer(c_char * name_length)
            yield name.decode('ascii')

    def parse_uobject_table(self, table, type_):
        self.mm.seek(table.offset)
        for i in range(table.entries):
            entry = Struct.read_buffer(self.mm, type_)
            yield entry

    def resolve_table_info(self, table):
        for entry in table:
            entry.resolve(self.name_table, self.import_table, self.export_table)

    def read_export(self, export):
        self.mm.seek(export.object_offset, 0)
        return self.mm.read(export.object_size)

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
            with open(file_out, "wb") as f:
                f.write(data)

    def dump_tables(self, location, formatted=False):
        location = os.path.join(location, self.file_name)
        os.makedirs(location, exist_ok=True)

        # Names
        with open(os.path.join(location, "nametable.txt"), "w+", encoding="utf-8") as f:
            for i, name in enumerate(self.name_table):
                f.write(f"{hex(i)[2:].upper()}:\t{name}\n")

        # Import/Export tables
        for table, file_base in [(self.import_table, "importtable"), (self.export_table, "exporttable")]:
            if not table:
                continue
            func = str if formatted else repr
            suffix = ".parsed" if formatted else ""
            with open(os.path.join(location, f"{file_base}{suffix}.txt"), "w+", encoding="utf-8") as f:
                for i, entry in enumerate(table):
                    f.write(f"{hex(i)[2:].upper()}:\t{func(entry)}\n")

    def parse_and_save_export(self, export, handler_class, save_dir, overwrite=False):
        if not overwrite:
            out_file = handler_class.make_save_path(export, self.file_name, save_dir)
            if os.path.isfile(out_file):
                logging.getLogger("Midway").info(f"Skipping {export.file_name}...")
                return out_file

        export_data = self.read_export(export)
        handler_obj = handler_class(export_data, self.name_table)
        parsed = handler_obj.parse()
        saved_file = handler_obj.save(parsed, export, self.file_name, save_dir, self)
        return saved_file

    def __str__(self):
        return '\n'.join([
            f"Midway Asset File: {self.file_name}",
            f"Compression Mode: {ECompressionFlags(self.header.compression_flag).name}",
            f"{self.packages_count} Packages | {self.packages_extra_count} Extra Packages",
            f"{len(self.name_table)} Names",
            f"{len(self.import_table)} Imports",
            f"{len(self.export_table)} Exports",
        ])
