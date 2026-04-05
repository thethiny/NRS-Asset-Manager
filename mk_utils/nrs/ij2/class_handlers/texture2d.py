"""
IJ2 Texture2D handler.

IJ2 textures store mip data differently from MK11:
- No central PSF/bulk tables; TFC references are per-texture
- TextureFileCacheName property specifies the .tfc file
- Each mip has: flags(u32) + element_count(u32) + size_on_disk(u64)
  + offset_in_file(u64) + [inline_data if not in TFC] + width(u32) + height(u32)
- flags & 1 = data stored in TFC file (compressed with Oodle blocks)
- flags == 0 = inline data stored in the UPK midway buffer
"""

import json
import logging
import os
from ctypes import c_uint32, c_uint64
from typing import List, Optional

from mk_utils.nrs.ij2.enums import EPixelFormat, ECompressionFlags
from mk_utils.nrs.ij2.ue3_common import IJ2Archive
from mk_utils.nrs.ij2.ue3_properties import UProperty
from mk_utils.nrs.mk11.class_handlers.bc7 import (
    make_dds_data,
    make_png_data,
    make_png_from_data,
    _make_header,
)
from mk_utils.nrs.ue3_common import ClassHandler
from mk_utils.utils.structs import Struct


BULKDATA_StoreInSeparateFile = 0x01


class TextureAddress:
    TA_Wrap = 0
    TA_Clamp = 1
    TA_Mirror = 2


class TextureGroup:
    TEXTUREGROUP_World = 0
    TEXTUREGROUP_Character = 2


