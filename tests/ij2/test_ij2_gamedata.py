"""Tests for IJ2 files in the gamedata/IJ2 folder."""

import os
import pytest

from mk_utils.nrs.ij2.archive import IJ2UE3Asset
from mk_utils.scripts.ij2_extractors import extract_all
from conftest import IJ2_GAMEDATA


XXX_FILES = [f[:-4] for f in os.listdir(IJ2_GAMEDATA) if f.endswith(".xxx")] if IJ2_GAMEDATA.is_dir() else []


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("ij2_gamedata"))


@pytest.mark.parametrize("file_base", XXX_FILES)
def test_parse_xxx(file_base):
    """Every .xxx in gamedata/IJ2 must parse without crashing."""
    xxx_path = str(IJ2_GAMEDATA / (file_base + ".xxx"))
    tfc_path = str(IJ2_GAMEDATA / (file_base + ".tfc"))

    if os.path.isfile(tfc_path):
        asset = IJ2UE3Asset(xxx_path, tfc_path)
    else:
        asset = IJ2UE3Asset(xxx_path)

    midway = asset.parse_all()

    assert midway.parsed
    assert midway.name_table
    assert midway.export_table is not None


@pytest.mark.parametrize("file_base", XXX_FILES)
def test_extract_xxx(file_base, output_dir):
    """Every .xxx in gamedata/IJ2 must extract without crashing."""
    xxx_path = str(IJ2_GAMEDATA / (file_base + ".xxx"))
    tfc_path = str(IJ2_GAMEDATA / (file_base + ".tfc"))

    if os.path.isfile(tfc_path):
        files = [(xxx_path, tfc_path)]
    else:
        files = [xxx_path]

    # Should not raise
    extract_all(files, output_dir=output_dir, overwrite=True)


COALESCED_FILES = [f for f in os.listdir(IJ2_GAMEDATA) if f.lower().endswith((".eng", ".ini"))] if IJ2_GAMEDATA.is_dir() else []


@pytest.mark.parametrize("file_name", COALESCED_FILES)
def test_extract_coalesced(file_name, output_dir):
    """Coalesced files must extract without crashing."""
    result = extract_all(
        [str(IJ2_GAMEDATA / file_name)],
        output_dir=output_dir,
        overwrite=True,
    )
    assert len(result) > 0
