"""Pass validation tests for IJ2.

Copies files from the IJ2 game asset directory (defined in .env) to temp,
then validates that they parse and extract correctly.

Tests:
- Init file (different format)
- File with TFC companion
- Random file without TFC
"""

import os
import pytest

from mk_utils.nrs.ij2.archive import IJ2UE3Asset
from mk_utils.scripts.ij2_extractors import extract_all
from conftest import copy_xxx, find_random_xxx, TEMP_DIR


@pytest.fixture(scope="module")
def ij2_temp(ij2_asset_dir):
    dest = TEMP_DIR / "ij2_validation"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("ij2_validation_output"))


class TestInit:
    """Init files use a different internal format (audio packages)."""

    def test_parse_init(self, ij2_asset_dir, ij2_temp):
        xxx = copy_xxx(ij2_asset_dir, "Init", ij2_temp / "init")
        asset = IJ2UE3Asset(xxx)
        midway = asset.parse_all()

        assert midway.parsed
        assert midway.name_table
        assert midway.export_table is not None

    def test_parse_init_scriptassets(self, ij2_asset_dir, ij2_temp):
        xxx = copy_xxx(ij2_asset_dir, "INIT_ScriptAssets", ij2_temp / "init_sa")
        asset = IJ2UE3Asset(xxx)
        midway = asset.parse_all()

        assert midway.parsed
        assert len(midway.export_table) > 0


class TestTFC:
    """Files with external TFC texture data."""

    def test_parse_with_tfc(self, ij2_asset_dir, ij2_temp):
        name = find_random_xxx(ij2_asset_dir, with_tfc=True)
        dest = ij2_temp / "tfc"
        xxx = copy_xxx(ij2_asset_dir, name, dest)

        tfc_path = os.path.splitext(xxx)[0] + ".tfc"
        extra = tfc_path if os.path.isfile(tfc_path) else ""

        asset = IJ2UE3Asset(xxx, extra)
        midway = asset.parse_all()

        assert midway.parsed
        assert len(midway.export_table) > 0

    def test_extract_with_tfc(self, ij2_asset_dir, ij2_temp, output_dir):
        name = find_random_xxx(ij2_asset_dir, with_tfc=True)
        dest = ij2_temp / "tfc_extract"
        xxx = copy_xxx(ij2_asset_dir, name, dest)

        result = extract_all([xxx], output_dir=output_dir, overwrite=True)
        # TFC files typically have textures that get extracted
        assert result is not None


class TestNoTFC:
    """Random file without TFC companion."""

    def test_parse_no_tfc(self, ij2_asset_dir, ij2_temp):
        name = find_random_xxx(ij2_asset_dir, without_tfc=True)
        dest = ij2_temp / "no_tfc"
        xxx = copy_xxx(ij2_asset_dir, name, dest)

        asset = IJ2UE3Asset(xxx)
        midway = asset.parse_all()

        assert midway.parsed

    def test_extract_no_tfc(self, ij2_asset_dir, ij2_temp, output_dir):
        name = find_random_xxx(ij2_asset_dir, without_tfc=True)
        dest = ij2_temp / "no_tfc_extract"
        xxx = copy_xxx(ij2_asset_dir, name, dest)

        result = extract_all([xxx], output_dir=output_dir, overwrite=True)
        assert result is not None
