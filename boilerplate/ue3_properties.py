"""
TODO: Game-specific UE3 property parser.

Start by copying from the closest game version (IJ2 or MK11) and adjust:
- Property size field: IJ2 uses u32 size + u32 array_index, MK11 uses u64 size
- FName reads: both use u64 but IJ2 treats as u32+u32 (name + instance number)
- Known array/map key types specific to this game
"""

import logging
from ctypes import c_char, c_float, c_uint32, c_uint64
from typing import Dict, Tuple, Type

from mk_utils.nrs.ue3_common import GUID
from mk_utils.nrs.GAME.enums import enumMaps  # TODO: rename GAME
from mk_utils.utils.structs import Struct

warned_classes = set()


class UProperty:
    def __init__(self) -> None:
        self.name: str = ""
        self.type: str = ""
        self.value: Dict = {}

    @classmethod
    def read_type(cls, file_handle, name_table) -> Tuple[str, str]:
        pos = file_handle.tell()
        name = Struct.read_buffer(file_handle, c_uint64)
        if name >= len(name_table):
            raise IndexError(
                f"Name index {name} (0x{name:X}) out of range at offset 0x{pos:X}. "
                f"Name table has {len(name_table)} entries."
            )
        name = name_table[name]
        if name == "None":
            return "", ""

        type = Struct.read_buffer(file_handle, c_uint64)
        if type >= len(name_table):
            raise IndexError(
                f"Type index {type} (0x{type:X}) out of range at offset 0x{pos+8:X}. "
                f"Name table has {len(name_table)} entries."
            )
        type = name_table[type]

        return name, type

    @classmethod
    def _fix_property_size(cls):
        if cls == BoolProperty:
            return 4
        raise ValueError(f"Error: Property Size was 0 for {cls}!")

    @classmethod
    def read(cls, file_handle, name_table, headers: bool = True, key_name: str = ""):
        # TODO: Check if this game uses u32+u32 (IJ2) or u64 (MK11) for size
        property_size = Struct.read_buffer(file_handle, c_uint32)
        array_index = Struct.read_buffer(file_handle, c_uint32)
        if property_size == 0:
            property_size = cls._fix_property_size()

        parsed_headers = {}
        if headers:
            parsed_headers = cls.read_headers(file_handle, name_table)
            s_t = StructPropertyMap.get(parsed_headers.get("struct_type", ""))
            if s_t:
                cls = s_t

        start_tell = file_handle.tell()
        data = cls.read_data(
            file_handle,
            name_table=name_table,
            headers=headers,
            read_size=property_size,
            key_name=key_name,
            **parsed_headers,
        )
        end_tell = file_handle.tell()
        total_read = end_tell - start_tell

        if property_size != -1 and total_read != property_size:
            raise ValueError(f"Read {total_read} | Expected {property_size}")

        return data, array_index

    @classmethod
    def read_headers(cls, file_handle, name_table, *args, **kwargs):
        return {}

    @classmethod
    def read_data(cls, file_handle, name_table, headers, *args, **kwargs):
        raise NotImplementedError(f"Implement me!")

    @classmethod
    def parse_once(cls, file_handle, name_table, headers):
        name, type_ = cls.read_type(file_handle, name_table)
        if not name:
            return None

        type_class = PropertyMap.get(type_, None)
        if not type_class:
            raise NotImplementedError(f"Couldn't match Property Type {type_}!")

        value, array_index = type_class.read(
            file_handle, name_table=name_table, headers=True, key_name=name
        )
        return {name: value}, array_index


# ── Property Types ───────────────────────────────────────────────────────────
# TODO: Add/remove types as needed for this game.

class StrProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        string_size = Struct.read_buffer(file_handle, c_uint32)
        return Struct.read_buffer(file_handle, c_char * string_size).decode("ascii")


class NameProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, name_table, *args, **kwargs):
        return name_table[Struct.read_buffer(file_handle, c_uint64)]


class IntProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        return Struct.read_buffer(file_handle, read_size, signed=True)


class FloatProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        return Struct.read_buffer(file_handle, c_float)


class BoolProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        return Struct.read_buffer(file_handle, c_uint32) == 1


class DWordProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        return Struct.read_buffer(file_handle, read_size)


class QWordProperty(DWordProperty): ...


class ObjectProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        return Struct.read_buffer(file_handle, read_size, signed=True)


class ByteProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        return Struct.read_buffer(file_handle, read_size)


class EnumProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, key_name, *args, **kwargs):
        value = Struct.read_buffer(file_handle, read_size)
        enum_class = enumMaps.get(key_name)
        if enum_class:
            return f"{enum_class.__name__}::{enum_class(value).name}"
        return f"{key_name}::{value}"


class StructProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, name_table, headers, read_size: int = -1, *args, **kwargs):
        object = {}
        start_pos = file_handle.tell()
        use_size = read_size > 0

        while True:
            if use_size and file_handle.tell() >= start_pos + read_size:
                break
            result = cls.parse_once(file_handle, name_table, headers)
            if result is None:
                break
            prop_dict, array_index = result
            for key, val in prop_dict.items():
                if array_index > 0:
                    if isinstance(object.get(key), list):
                        object[key].append(val)
                    elif key in object:
                        object[key] = [object[key], val]
                    else:
                        object[key] = val
                else:
                    object[key] = val
        return object

    @classmethod
    def read_headers(cls, file_handle, name_table):
        struct_type = NameProperty.read_data(file_handle, name_table)
        return {"struct_type": struct_type}


class FGuid(StructProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        return str(Struct.read_buffer(file_handle, GUID))


class ArrayProperty(UProperty):
    # TODO: Add game-specific array key whitelists
    STRING_ARRAY_KEYS: set = set()
    NAME_ARRAY_KEYS: set = set()
    INT_ARRAY_KEYS: set = set()

    @classmethod
    def read_data(cls, file_handle, name_table, headers: bool = True, key_name: str = "", read_size: int = -1, *args, **kwargs):
        elements_count = Struct.read_buffer(file_handle, c_uint32)
        data = []

        if key_name in cls.STRING_ARRAY_KEYS:
            subtype = StrProperty
            sub_args = ()
        elif key_name in cls.NAME_ARRAY_KEYS:
            subtype = NameProperty
            sub_args = (name_table,)
        elif key_name in cls.INT_ARRAY_KEYS:
            subtype = DWordProperty
            sub_args = (c_uint32,)
        else:
            if key_name not in warned_classes:
                logging.getLogger("Database").warning(
                    f"Array type {key_name} is not officially supported! Proceed with caution!"
                )
                warned_classes.add(key_name)
            subtype = StructProperty
            sub_args = (name_table, False)

        for i in range(elements_count):
            value = subtype.read_data(file_handle, *sub_args)
            data.append(value)

        return data


class MapProperty(UProperty):
    # TODO: Add game-specific map key whitelists
    STRING_KEY_MAPS: set = set()
    NAME_KEY_MAPS: set = set()
    STRUCT_KEY_MAPS: set = set()

    @classmethod
    def read_data(cls, file_handle, name_table, headers, key_name: str = "", read_size: int = -1, *args, **kwargs):
        elements = Struct.read_buffer(file_handle, c_uint32)
        # TODO: Implement map parsing based on key_name
        raise NotImplementedError(f"Unsupported Map type: {key_name}")


# ── Property Map ─────────────────────────────────────────────────────────────

PropertyMap: Dict[str, Type[UProperty]] = {
    "StrProperty": StrProperty,
    "IntProperty": IntProperty,
    "FloatProperty": FloatProperty,
    "BoolProperty": BoolProperty,
    "StructProperty": StructProperty,
    "ArrayProperty": ArrayProperty,
    "EnumProperty": EnumProperty,
    "DWordProperty": DWordProperty,
    "QWordProperty": QWordProperty,
    "MapProperty": MapProperty,
    "NameProperty": NameProperty,
    "ObjectProperty": ObjectProperty,
    "ByteProperty": ByteProperty,
}

StructPropertyMap: Dict[str, Type[StructProperty]] = {
    "FGuid": FGuid,
    # TODO: Add game-specific struct types (FVector2D, FLinearColor, etc.)
}
