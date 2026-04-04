"""
IJ2 extraction script.

Supports:
- .xxx asset packages (databases, textures, etc.)
- Coalesced.ENG/.ini localization/config files

Usage:
    from mk_utils.scripts.ij2_extractors import extract_all, extract_coalesced
    extract_all(["path/to/file.xxx"], output_dir="extracted", oodle_dll="path/to/oo2core_4_win64.dll")
    extract_coalesced("path/to/Coalesced.ENG", output_dir="extracted")
"""

import logging
import os
from typing import List

from mk_utils.nrs.ij2.archive import IJ2UE3Asset
from mk_utils.nrs.ij2.class_handlers import ij2_handlers
from mk_utils.nrs.localization_parser import LocalizationParser


def extract_all(
    files: List[str],
    output_dir: str = "extracted",
    oodle_dll: str = "./oo2core_4_win64.dll",
    overwrite: bool = False,
):
    saved = []
    for file_path in files:
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".eng", ".ini"):
            saved += extract_coalesced(file_path, output_dir)
            continue

        if ext != ".xxx":
            logging.getLogger("IJ2").warning(f"Skipping unknown file type: {file_path}")
            continue

        logging.getLogger("IJ2").info(f"Parsing {file_path}")

        ij2_asset = IJ2UE3Asset(file_path, oodle_dll=oodle_dll)
        midway_file = ij2_asset.parse_all(save_path=output_dir)

        for export in midway_file.export_table:
            file_type = export.class_.name if export.class_ else ""
            handler = ij2_handlers.get(file_type.lower())
            if not handler:
                continue

            handler_class = handler["handler_class"]

            try:
                saved_file = midway_file.parse_and_save_export(
                    export, handler_class, output_dir, overwrite
                )
                saved.append(saved_file)
            except Exception as e:
                logging.getLogger("IJ2").error(
                    f"Failed to parse export {export.file_name}: {e}"
                )

    return saved


def extract_coalesced(file_path: str, output_dir: str = "extracted"):
    logging.getLogger("IJ2").info(f"Extracting Coalesced: {file_path}")
    saved = []

    parser = LocalizationParser(file_path, decrypted_out_dir=output_dir)
    for path, content in parser.extract_files(save_dir=output_dir):
        saved.append(path)

    logging.getLogger("IJ2").info(f"Extracted {len(saved)} files from {file_path}")
    return saved


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m mk_utils.scripts.ij2_extractors <file> [output_dir] [oodle_dll]")
        print("")
        print("Supports: .xxx asset packages, Coalesced.ENG, Coalesced.ini")
        sys.exit(1)

    files = [sys.argv[1]]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "extracted"
    oodle_dll = sys.argv[3] if len(sys.argv) > 3 else "./oo2core_4_win64.dll"

    result = extract_all(files, output_dir, oodle_dll)
    print(f"\nExtracted {len(result)} files")
    for f in result:
        print(f"  {f}")
