"""
NRS Asset Manager CLI

Auto-detects game from file header and performs extraction operations.
Supports both individual files and directories (recursive scan).

Usage:
    python main.py header <path>
    python main.py list <path> [--names | --imports | --exports]
    python main.py extract <path> [--output DIR]
    python main.py extract-all <path> [--output DIR]
    python main.py export <path> --name PATTERN [--output DIR] [--regex] [--raw]
    python main.py midway <path> [--output DIR]
    python main.py bulk <path> [--output DIR]
"""

import argparse
import fnmatch
import logging
import os
import re
import sys


# ── Game Registry ────────────────────────────────────────────────────────────

GAME_NAMES = {
    "IJ2UE3Asset": "Injustice 2",
    "MK11UE3Asset": "Mortal Kombat 11",
}

NRS_MAGIC = 0x9E2A83C1


def _get_game_registry():
    """Lazy import to avoid loading all game modules at startup."""
    from mk_utils.nrs.ij2.archive import IJ2UE3Asset
    from mk_utils.nrs.mk11.archive import MK11UE3Asset
    return [
        IJ2UE3Asset,
        MK11UE3Asset,
    ]


def detect_game(path: str):
    """Detect the game from file header. Returns (asset_class, file_version).

    Detection uses file_version at fixed offset 0x04 (u16). This field is at the
    same position in all NRS games. FourCC position varies by game so it cannot
    be used for detection before parsing.
    """
    with open(path, "rb") as f:
        header = f.read(8)

    magic = int.from_bytes(header[0:4], "little")
    if magic != NRS_MAGIC:
        raise ValueError(f"Not an NRS asset file (magic: 0x{magic:08X})")

    file_version = int.from_bytes(header[4:6], "little")

    for asset_class in _get_game_registry():
        if file_version in asset_class.VERSION_RANGE:
            return asset_class, file_version

    raise ValueError(
        f"Unknown game: file_version=0x{file_version:X} ({file_version}). "
        f"No registered game handler matches."
    )


def _print_detected(asset_class, file_version, path, companion=""):
    """Print detection info."""
    game = GAME_NAMES.get(asset_class.__name__, asset_class.__name__)
    print(f"Detected: {game} (version 0x{file_version:X})")
    print(f"File: {path}")
    if companion:
        print(f"Companion: {companion}")
    print()


def _find_companion(xxx_path: str) -> str:
    """Find .tfc or .psf companion file."""
    base = os.path.splitext(xxx_path)[0]
    for ext in (".tfc", ".psf", ".TFC", ".PSF"):
        companion = base + ext
        if os.path.isfile(companion):
            return companion
    return ""


def _get_handlers(asset_class):
    """Get the appropriate handler registry for the game."""
    class_name = asset_class.__name__
    if "IJ2" in class_name:
        from mk_utils.nrs.ij2.class_handlers import ij2_handlers
        return ij2_handlers
    elif "MK11" in class_name:
        from mk_utils.nrs.ue3_common import get_handlers
        import mk_utils.nrs.mk11.class_handlers  # noqa: F401 - registers handlers
        return get_handlers()
    return {}


# ── File Discovery ───────────────────────────────────────────────────────────

def _is_coalesced(path: str) -> bool:
    """Check if a file is a Coalesced localization/config file.

    Must match exactly: coalesced.<ext> (case-insensitive).
    Extensions can be any language code (.ENG, .FRA, .GER, .JPN, etc.) or .ini.
    """
    name = os.path.basename(path).lower()
    return name.startswith("coalesced.") and len(name) > len("coalesced.")


def _is_nrs_asset(path: str) -> bool:
    """Check if a file is an NRS .xxx asset by reading the magic bytes."""
    if not path.lower().endswith(".xxx"):
        return False
    try:
        with open(path, "rb") as f:
            magic = int.from_bytes(f.read(4), "little")
        return magic == NRS_MAGIC
    except (OSError, ValueError):
        return False


def collect_files(path: str) -> list:
    """Collect processable files from a path (file or directory).

    Returns a list of file paths. For directories, recursively scans for:
    - .xxx files with valid NRS magic
    - Coalesced.* files (localization/config)
    """
    if os.path.isfile(path):
        return [path]

    if not os.path.isdir(path):
        raise FileNotFoundError(f"Path not found: {path}")

    files = []
    for root, _, filenames in os.walk(path):
        for name in sorted(filenames):
            full = os.path.join(root, name)
            if _is_coalesced(full) or _is_nrs_asset(full):
                files.append(full)

    if not files:
        raise FileNotFoundError(f"No .xxx or Coalesced files found in {path}")

    return files


# ── Commands ─────────────────────────────────────────────────────────────────

