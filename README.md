# NRS Asset Manager

A Python toolkit for extracting and parsing game assets from **NetherRealm Studios** titles built on the custom UE3-based Midway engine.

## Supported Games

| Game | Year | Codename | Status |
|------|------|----------|--------|
| **Injustice 2** | 2017 | DCF2 | Full extraction (textures, databases, TFC, localization) |
| **Mortal Kombat 11** | 2019 | MK11 | Full extraction (textures, databases, PSF) |

## Quick Start

```bash
# Auto-detects game from file version
python main.py extract path/to/file.xxx

# Display file header (game, version, tables)
python main.py header path/to/file.xxx

# List exports, imports, or names
python main.py list path/to/file.xxx --exports
python main.py list path/to/file.xxx --imports
python main.py list path/to/file.xxx --names

# Extract specific export by glob or regex
python main.py export path/to/file.xxx --name "*Body_Color*"
python main.py export path/to/file.xxx --name "Batman.*Texture" --regex

# Extract raw data (no handler)
python main.py export path/to/file.xxx --name "*.SkeletalMesh" --raw

# Create decompressed Midway UPK only
python main.py midway path/to/file.xxx --output out/

# Dump all raw exports
python main.py extract-all path/to/file.xxx
```

Companion files (`.tfc` for IJ2, `.psf` for MK11) are auto-discovered from the same directory.

## Extraction Pipeline

All NRS games follow the same three-stage pipeline:

```
.xxx (Compressed)  →  Midway (Decompressed UPK)  →  Exports (Game Objects)
                                                      ├── Database  → JSON
                                                      ├── Texture2D → DDS/PNG
                                                      └── Coalesced → Text files
```

## Project Structure

```
main.py                        # CLI entry point (auto-detects game)
mk_utils/
├── nrs/
│   ├── ue3_common.py          # Shared base classes
│   ├── compression/           # Oodle v4/v5 DLL wrappers
│   ├── localization_parser.py # Coalesced AES decryption
│   ├── ij2/                   # Injustice 2
│   │   ├── archive.py         # .xxx → Midway builder
│   │   ├── midway.py          # Table parser + TFC reader
│   │   ├── ue3_common.py      # UE structs
│   │   ├── ue3_properties.py  # Property deserializer
│   │   └── class_handlers/    # Database, Texture2D → JSON/DDS
│   └── mk11/                  # Mortal Kombat 11 (same structure)
├── scripts/                   # Game-specific extractor entry points
└── utils/                     # FileReader, Struct helpers
tests/                         # Pytest suite (gamedata + validation + per-handler)
wiki/                          # GitHub Wiki pages
```

## Documentation

Full documentation is available in the [wiki/](wiki/) folder, designed as a GitHub Wiki:

| Topic | Page |
|-------|------|
| Architecture | [Extraction Pipeline](wiki/Extraction-Pipeline.md) |
| File formats | [File Format Overview](wiki/File-Format-Overview.md) |
| Adding games | [How to Expand](wiki/How-to-Expand.md) |
| IJ2 format | [Injustice 2 Format](wiki/Injustice-2-Format.md) |
| MK11 format | [MK11 Format](wiki/MK11-Format.md) |
| Side-by-side comparison | [Format Comparison](wiki/Format-Comparison.md) |
| IJ2 inventory system | [IJ2 Inventory System](wiki/IJ2-Inventory-System.md) |
| IJ2 gear randomization | [IJ2 Gear Randomization](wiki/IJ2-Gear-Randomization.md) |
| Database handler | [Database Handler](wiki/Database-Handler.md) |
| Texture2D handler | [Texture2D Handler](wiki/Texture2D-Handler.md) |
| UE3 property types | [UE3 Property Types](wiki/UE3-Property-Types.md) |
| Enum reference | [Enums Reference](wiki/Enums-Reference.md) |
| Known issues | [Known Limitations](wiki/Known-Limitations.md) |

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run only gamedata tests (uses files in gamedata/ folder)
python -m pytest tests/test_ij2_gamedata.py tests/test_mk11_gamedata.py -v

# Run pass validation (copies from game install, needs .env)
python -m pytest tests/test_ij2_pass_validation.py tests/test_mk11_pass_validation.py -v
```

Configure game paths in `.env`:
```
IJ2_ASSET_DIR=J:\SteamLibrary\steamapps\common\Injustice2\Asset
MK11_ASSET_DIR=H:\MK11\Asset
```

## Task List

See [TASKLIST.md](TASKLIST.md) for the current completion status and roadmap.

## Requirements

- Python 3.9+
- Oodle DLL: `oo2core_4_win64.dll` (IJ2) and/or `oo2core_5_win64.dll` (MK11) in the working directory
- `python-dotenv` (for tests)
- `dds` library (for PNG conversion from DDS)
- `requests` (for CaseInsensitiveDict)
