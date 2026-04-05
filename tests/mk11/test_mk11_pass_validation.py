"""Pass validation tests for MK11.

Copies files from the MK11 game asset directory (defined in .env) to temp,
then validates that they parse and extract correctly.

Tests:
- Init file (different format)
- File with PSF companion
- Random file without PSF
"""

import os
import pytest

from mk_utils.nrs.mk11.archive import MK11UE3Asset
from conftest import copy_xxx, find_random_xxx, TEMP_DIR


@pytest.fixture(scope="module")
def mk11_temp(mk11_asset_dir):
    dest = TEMP_DIR / "mk11_validation"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


class TestInit:
    """Init files use a different internal format (audio packages)."""

    def test_parse_init(self, mk11_asset_dir, mk11_temp):
        xxx = copy_xxx(mk11_asset_dir, "Init", mk11_temp / "init")
        asset = MK11UE3Asset(xxx)
        asset.parse(skip_bulk=True)

        assert asset.parsed
        assert asset.file_name

    def test_parse_init_scriptassets(self, mk11_asset_dir, mk11_temp):
        xxx = copy_xxx(mk11_asset_dir, "INIT_ScriptAssets", mk11_temp / "init_sa")
        psf_path = os.path.splitext(xxx)[0] + ".psf"
        # PSF may be uppercase
        if not os.path.isfile(psf_path):
            psf_candidates = [f for f in os.listdir(os.path.dirname(xxx)) if f.lower().endswith(".psf")]
            if psf_candidates:
                psf_path = os.path.join(os.path.dirname(xxx), psf_candidates[0])

        extra = psf_path if os.path.isfile(psf_path) else ""
        asset = MK11UE3Asset(xxx, extra)
        midway = asset.parse_all(skip_bulk=True)

        assert midway.parsed
        assert len(midway.export_table) > 0


class TestPSF:
    """Files with external PSF data."""

    def test_parse_with_psf(self, mk11_asset_dir, mk11_temp):
        name = find_random_xxx(mk11_asset_dir, with_tfc=True)
        dest = mk11_temp / "psf"
        xxx = copy_xxx(mk11_asset_dir, name, dest)
        psf_path = os.path.splitext(xxx)[0] + ".psf"
        extra = psf_path if os.path.isfile(psf_path) else ""

        asset = MK11UE3Asset(xxx, extra)
        midway = asset.parse_all(skip_bulk=True)

        assert midway.parsed
        assert len(midway.export_table) > 0


class TestNoPSF:
    """Random file without PSF companion."""

    def test_parse_no_psf(self, mk11_asset_dir, mk11_temp):
        name = find_random_xxx(mk11_asset_dir, without_tfc=True)
        dest = mk11_temp / "no_psf"
        xxx = copy_xxx(mk11_asset_dir, name, dest)

        asset = MK11UE3Asset(xxx)
        midway = asset.parse_all(skip_bulk=True)

        assert midway.parsed
