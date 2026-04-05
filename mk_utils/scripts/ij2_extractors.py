"""
IJ2 extraction script.

Supports:
- .xxx asset packages (databases, textures, etc.)
- Coalesced.ENG/.ini localization/config files

Usage:
    from mk_utils.scripts.ij2_extractors import extract_all, extract_coalesced
    extract_all(["path/to/file.xxx"], output_dir="extracted")
    extract_coalesced("path/to/Coalesced.ENG", output_dir="extracted")
"""

import logging
import os
from typing import Sequence, Tuple, Union

from mk_utils.nrs.ij2.archive import IJ2UE3Asset
from mk_utils.nrs.ij2.class_handlers import ij2_handlers
from mk_utils.nrs.localization_parser import LocalizationParser


def extract_all(
    files: Sequence[Union[str, Tuple[str, str]]],
    output_dir: str = "extracted",
    overwrite: bool = False,
):
    """Extract IJ2 asset files.

    Args:
        files: List of file paths or (xxx_path, tfc_path) tuples.
               For .xxx files without a TFC tuple, auto-discovers .tfc in same directory.
        output_dir: Output directory for extracted files.
        overwrite: Whether to overwrite existing files.
    """
    saved = []
    for file_info in files:
        if isinstance(file_info, tuple):
            file_path, tfc_source = file_info
        else:
            file_path = file_info
            tfc_source = ""

        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".eng", ".ini"):
            saved += extract_coalesced(file_path, output_dir)
            continue

        if ext != ".xxx":
            logging.getLogger("IJ2").warning(f"Skipping unknown file type: {file_path}")
            continue

        # Auto-discover TFC file if not explicitly provided
        if not tfc_source:
            tfc_candidate = os.path.splitext(file_path)[0] + ".tfc"
            if os.path.isfile(tfc_candidate):
                tfc_source = tfc_candidate
                logging.getLogger("IJ2").info(f"Auto-discovered TFC: {tfc_source}")

        logging.getLogger("IJ2").info(f"Parsing {file_path}")

        ij2_asset = IJ2UE3Asset(file_path, tfc_source)
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
        print("Usage: python -m mk_utils.scripts.ij2_extractors <file> [output_dir]")
        print("")
        print("Supports: .xxx asset packages, Coalesced.ENG, Coalesced.ini")
        sys.exit(1)

    files = [sys.argv[1]]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "extracted"

    result = extract_all(files, output_dir)
    print(f"\nExtracted {len(result)} files")
    for f in result:
        print(f"  {f}")
