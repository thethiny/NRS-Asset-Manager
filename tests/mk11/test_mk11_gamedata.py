"""Tests for MK11 files in the gamedata/MK11 folder."""

import os
import pytest

from mk_utils.nrs.mk11.archive import MK11UE3Asset
from conftest import MK11_GAMEDATA


XXX_FILES = [f[:-4] for f in os.listdir(MK11_GAMEDATA) if f.endswith(".xxx")] if MK11_GAMEDATA.is_dir() else []


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("mk11_gamedata"))


@pytest.mark.parametrize("file_base", XXX_FILES)
def test_parse_xxx(file_base, output_dir):
    """Every .xxx in gamedata/MK11 must parse without crashing."""
    xxx_path = str(MK11_GAMEDATA / (file_base + ".xxx"))
    psf_path = str(MK11_GAMEDATA / (file_base + ".psf"))

    if os.path.isfile(psf_path):
        asset = MK11UE3Asset(xxx_path, psf_path)
    else:
        asset = MK11UE3Asset(xxx_path)

    midway = asset.parse_all(skip_bulk=True)

    assert midway.parsed
    assert midway.name_table
    assert midway.export_table is not None
