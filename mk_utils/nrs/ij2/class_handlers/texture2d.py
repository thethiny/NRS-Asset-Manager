import json
import logging
from mk_utils.nrs.ij2.ue3_properties import UProperty
from mk_utils.nrs.ue3_common import ClassHandler


class IJ2Texture2DHandler(ClassHandler):
    HANDLED_TYPES = {
        "Texture2D",
    }

    def parse(self):
        metadata = {}
        while self.mm.tell() != self.mm.size():
            result = UProperty.parse_once(self.mm, self.name_table, True)
            if result is None:
                break
            prop_dict, array_index = result
            metadata.update(prop_dict)

        return {"meta": metadata}

    @classmethod
    def make_save_path(cls, export, asset_name: str, save_path: str):
        save_path = super().make_save_path(export, asset_name, save_path)
        return save_path.rsplit(".", 1)[0].strip() + ".json"

    def save(self, data, export, asset_name, save_dir, *args, **kwargs):
        save_file = self.make_save_path(export, asset_name, save_dir)
        with open(save_file, "w+") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.getLogger("IJ2Texture2D").info(f"Texture metadata saved to {save_file}")
        return save_file
