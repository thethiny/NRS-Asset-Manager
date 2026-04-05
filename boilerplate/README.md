# New Game Boilerplate

Copy this entire folder into `mk_utils/nrs/<game_code>/` and fill in the placeholders.

## Files to implement

1. `enums.py` - Game-specific enums (compression flags, pixel formats)
2. `ue3_common.py` - Binary structs (header, archive base, table entries)
3. `archive.py` - Compressed .xxx parser and midway builder
4. `midway.py` - Decompressed midway format parser
5. `ue3_properties.py` - UE3 property deserializer
6. `class_handlers/__init__.py` - Handler registration
7. `class_handlers/database.py` - Database export handler

## After implementing

1. Add the game to `main.py`'s `_get_game_registry()` and `GAME_NAMES`
2. Create `mk_utils/scripts/<game>_extractors.py`
3. Create tests in `tests/<game>/`
4. Add the Oodle DLL to the project root
