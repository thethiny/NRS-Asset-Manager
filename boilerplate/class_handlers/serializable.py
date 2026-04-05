"""
Serializable export handler.

Handles any export whose data is serialized as UE3 properties (name/type/value).
This covers database tables, config objects, asset definitions, presets, etc.
All output as JSON.

Add the export class names this game uses to HANDLED_TYPES.
"""

import json
from mk_utils.nrs.GAME.ue3_properties import UProperty  # TODO: rename GAME
from mk_utils.nrs.ue3_common import ClassHandler


class GameSerializableHandler(ClassHandler):
    # TODO: Add the lowercase class names this handler should process.
    # These are the names from the import table that appear as export class types.
    # Examples from IJ2: "dcf2assetdefinitions", "capasset", "colorpaletteasset"
    # Examples from MK11: "mk11unlockdata", "mk11itemdatabase"
    HANDLED_TYPES = {
        # "somedatabasetype",
        # "someconfigtype",
    }

    def parse(self):
        data = {}
        while self.mm.tell() < self.mm.size():
            result = UProperty.parse_once(self.mm, self.name_table, True)
            if result is None:
                break
            prop_dict, array_index = result
            data.update(prop_dict)
        return data

    @classmethod
    def make_save_path(cls, export, asset_name: str, save_path: str):
        save_path = super().make_save_path(export, asset_name, save_path)
        return save_path + ".json"

    def save(self, data, export, asset_name, save_dir, *args, **kwargs):
        save_file = self.make_save_path(export, asset_name, save_dir)
        with open(save_file, "w+") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return save_file
