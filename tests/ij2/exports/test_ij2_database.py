"""IJ2 Database export handler tests.

Tests that database-type exports (DCF2AssetDefinitions, DCF2GearRarity, etc.)
parse correctly and produce valid JSON output.
"""

import json
import pytest

from mk_utils.nrs.ij2.archive import IJ2UE3Asset
from mk_utils.nrs.ij2.class_handlers import ij2_handlers
from conftest import IJ2_GAMEDATA


DATABASE_FILES = {
    "ITEMDEFINITIONSAUX": "dcf2assetdefinitions",
    "DCF2GEARRARITYTABLE": "dcf2gearrarity",
    "ExportedCapData": "dcf2capinfotable",
}

AVAILABLE = {
    name: cls for name, cls in DATABASE_FILES.items()
    if (IJ2_GAMEDATA / (name + ".xxx")).is_file()
}


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("ij2_database"))


@pytest.mark.parametrize("file_base", AVAILABLE.keys())
def test_database_extracts_json(file_base, output_dir):
    """Database files must produce at least one JSON output."""
    xxx_path = str(IJ2_GAMEDATA / (file_base + ".xxx"))
    asset = IJ2UE3Asset(xxx_path)
    midway = asset.parse_all()

    extracted = []
    for export in midway.export_table:
        file_type = export.class_.name if export.class_ else ""
        handler = ij2_handlers.get(file_type.lower())
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
        assert isinstance(data, dict), f"JSON root must be a dict: {path}"
        assert len(data) > 0, f"JSON must not be empty: {path}"


@pytest.mark.parametrize("file_base", AVAILABLE.keys())
def test_database_properties_not_empty(file_base, output_dir):
    """Database JSON must contain meaningful property data."""
    xxx_path = str(IJ2_GAMEDATA / (file_base + ".xxx"))
    asset = IJ2UE3Asset(xxx_path)
    midway = asset.parse_all()

    for export in midway.export_table:
        file_type = export.class_.name if export.class_ else ""
        handler = ij2_handlers.get(file_type.lower())
        if not handler:
            continue
        handler_class = handler["handler_class"]
        saved = midway.parse_and_save_export(export, handler_class, output_dir, overwrite=True)

        with open(saved, encoding="utf-8") as f:
            data = json.load(f)

        # At least one property with a non-trivial value
        has_data = any(
            v is not None and v != {} and v != [] and v != ""
            for v in data.values()
        )
        assert has_data, f"Database {file_base}/{export.file_name} has no meaningful data"
        break  # Only check first database export per file
