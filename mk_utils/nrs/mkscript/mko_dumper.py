"""
MKO file dumper — exports parsed MKO data to JSON.
"""

import json
import logging
import os
from typing import Optional

from mk_utils.nrs.mkscript.mko_parser import MKOParser
from mk_utils.nrs.mkscript.mko_common import FIXUP_TYPE_NAMES, ASSET_TYPE_NAMES

logger = logging.getLogger("MKODumper")


def dump_mko(parser: MKOParser, output_dir: str, file_name: str = "") -> str:
    if not parser.parsed:
        parser.parse()

    if not file_name:
        file_name = "mko_output"

    out_dir = os.path.join(output_dir, file_name)
    os.makedirs(out_dir, exist_ok=True)

    assert parser.header is not None
    h = parser.header
    result = {
        "header": {
            "endian": "LE" if h.endian_flag == 1 else "BE",
            "glue_hash": f"0x{h.glue_hash:08X}",
            "num_functions": h.num_functions,
            "num_static_variables": h.num_static_variables,
            "num_dynamic_variables": h.num_dynamic_variables,
            "num_externs": h.num_externs,
            "num_extern_variables": h.num_extern_variables,
            "num_assets": h.num_assets,
            "bytecode_size": h.bytecode_data_len,
            "string_table_size": h.string_argument_table_len,
            "stack_data_size": h.stack_data_len,
            "num_global_fixups": h.global_fixup_list_len,
            "num_tweakvars": h.num_tweakvars,
            "num_source_files": h.num_source_files,
        },
        "functions": [
            {
                "name": f.name,
                "name_hash": f"0x{f.header.name_hash:08X}",
                "num_args": f.header.num_args,
                "stack_size": f.header.stack_size,
                "scratch_size": f.header.scratch_size,
                "bytecode_size": f.header.bytecode_size,
                "local_fixup_count": f.header.local_fixup_count,
                "checked_object_count": f.header.checked_object_count,
            }
            for f in parser.functions
        ],
        "static_variables": [
            {
                "name_hash": f"0x{v.name_hash:08X}",
                "data_size": v.data_size,
                "stride": v.stride,
            }
            for v in parser.static_variables
        ],
        "dynamic_variables": [
            {
                "name_hash": f"0x{v.name_hash:08X}",
                "data_size": v.data_size,
                "stride": v.stride,
            }
            for v in parser.dynamic_variables
        ],
        "externs": [
            {
                "file": e.file_name,
                "name": e.name,
                "name_hash": f"0x{e.header.name_hash:08X}",
            }
            for e in parser.externs
        ],
        "assets": [
            {
                "name": a.name,
                "type": a.asset_type,
                "hash": f"0x{a.header.hash:08X}",
            }
            for a in parser.assets
        ],
        "global_fixups": [
            {
                "type": FIXUP_TYPE_NAMES.get(fx.fixup_type, f"Unknown({fx.fixup_type})"),
                "offset": fx.offset,
                "src_value": fx.src_value,
            }
            for fx in parser.global_fixups
        ],
    }

    json_path = os.path.join(out_dir, f"{file_name}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    logger.info(f"Dumped {file_name} to {json_path}")
    return json_path
