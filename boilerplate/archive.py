"""
TODO: Game Archive (.xxx) parser and Midway format converter.

Copy this file to mk_utils/nrs/<game_code>/archive.py and implement.
"""

from ctypes import c_uint32
from logging import getLogger
import logging
import os

from mk_utils.nrs.GAME.ue3_common import (  # TODO: rename GAME
    GameArchive, AssetHeader, CompressedChunk,
)
from mk_utils.nrs.GAME.midway import GameMidwayAsset  # TODO: rename GAME
from mk_utils.nrs.GAME.enums import ECompressionFlags  # TODO: rename GAME
from mk_utils.utils.structs import Struct


class GameUE3Asset(GameArchive):
    """Parser for game .xxx compressed archive files."""

    VERSION_RANGE = range(0x000, 0x000)  # TODO: Set the version range for this game

    def __init__(self, path: str, extra_path: str = ""):
        super().__init__(path, extra_path)

    def parse_header(self):
        header = AssetHeader.read(self.mm)
        return header

    def parse(self, skip_bulk: bool = False):
        self.header = self.parse_header()
        self.compression_mode = ECompressionFlags(self.header.compression_flag)
        self.compressor = self.get_compressor(self.compression_mode)

        # TODO: Parse compressed chunk table
        self.packages_count = Struct.read_buffer(self.mm, c_uint32)
        self.package_entries = list(self._parse_package_entries(self.packages_count))

        self.packages_extra = []  # TODO: MK11 has extra packages, IJ2 does not

        self.skip(0x18)  # Padding

        self.file_name = self.parse_file_name()

        # TODO: Parse file tables if this game has them (MK11 has PSF/bulk tables here)
        self.psf_tables = []
        self.bulk_tables = []

        self.parsed = True

    def _parse_package_entries(self, count):
        for _ in range(count):
            yield CompressedChunk.read(self.mm)

    def deserialize_block(self):
        return super().deserialize_block(self.mm, self.compressor)

    def to_midway(self, skip_bulk: bool = False):
        buffer = self._MidwayBuilder.from_asset(self, skip_bulk)
        return GameMidwayAsset(buffer, self.psf_source)

    class _MidwayBuilder:
        @classmethod
        def from_asset(cls, asset, skip_bulk: bool = False):
            if not asset.parsed:
                logging.getLogger("Archive").warning("Asset was not parsed. Parsing first.")
                asset.parse(skip_bulk=skip_bulk)

            buffer = bytearray()

            # Build header with compression reset to 0
            base = asset.header.serialize()[:-4]
            buffer += base + (0).to_bytes(4, "little")

            # Packages count = 0 in midway
            buffer += (0).to_bytes(4, "little")

            # TODO: If this game has extra packages, add another count here

            # Padding
            buffer += b"\x00" * 0x18

            # Filename
            fn = asset.file_name
            buffer += (len(fn) + 1).to_bytes(4, "little") + fn.encode("ascii") + b"\x00"

            # TODO: If this game has file tables, build them here

            # Decompress all blocks and place at correct offsets
            for entry in asset.package_entries:
                asset.mm.seek(entry.compressed_offset)
                data = asset.deserialize_block()
                if len(data) != entry.uncompressed_size:
                    getLogger("Archive").warning(
                        f"Size mismatch: got {len(data)}, expected {entry.uncompressed_size}"
                    )
                end = entry.uncompressed_offset + len(data)
                if entry.uncompressed_offset > len(buffer):
                    buffer += b"\x00" * (entry.uncompressed_offset - len(buffer))
                buffer[entry.uncompressed_offset:end] = data

            return buffer

    def dump(self, save_path: str):
        save_path = os.path.join(save_path, self.file_name)
        os.makedirs(save_path, exist_ok=True)
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