class IJ2Texture2DHandler(ClassHandler):
    HANDLED_TYPES = {
        "Texture2D",
    }

    enums = {
        "Format": EPixelFormat,
    }

    def parse(self):
        metadata = {}
        while self.mm.tell() < self.mm.size():
            result = UProperty.parse_once(self.mm, self.name_table, True)
            if result is None:
                break
            prop_dict, _ = result
            for k, v in prop_dict.items():
                if isinstance(v, str) and "::" in v:
                    enum_class = self.enums.get(k)
                    if enum_class:
                        try:
                            enum_val = int(v.split("::")[1])
                            prop_dict[k] = f"{enum_class.__name__}::{enum_class(enum_val).name}"
                        except (ValueError, KeyError):
                            pass
            metadata.update(prop_dict)

        # Parse the mip data structure after properties
        mips = self._parse_mips()

        return {
            "meta": metadata,
            "mips": mips,
        }

    def _parse_mips(self) -> List[dict]:
        """Parse IJ2 Texture2D mip data structure.

        Structure before mips:
        - 16 bytes padding/unknown
        - u64 unknown_offset_1
        - 16 bytes padding/unknown
        - u64 unknown_offset_2
        - 8 bytes padding
        - u32 mip_count

        Per mip:
        - u32 flags (bit 0 = store in separate TFC file)
        - u32 element_count (uncompressed data size in bytes)
        - u64 size_on_disk (compressed size for TFC, same as element_count for inline)
        - u64 offset_in_file (offset in TFC file or absolute offset in UPK)
        - [element_count bytes of inline data if flags == 0]
        - u32 width
        - u32 height
        """
        # Skip header area (16 + 8 + 16 + 8 + 8 + 4 padding = 0x3C bytes to mip_count)
        self.mm.seek(0x3C, 1)
        mip_count = Struct.read_buffer(self.mm, c_uint32)

        mips = []
        for i in range(mip_count):
            flags = Struct.read_buffer(self.mm, c_uint32)
            element_count = Struct.read_buffer(self.mm, c_uint32)
            size_on_disk = Struct.read_buffer(self.mm, c_uint64)
            offset_in_file = Struct.read_buffer(self.mm, c_uint64)

            in_tfc = bool(flags & BULKDATA_StoreInSeparateFile)

            # For inline data (not in TFC), the raw bytes follow immediately
            inline_data = None
            if not in_tfc and element_count > 0:
                inline_data = self.mm.read(element_count)

            width = Struct.read_buffer(self.mm, c_uint32)
            height = Struct.read_buffer(self.mm, c_uint32)

            mips.append({
                "index": i,
                "flags": flags,
                "element_count": element_count,
                "size_on_disk": size_on_disk,
                "offset_in_file": offset_in_file,
                "width": width,
                "height": height,
                "in_tfc": in_tfc,
                "inline_data": inline_data,
            })

        return mips

    @classmethod
    def make_save_path(cls, export, asset_name: str, save_path: str):
        save_path = super().make_save_path(export, asset_name, save_path)
        return save_path.rsplit(".", 1)[0].strip() + ".json"

    @classmethod
    def make_texture_path(cls, export, asset_name: str, save_path: str):
        save_path = ClassHandler.make_save_path(export, asset_name, save_path)
        return save_path.rsplit(".", 1)[0].strip() + ".dds"

    def _read_tfc_mip(self, mip: dict, tfc_reader, compression_flag: int) -> Optional[bytes]:
        """Read and decompress a mip from the TFC file."""
        if not tfc_reader:
            logging.getLogger("IJ2Texture2D").warning("No TFC reader available for TFC mip data")
            return None

        tfc_reader.mm.seek(mip["offset_in_file"])
        return IJ2Archive.deserialize_block(tfc_reader.mm, compression_flag)

    def _read_inline_mip(self, mip: dict, midway_mm) -> Optional[bytes]:
        """Read inline mip data from the midway buffer."""
        if mip["inline_data"] is not None:
            return mip["inline_data"]

        # Fallback: read from midway buffer at absolute offset
        midway_mm.seek(mip["offset_in_file"])
        return midway_mm.read(mip["element_count"])

    def save(self, data, export, asset_name, save_dir, instance, *args, **kwargs):
        metadata = data["meta"]
        mips = data["mips"]

        format_str = metadata.get("Format", "")
        if "::" in format_str:
            format_name = format_str.split("::")[-1]
            try:
                pixel_format = EPixelFormat[format_name]
            except KeyError:
                logging.getLogger("IJ2Texture2D").warning(
                    f"Unknown pixel format: {format_name}"
                )
                return self._save_json_only(data, export, asset_name, save_dir)
        else:
            logging.getLogger("IJ2Texture2D").warning(f"No format in metadata")
            return self._save_json_only(data, export, asset_name, save_dir)

        tfc_name = metadata.get("TextureFileCacheName", "")
        tfc_reader = None
        compression_flag = ECompressionFlags.OODLE  # TFC data is always Oodle-compressed

        if tfc_name and any(m["in_tfc"] for m in mips):
            tfc_reader = getattr(instance, "tfc_reader", None)

            if not tfc_reader:
                logging.getLogger("IJ2Texture2D").warning(
                    f"Texture references TFC '{tfc_name}' but no TFC reader available. "
                    f"Only inline mips will be extracted."
                )

        # Collect all mip raw data (decompressed)
        mip_data_list = []
        for mip in mips:
            if mip["in_tfc"]:
                raw = self._read_tfc_mip(mip, tfc_reader, compression_flag)
            else:
                raw = self._read_inline_mip(mip, instance.mm)

            if raw is None:
                logging.getLogger("IJ2Texture2D").warning(
                    f"Failed to read mip[{mip['index']}] {mip['width']}x{mip['height']}"
                )
                continue

            if len(raw) != mip["element_count"]:
                logging.getLogger("IJ2Texture2D").warning(
                    f"Mip[{mip['index']}] size mismatch: got {len(raw)}, expected {mip['element_count']}"
                )

            mip_data_list.append((mip, raw))

        if not mip_data_list:
            logging.getLogger("IJ2Texture2D").warning("No mip data extracted")
            return self._save_json_only(data, export, asset_name, save_dir)

        # Build DDS from raw mip data
        image_file = self.make_texture_path(export, asset_name, save_dir)
        self._save_texture(
            mip_data_list, pixel_format, metadata, image_file
        )

        # Save JSON metadata
        return self._save_json(data, mips, export, asset_name, save_dir)

    def _save_texture(self, mip_data_list, pixel_format, metadata, image_file):
        """Build and save DDS/PNG from raw mip data."""
        dxgi_map = {
            EPixelFormat.PF_DXT1: 71,   # DXGI_FORMAT_BC1_UNORM
            EPixelFormat.PF_DXT3: 74,   # DXGI_FORMAT_BC2_UNORM
            EPixelFormat.PF_DXT5: 77,   # DXGI_FORMAT_BC3_UNORM
            EPixelFormat.PF_BC4: 80,    # DXGI_FORMAT_BC4_UNORM
            EPixelFormat.PF_BC5: 83,    # DXGI_FORMAT_BC5_UNORM
            EPixelFormat.PF_BC6: 95,    # DXGI_FORMAT_BC6H_UF16
            EPixelFormat.PF_BC7: 98,    # DXGI_FORMAT_BC7_UNORM
            EPixelFormat.PF_G8: 61,     # DXGI_FORMAT_R8_UNORM
            EPixelFormat.PF_A8R8G8B8: 28,  # DXGI_FORMAT_R8G8B8A8_UNORM
            EPixelFormat.PF_V8U8: 118,  # DXGI_FORMAT_R8G8_SNORM
        }

        dxgi_format = dxgi_map.get(pixel_format)
        if dxgi_format is None:
            logging.getLogger("IJ2Texture2D").warning(
                f"Pixel format {pixel_format.name} not supported for DDS export"
            )
            return

        # Sort mips by size (largest first for DDS)
        mip_data_list.sort(key=lambda x: x[0]["element_count"], reverse=True)

        width = mip_data_list[0][0]["width"]
        height = mip_data_list[0][0]["height"]
        mip_count = len(mip_data_list)

        # Concatenate all mip data
        all_data = b"".join(raw for _, raw in mip_data_list)

        header = _make_header(width, height, mip_count, dxgi_format, 1)
        dds_data = header + all_data

        os.makedirs(os.path.dirname(image_file), exist_ok=True)
        with open(image_file, "wb") as f:
            f.write(dds_data)

        logging.getLogger("IJ2Texture2D").info(f"Saved DDS: {image_file} ({width}x{height}, {mip_count} mips)")

        # Try PNG conversion for supported formats
        if pixel_format in {
            EPixelFormat.PF_BC5, EPixelFormat.PF_BC6,
            EPixelFormat.PF_BC7, EPixelFormat.PF_DXT1,
            EPixelFormat.PF_DXT3, EPixelFormat.PF_DXT5,
        }:
            try:
                first_mip_data = mip_data_list[0][1]
                first_header = _make_header(width, height, 1, dxgi_format, 1)
                from dds import decode_dds
                png = decode_dds(first_header + first_mip_data)
                if png:
                    png_file = image_file.rsplit(".", 1)[0] + ".png"
                    png.save(png_file)
                    logging.getLogger("IJ2Texture2D").info(f"Saved PNG: {png_file}")
            except Exception as e:
                logging.getLogger("IJ2Texture2D").debug(f"PNG conversion skipped: {e}")

    def _save_json_only(self, data, export, asset_name, save_dir):
        """Save only JSON metadata (no texture extraction)."""
        return self._save_json(data, data["mips"], export, asset_name, save_dir)

    def _save_json(self, data, mips, export, asset_name, save_dir):
        save_file = self.make_save_path(export, asset_name, save_dir)
        # Strip inline_data from JSON (not serializable and not useful)
        json_data = {
            "meta": data["meta"],
            "mips": [
                {k: v for k, v in m.items() if k != "inline_data"}
                for m in mips
            ],
        }
        with open(save_file, "w+") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        logging.getLogger("IJ2Texture2D").info(f"Saved metadata: {save_file}")
        return save_file
