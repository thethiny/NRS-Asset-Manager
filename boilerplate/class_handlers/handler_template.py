"""
ClassHandler template.

Copy this file and implement the required methods to create a new export handler.
Each handler processes a specific set of export class types (e.g., Texture2D,
SkeletalMesh, NRSAudioBank, etc.).

Required overrides:
- HANDLED_TYPES: Set of lowercase class names this handler processes
- parse(): Read and interpret the export's raw data
- make_save_path(): Determine the output file path
- save(): Write the parsed data to disk

The handler receives:
- self.mm: Memory-mapped export data (positioned at byte 0 of the export)
- self.name_table: The file's name table (list of strings)
"""

import os
from mk_utils.nrs.ue3_common import ClassHandler


class GameCustomHandler(ClassHandler):
    # Set of lowercase export class names this handler processes.
    # These must match the resolved class names from the import table.
    HANDLED_TYPES = {
        # "texture2d",
        # "nrsaudiobank",
        # "skeletalmesh",
    }

    def parse(self):
        """Parse the export's raw binary data.

        self.mm is positioned at byte 0 of the export data.
        self.mm.size() is the total export data size.
        self.name_table is available for name lookups.

        Returns: Any data structure that save() knows how to write.
        """
        raise NotImplementedError("Implement parse()")

    @classmethod
    def make_save_path(cls, export, asset_name: str, save_path: str):
        """Determine the output file path for this export.

        Args:
            export: The export table entry (has .file_name, .file_dir, .full_name)
            asset_name: The midway asset's file_name
            save_path: The base output directory

        Returns: Full path to the output file (with extension).
        """
        save_path = super().make_save_path(export, asset_name, save_path)
        # TODO: Add the appropriate extension
        return save_path + ".bin"

    def save(self, data, export, asset_name, save_dir, instance, *args, **kwargs):
        """Write the parsed data to disk.

        Args:
            data: The return value from parse()
            export: The export table entry
            asset_name: The midway asset's file_name
            save_dir: The base output directory
            instance: The MidwayAsset instance (for accessing mm, name_table,
                      tfc_reader, psf_reader, etc.)

        Returns: Path to the saved file.
        """
        save_file = self.make_save_path(export, asset_name, save_dir)
        # TODO: Write the data
        with open(save_file, "wb") as f:
            f.write(data)
        return save_file
