import os
import pytest
from mk_utils.scripts.extractors import extract_all

GAME_DIR = os.path.join("H:", "MK11", "Asset")

test_files = [
    "ui_i_Emoticons",
    "MK11UNLOCKTABLE",
    "KOLLECTIONITEMDATA",
    "MK11ItemDatabase",
]


@pytest.fixture(scope="module")
def game_dir():
    return GAME_DIR


@pytest.mark.parametrize("file_base", test_files)
def test_extract_file(game_dir, file_base):
    xxx_path = os.path.join(game_dir, file_base + ".xxx")
    psf_path = os.path.join(game_dir, file_base + ".psf")

    assert os.path.isfile(xxx_path), f"Missing input file: {xxx_path}"

    result = extract_all([(xxx_path, psf_path)], overwrite=True)

    assert result, f"extract_all failed for: {xxx_path}"
