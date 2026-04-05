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
│   ├── compression/           # Oodle DLL wrappers
│   ├── localization_parser.py # Coalesced AES decryption (shared across games)
│   └── <game>/                # Per-game module (mk11/, ij2/, ...)
│       ├── ue3_common.py      # Structs (header, tables, archive base)
│       ├── archive.py         # .xxx parser + midway builder
│       ├── midway.py          # Table parser + external data reader
│       ├── ue3_properties.py  # Property deserializer
│       └── class_handlers/    # Export processors (Serializable→JSON, Texture2D→DDS)
├── scripts/                   # Per-game extraction entry points
└── utils/                     # FileReader, Struct helpers
tests/                         # Pytest suite (gamedata + validation + per-handler)
boilerplate/                   # Template for adding new game support
```

## Documentation

Full documentation is available on the [GitHub Wiki](https://github.com/thethiny/NRS-Asset-Manager/wiki).

# Run all tests
```bash
python -m pytest tests/ -v
```

# Run only gamedata tests (uses files in gamedata/ folder)
```bash
python -m pytest tests/test_ij2_gamedata.py tests/test_mk11_gamedata.py -v
```

# Run pass validation (copies from game install, needs .env)
```bash
python -m pytest tests/test_ij2_pass_validation.py tests/test_mk11_pass_validation.py -v
```

Configure game paths in `.env`:
```bash
IJ2_ASSET_DIR=/path/to/IJ2/Asset
MK11_ASSET_DIR=/path/to/MK11/Asset
```

## Task List

See [TASKLIST.md](TASKLIST.md) for the current completion status and roadmap.