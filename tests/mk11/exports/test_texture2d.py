"""MK11 Texture2D export handler tests.

Tests that Texture2D exports parse correctly.
Uses CHAR_BAR_ScriptAssets from gamedata (skip_bulk since PSF decompression
can segfault on some Oodle versions).
"""

import pytest

from mk_utils.nrs.mk11.archive import MK11UE3Asset
from mk_utils.nrs.mk11.class_handlers import *  # noqa: F401, F403 - registers handlers
from conftest import MK11_GAMEDATA


BARAKA_XXX = MK11_GAMEDATA / "CHAR_BAR_ScriptAssets.xxx"
BARAKA_PSF = MK11_GAMEDATA / "CHAR_BAR_ScriptAssets.psf"


@pytest.fixture(scope="module")
def baraka_midway():
    if not BARAKA_XXX.is_file():
        pytest.skip("CHAR_BAR_ScriptAssets.xxx not in gamedata")
    psf = str(BARAKA_PSF) if BARAKA_PSF.is_file() else ""
    asset = MK11UE3Asset(str(BARAKA_XXX), psf)
    return asset.parse_all(skip_bulk=True)


def test_texture_exports_exist(baraka_midway):
    """Baraka package must contain Texture2D exports."""
    texture_exports = [
        exp for exp in baraka_midway.export_table
        if exp.class_ and exp.class_.name == "Texture2D"
    ]
    assert len(texture_exports) > 0, "No Texture2D exports found in Baraka"


def test_texture_exports_have_valid_offsets(baraka_midway):
    """Texture2D exports must have valid offsets within the file."""
    buffer_size = baraka_midway.mm.size()

    for export in baraka_midway.export_table:
        if not export.class_ or export.class_.name != "Texture2D":
            continue
        assert export.object_offset < buffer_size, (
            f"{export.full_name}: offset 0x{export.object_offset:X} >= buffer 0x{buffer_size:X}"
        )
        assert export.object_offset + export.object_size <= buffer_size, (
            f"{export.full_name}: extends past buffer end"
        )


def test_texture_export_data_readable(baraka_midway):
    """Texture2D export data must be readable from the midway buffer."""
    for export in baraka_midway.export_table:
        if not export.class_ or export.class_.name != "Texture2D":
            continue
        data = baraka_midway.read_export(export)
        assert len(data) == export.object_size
        assert len(data) > 0
        return  # One check is enough

    pytest.skip("No Texture2D exports to check")
