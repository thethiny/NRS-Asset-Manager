import json
from mk_utils.nrs.ij2.ue3_properties import UProperty
from mk_utils.nrs.ue3_common import ClassHandler


class IJ2DatabaseHandler(ClassHandler):
    # Accept all DCF2 / CAP database types
    HANDLED_TYPES = {
        "dcf2assetdefinitions",
        "dcf2gearrarity",
        "dcf2dialogconfigdata",
        "dcf2billboardconfigdata",
        "dcf2storydata",
        "dcf2storydatashowbuild",
        "capasset",
        "capitempresetsasset",
        "capmaterialasset",
        "colorpaletteasset",
        "dcf2cappresets",
        "dcf2capinfotable",
        "dcf2materialpalettetable",
        "mktweakvars",
        "umktweakvars",
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
        with open(save_file, "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return save_file
