"""
IJ2 Archive (.xxx) parser and Midway format converter.

IJ2 .xxx file structure:
1. IJ2AssetHeader (100 bytes)
2. packages_count (u32)
3. IJ2CompressedChunk[packages_count] (24 bytes each, flat array)
4. 0x18 bytes padding (zeros)
5. filename_length (u32) + filename (null-terminated)
6. Compressed blocks (Oodle)
"""

from ctypes import c_uint32
from logging import getLogger
import logging
import os

from mk_utils.nrs.ij2.ue3_common import (
    IJ2Archive, IJ2AssetHeader, IJ2CompressedChunk,
)
from mk_utils.nrs.ij2.midway import IJ2MidwayAsset
from mk_utils.nrs.ij2.enums import ECompressionFlags
from mk_utils.utils.structs import Struct


class IJ2UE3Asset(IJ2Archive):
    """Parser for IJ2 .xxx compressed archive files."""

    VERSION_RANGE = range(0x254, 0x2F8)  # IJ2 engine versions (retail = 0x2DC)

    def __init__(self, path: str, extra_path: str = ""):
        super().__init__(path, extra_path)

    def parse_header(self):
        header = IJ2AssetHeader.read(self.mm)
        return header

    def parse(self, skip_bulk: bool = False):
        self.header = self.parse_header()
        self.compression_mode = ECompressionFlags(self.header.compression_flag)
        self.compressor = self.get_compressor(self.compression_mode)

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
            yield IJ2CompressedChunk.read(self.mm)

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
                if len(data) != entry.uncompressed_size:
                    getLogger("IJ2Archive").warning(
                        f"Decompressed size mismatch: got {len(data)}, expected {entry.uncompressed_size}"
                    )
                cls._place_data(buffer, entry.uncompressed_offset, data)

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
