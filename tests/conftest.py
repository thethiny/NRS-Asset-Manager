import os
import shutil
import random
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

TEMP_DIR = Path("temp/test_runs")

IJ2_ASSET_DIR = os.getenv("IJ2_ASSET_DIR", "")
MK11_ASSET_DIR = os.getenv("MK11_ASSET_DIR", "")

IJ2_GAMEDATA = Path("gamedata/IJ2")
MK11_GAMEDATA = Path("gamedata/MK11")


def _copy_to_temp(src: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(src, dest_dir))


# ── Fixtures: Game Asset Directories ─────────────────────────────────────────

@pytest.fixture(scope="session")
def ij2_asset_dir():
    if not IJ2_ASSET_DIR or not os.path.isdir(IJ2_ASSET_DIR):
        pytest.skip("IJ2_ASSET_DIR not set or not found")
    return IJ2_ASSET_DIR


@pytest.fixture(scope="session")
def mk11_asset_dir():
    if not MK11_ASSET_DIR or not os.path.isdir(MK11_ASSET_DIR):
        pytest.skip("MK11_ASSET_DIR not set or not found")
    return MK11_ASSET_DIR


# ── Fixtures: Temp Output ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def temp_output():
    path = TEMP_DIR / "output"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


# ── Helpers: Copy game files to temp ─────────────────────────────────────────

def copy_xxx(asset_dir: str, name: str, dest: Path) -> str:
    """Copy a .xxx file (and .tfc/.psf if present) to dest. Returns xxx path."""
    src_xxx = os.path.join(asset_dir, name + ".xxx")
    if not os.path.isfile(src_xxx):
        pytest.skip(f"File not found: {src_xxx}")
    dest.mkdir(parents=True, exist_ok=True)
    xxx = str(shutil.copy2(src_xxx, dest))

    for ext in (".tfc", ".psf"):
        companion = os.path.join(asset_dir, name + ext)
        if os.path.isfile(companion):
            shutil.copy2(companion, dest)

    return xxx


def find_random_xxx(asset_dir: str, with_tfc: bool = False, without_tfc: bool = False) -> str:
    """Find a random .xxx file from asset_dir matching criteria."""
    all_xxx = [f[:-4] for f in os.listdir(asset_dir) if f.endswith(".xxx")]
    tfc_names = {f[:-4] for f in os.listdir(asset_dir) if f.endswith(".tfc")}
    psf_names = {f[:-4] for f in os.listdir(asset_dir) if f.endswith(".psf")}

    if with_tfc:
        candidates = [n for n in all_xxx if n in tfc_names or n in psf_names]
    elif without_tfc:
        candidates = [n for n in all_xxx if n not in tfc_names and n not in psf_names]
    else:
        candidates = all_xxx

    if not candidates:
        pytest.skip(f"No matching .xxx files in {asset_dir}")

    return random.choice(candidates)
