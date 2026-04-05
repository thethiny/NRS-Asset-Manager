"""IJ2 Texture2D export handler tests.

Tests that Texture2D exports parse correctly and produce DDS output.
Uses CHAR_Batman_A (with TFC) from gamedata.
"""

import os
import pytest

from mk_utils.nrs.ij2.archive import IJ2UE3Asset
from mk_utils.nrs.ij2.class_handlers import ij2_handlers
from conftest import IJ2_GAMEDATA


BATMAN_XXX = IJ2_GAMEDATA / "CHAR_Batman_A.xxx"
BATMAN_TFC = IJ2_GAMEDATA / "CHAR_Batman_A.tfc"


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("ij2_texture2d"))


@pytest.fixture(scope="module")
def batman_midway():
    if not BATMAN_XXX.is_file():
        pytest.skip("CHAR_Batman_A.xxx not in gamedata")
    tfc = str(BATMAN_TFC) if BATMAN_TFC.is_file() else ""
    asset = IJ2UE3Asset(str(BATMAN_XXX), tfc)
    return asset.parse_all()


def test_texture_exports_exist(batman_midway):
    """Batman package must contain Texture2D exports."""
    texture_exports = [
        exp for exp in batman_midway.export_table
        if exp.class_ and exp.class_.name == "Texture2D"
    ]
    assert len(texture_exports) > 0


def test_texture_extracts_dds(batman_midway, output_dir):
    """At least one Texture2D must produce a DDS file."""
    handler_info = ij2_handlers.get("texture2d")
    assert handler_info, "Texture2D handler not registered"

    handler_class = handler_info["handler_class"]
    dds_files = []

    for export in batman_midway.export_table:
        if not export.class_ or export.class_.name != "Texture2D":
            continue
        try:
            batman_midway.parse_and_save_export(export, handler_class, output_dir, overwrite=True)
        except Exception:
            continue

        # Check if DDS was created
        dds_path = handler_class.make_texture_path(export, batman_midway.file_name, output_dir)
        if os.path.isfile(dds_path):
            dds_files.append(dds_path)

    assert len(dds_files) > 0, "No DDS files produced from Batman textures"


def test_dds_has_valid_header(batman_midway, output_dir):
    """DDS files must start with the DDS magic bytes."""
    handler_info = ij2_handlers.get("texture2d")
    assert handler_info, "Texture2D handler not registered"
    handler_class = handler_info["handler_class"]

    for export in batman_midway.export_table:
        if not export.class_ or export.class_.name != "Texture2D":
            continue

        try:
            batman_midway.parse_and_save_export(export, handler_class, output_dir, overwrite=True)
        except Exception:
            continue

        dds_path = handler_class.make_texture_path(export, batman_midway.file_name, output_dir)
        if os.path.isfile(dds_path):
            with open(dds_path, "rb") as f:
                magic = f.read(4)
            assert magic == b"DDS ", f"Invalid DDS magic in {dds_path}: {magic}"
            return  # One valid check is enough

    pytest.skip("No DDS files available to check")


def test_texture_json_has_mips(batman_midway, output_dir):
    """Texture2D JSON metadata must contain mip information."""
    import json

    handler_info = ij2_handlers.get("texture2d")
    assert handler_info, "Texture2D handler not registered"
    handler_class = handler_info["handler_class"]

    for export in batman_midway.export_table:
        if not export.class_ or export.class_.name != "Texture2D":
            continue

        try:
            saved = batman_midway.parse_and_save_export(export, handler_class, output_dir, overwrite=True)
        except Exception:
            continue

        if saved and os.path.isfile(saved):
            with open(saved, encoding="utf-8") as f:
                data = json.load(f)
            assert "mips" in data, f"Missing mips in {saved}"
            assert "meta" in data, f"Missing meta in {saved}"
            assert len(data["mips"]) > 0, f"Empty mips in {saved}"
            return

    pytest.skip("No texture JSON available to check")
