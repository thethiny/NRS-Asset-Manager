"""MK11 Database export handler tests.

Tests that database-type exports parse correctly and produce valid JSON output.
Uses files from gamedata/MK11/Databases if available.
"""

import json
import os
import pytest

from mk_utils.nrs.mk11.archive import MK11UE3Asset
from mk_utils.nrs.ue3_common import get_handlers
from mk_utils.nrs.mk11.class_handlers import *  # noqa: F401, F403 - registers handlers
from conftest import MK11_GAMEDATA


DATABASE_DIR = MK11_GAMEDATA / "Databases"

DATABASE_FILES = [f[:-4] for f in os.listdir(DATABASE_DIR) if f.endswith(".xxx")] if DATABASE_DIR.is_dir() else []


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("mk11_database"))


@pytest.fixture(scope="module")
def handlers():
    return get_handlers()


@pytest.mark.parametrize("file_base", DATABASE_FILES)
def test_database_extracts_json(file_base, output_dir, handlers):
    """Database files must produce at least one JSON output."""
    xxx_path = str(DATABASE_DIR / (file_base + ".xxx"))
    asset = MK11UE3Asset(xxx_path)
    midway = asset.parse_all(skip_bulk=True)

    extracted = []
    for export in midway.export_table:
        file_type = export.class_.name
        handler = handlers.get(file_type)
        if not handler:
            continue
        handler_class = handler["handler_class"]
        saved = midway.parse_and_save_export(export, handler_class, output_dir, overwrite=True)
        extracted.append(saved)

    assert len(extracted) > 0, f"No database exports extracted from {file_base}"

    for path in extracted:
        assert path.endswith(".json"), f"Expected JSON output, got: {path}"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert len(data) > 0