def _for_each_xxx(args, callback):
    """Run callback for each .xxx file in the path. Skips coalesced files."""
    files = collect_files(args.path)
    xxx_files = [f for f in files if f.lower().endswith(".xxx")]

    if not xxx_files:
        print(f"No .xxx files found in {args.path}")
        return

    for f in xxx_files:
        try:
            callback(f)
        except Exception as e:
            logging.getLogger("Main").error(f"{f}: {e}")


def cmd_header(args):
    """Parse and display the file header."""
    def _header(f):
        asset_class, version = detect_game(f)
        companion = _find_companion(f)
        asset = asset_class(f, companion)
        asset.parse(skip_bulk=True)
        _print_detected(asset_class, version, f, companion)
        print(asset.header)
        print()

    _for_each_xxx(args, _header)


def cmd_list(args):
    """List names, imports, exports, or all tables."""
    def _list(f):
        asset_class, version = detect_game(f)
        companion = _find_companion(f)
        asset = asset_class(f, companion)
        midway = asset.parse_all(skip_bulk=True)

        _print_detected(asset_class, version, f, companion)
        print(f"Asset: {midway.file_name}")
        print(f"Names: {len(midway.name_table)} | Imports: {len(midway.import_table)} | Exports: {len(midway.export_table)}")
        print()

        show_all = not args.names and not args.imports and not args.exports

        if args.names or show_all:
            print(f"-- Name Table ({len(midway.name_table)} entries) --")
            for i, name in enumerate(midway.name_table):
                print(f"  [{i:4X}] {name}")
            print()

        if args.imports or show_all:
            print(f"-- Import Table ({len(midway.import_table)} entries) --")
            for i, imp in enumerate(midway.import_table):
                print(f"  [{i:4X}] {imp}")
            print()

        if args.exports or show_all:
            print(f"-- Export Table ({len(midway.export_table)} entries) --")
            for i, export in enumerate(midway.export_table):
                class_name = export.class_.name if export.class_ else "None"
                print(f"  [{i:4X}] {class_name}: {export.full_name} (0x{export.object_size:X} bytes)")
            print()

    _for_each_xxx(args, _list)


def cmd_midway(args):
    """Create the decompressed Midway file (.upk) without processing exports."""
    output = args.output or "."

    def _midway(f):
        asset_class, version = detect_game(f)
        companion = _find_companion(f)
        _print_detected(asset_class, version, f, companion)

        asset = asset_class(f, companion)
        asset.parse(skip_bulk=True)
        midway = asset.to_midway(skip_bulk=True)
        midway.parse(resolve=False, skip_bulk=True)
        midway.to_file(output, midway.file_name)
        print(f"Saved: {output}/{midway.file_name}/{midway.file_name}.upk")

    _for_each_xxx(args, _midway)


def cmd_extract(args):
    """Extract and process all exports using registered handlers."""
    files = collect_files(args.path)
    output = args.output or "extracted"

    xxx_files = [f for f in files if f.lower().endswith(".xxx")]
    coalesced_files = [f for f in files if _is_coalesced(f)]

    total = 0

    for f in xxx_files:
        try:
            asset_class, version = detect_game(f)
            companion = _find_companion(f)
            _print_detected(asset_class, version, f, companion)

            class_name = asset_class.__name__
            if "IJ2" in class_name:
                from mk_utils.scripts.ij2_extractors import extract_all
                result = extract_all([f], output_dir=output, overwrite=args.overwrite)
            elif "MK11" in class_name:
                from mk_utils.scripts.extractors import extract_all
                info = (f, companion) if companion else f
                result = extract_all([info], output_dir=output, overwrite=args.overwrite)
            else:
                continue

            total += len(result)
            for r in result:
                print(f"  {r}")
        except Exception as e:
            logging.getLogger("Main").error(f"{f}: {e}")

    for f in coalesced_files:
        try:
            from mk_utils.scripts.ij2_extractors import extract_coalesced
            print(f"Coalesced: {f}")
            result = extract_coalesced(f, output)
            total += len(result)
        except Exception as e:
            logging.getLogger("Main").error(f"{f}: {e}")

    print(f"\nTotal extracted: {total} files")


def cmd_extract_all(args):
    """Extract all raw exports (no handler processing) to disk."""
    output = args.output or "extracted"

    def _extract_all(f):
        asset_class, version = detect_game(f)
        companion = _find_companion(f)
        _print_detected(asset_class, version, f, companion)

        asset = asset_class(f, companion)
        midway = asset.parse_all(save_path=output, skip_bulk=True)
        print(f"Dumped {len(midway.export_table)} exports to {output}/{midway.file_name}/")

    _for_each_xxx(args, _extract_all)


def cmd_export(args):
    """Extract specific export(s) by name pattern (glob or regex)."""
    output = args.output or "extracted"

    def _export(f):
        asset_class, version = detect_game(f)
        companion = _find_companion(f)
        _print_detected(asset_class, version, f, companion)

        asset = asset_class(f, companion)
        midway = asset.parse_all()
        handlers = _get_handlers(asset_class)

        pattern = args.name
        is_regex = args.regex

        matched = []
        for export in midway.export_table:
            full = export.full_name
            short = export.file_name
            if is_regex:
                if re.search(pattern, full) or re.search(pattern, short):
                    matched.append(export)
            else:
                if fnmatch.fnmatch(full, pattern) or fnmatch.fnmatch(short, pattern):
                    matched.append(export)

        if not matched:
            return

        print(f"Matched {len(matched)} export(s) in {os.path.basename(f)}:")
        for export in matched:
            class_name = export.class_.name if export.class_ else "None"
            handler = handlers.get(class_name.lower()) or handlers.get(class_name)

            if handler and not args.raw:
                try:
                    saved = midway.parse_and_save_export(export, handler["handler_class"], output, overwrite=True)
                    print(f"  [PROCESSED] {export.full_name} -> {saved}")
                except Exception as e:
                    print(f"  [ERROR] {export.full_name}: {e}")
            else:
                data = midway.read_export(export)
                out_dir = os.path.join(output, midway.file_name, "raw_exports")
                os.makedirs(out_dir, exist_ok=True)
                out_file = os.path.join(out_dir, export.file_name)
                with open(out_file, "wb") as fout:
                    fout.write(data)
                print(f"  [RAW] {export.full_name} -> {out_file} ({len(data)} bytes)")

    _for_each_xxx(args, _export)


def cmd_bulk(args):
    """Extract external bulk data (TFC/PSF) for the file."""
    output = args.output or "extracted"

    def _bulk(f):
        asset_class, version = detect_game(f)
        companion = _find_companion(f)
        _print_detected(asset_class, version, f, companion)

        if not companion:
            print(f"No companion file (.tfc/.psf) found")
            return

        asset = asset_class(f, companion)
        midway = asset.parse_all(save_path=output)

        class_name = asset_class.__name__
        if "MK11" in class_name and hasattr(midway, "psf_tables"):
            print(f"PSF tables: {len(midway.psf_tables)}")
            if hasattr(midway, "dump_psfs"):
                midway.dump_psfs(output)
                print(f"PSF data dumped to {output}/")
        elif "IJ2" in class_name and hasattr(midway, "tfc_reader") and midway.tfc_reader:
            print(f"TFC reader available for {midway.file_name}")
            print("TFC data is extracted per-texture during the extract command.")
        else:
            print("No external bulk data to extract.")

    _for_each_xxx(args, _bulk)


# ── CLI Setup ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NRS Asset Manager -- Extract game assets from NetherRealm Studios titles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # header
    p = subparsers.add_parser("header", help="Display file header info")
    p.add_argument("path", help="Path to .xxx file or directory")

    # list
    p = subparsers.add_parser("list", help="List tables (names, imports, exports)")
    p.add_argument("path", help="Path to .xxx file or directory")
    p.add_argument("--names", action="store_true", help="Show only name table")
    p.add_argument("--imports", action="store_true", help="Show only import table")
    p.add_argument("--exports", action="store_true", help="Show only export table")

    # midway
    p = subparsers.add_parser("midway", help="Create decompressed Midway UPK file")
    p.add_argument("path", help="Path to .xxx file or directory")
    p.add_argument("-o", "--output", help="Output directory")

    # extract
    p = subparsers.add_parser("extract", help="Extract and process exports with handlers")
    p.add_argument("path", help="Path to .xxx file, Coalesced file, or directory")
    p.add_argument("-o", "--output", help="Output directory")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing files")

    # extract-all
    p = subparsers.add_parser("extract-all", help="Dump all raw exports to disk")
    p.add_argument("path", help="Path to .xxx file or directory")
    p.add_argument("-o", "--output", help="Output directory")

    # export
    p = subparsers.add_parser("export", help="Extract specific export(s) by name")
    p.add_argument("path", help="Path to .xxx file or directory")
    p.add_argument("-n", "--name", required=True, help="Export name pattern (glob or regex with -r)")
    p.add_argument("-r", "--regex", action="store_true", help="Treat pattern as regex")
    p.add_argument("--raw", action="store_true", help="Extract raw data without handler processing")
    p.add_argument("-o", "--output", help="Output directory")

    # bulk
    p = subparsers.add_parser("bulk", help="Extract external bulk data (TFC/PSF)")
    p.add_argument("path", help="Path to .xxx file or directory")
    p.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(name)s: %(message)s")

    commands = {
        "header": cmd_header,
        "list": cmd_list,
        "midway": cmd_midway,
        "extract": cmd_extract,
        "extract-all": cmd_extract_all,
        "export": cmd_export,
        "bulk": cmd_bulk,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
