"""
IJ2 UE3 Properties parser.

Based on the MK11 version but adapted for IJ2's property format.
IJ2 being an older game may have slight differences in property encoding.
"""

import logging
from ctypes import c_char, c_float, c_uint32, c_uint64
from typing import Dict, Tuple, Type

from mk_utils.nrs.ue3_common import GUID
from mk_utils.nrs.ij2.enums import enumMaps
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
        # IJ2 uses u32 size + u32 array_index (NOT u64 size like MK11).
        # MK11 gets away with u64 because array_index is always 0 there.
        # In IJ2, array_index can be non-zero (e.g., C-style fixed arrays like digest[16]).
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


class StrProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        string_size = Struct.read_buffer(file_handle, c_uint32)
        string = Struct.read_buffer(file_handle, c_char * string_size).decode("ascii")
        return string


class NameProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, name_table, *args, **kwargs):
        name = Struct.read_buffer(file_handle, c_uint64)
        name = name_table[name]
        return name


class IntProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        value = Struct.read_buffer(file_handle, read_size, signed=True)
        return value


class EnumProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, key_name, *args, **kwargs):
        value = Struct.read_buffer(file_handle, read_size)
        enum_class = enumMaps.get(key_name)
        if enum_class:
            return f"{enum_class.__name__}::{enum_class(value).name}"
        return f"{key_name}::{value}"


class DWordProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        value = Struct.read_buffer(file_handle, read_size)
        return value


class QWordProperty(DWordProperty): ...


class ObjectProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        value = Struct.read_buffer(file_handle, read_size, signed=True)
        return value


class WeakUObjectHandleProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        return str(Struct.read_buffer(file_handle, GUID))


class ByteProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, read_size, *args, **kwargs):
        value = Struct.read_buffer(file_handle, read_size)
        return value


class MultiDWordProperty(DWordProperty):
    @classmethod
    def read_data(cls, file_handle, key_size, val_size, *args, **kwargs):
        key = Struct.read_buffer(file_handle, key_size)
        value = Struct.read_buffer(file_handle, val_size)
        return {key: value}


class MapProperty(UProperty):
    # Maps with FString keys
    STRING_KEY_MAPS = {
        "mIntroTracks",
        "mPresets",
    }
    # Maps with FName keys (u64 name index) + struct values
    NAME_KEY_MAPS = {
        "mColorPaletteTable",
    }
    # Maps with struct keys AND struct values: TMap<Struct, Struct>
    STRUCT_KEY_MAPS = {
        "mCAPInfoTable",
        "mHellboyHeadIndexTable",
        "MD5HashToItemMap",
    }

    @classmethod
    def read_data(cls, file_handle, name_table, headers, key_name: str = "", read_size: int = -1, *args, **kwargs):
        start_pos = file_handle.tell()
        elements = Struct.read_buffer(file_handle, c_uint32)

        # Calculate per-entry size for size-based struct termination
        data_size = read_size - 4 if read_size > 0 else -1  # subtract count field
        entry_size = data_size // elements if elements > 0 and data_size > 0 else -1

        if key_name in cls.STRING_KEY_MAPS:
            object = {}
            for i in range(elements):
                key = StrProperty.read_data(file_handle)
                value = StructProperty.read_data(file_handle, name_table, False)
                object[key] = value
            return object
        elif key_name in cls.NAME_KEY_MAPS:
            object = {}
            # Name key = 8 bytes, so value_size = entry_size - 8
            value_size = entry_size - 8 if entry_size > 8 else -1
            for i in range(elements):
                key = NameProperty.read_data(file_handle, name_table)
                value = StructProperty.read_data(file_handle, name_table, False, read_size=value_size)
                object.setdefault(key, []).append(value)
            return object
        elif key_name in cls.STRUCT_KEY_MAPS:
            # Fixed-size struct entries with size-based termination.
            # Some maps are TMap<Struct, Struct> (key+value), others are TMap<FMD5Hash, Struct>.
            # Use entry_size to bound the read. If the struct consumes the entire entry,
            # there is no separate value (it's a single struct entry).
            result = []
            for i in range(elements):
                entry_start = file_handle.tell()
                entry = StructProperty.read_data(file_handle, name_table, False, read_size=entry_size)
                # If we didn't consume the full entry, read the remaining as value struct
                consumed = file_handle.tell() - entry_start
                remaining = entry_size - consumed if entry_size > 0 else 0
                if remaining > 8:  # enough for at least one property header
                    value = StructProperty.read_data(file_handle, name_table, False, read_size=remaining)
                    result.append({"key": entry, "value": value})
                else:
                    if remaining > 0:
                        file_handle.seek(remaining, 1)  # skip padding
                    result.append(entry)
            return result
        else:
            raise NotImplementedError(f"Unsupported Map type: {key_name}")


class FloatProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        value = Struct.read_buffer(file_handle, c_float)
        return value


class BoolProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        value = Struct.read_buffer(file_handle, c_uint32)
        return value == 1


class StructProperty(UProperty):
    @classmethod
    def read_data(cls, file_handle, name_table, headers, read_size: int = -1, *args, **kwargs):
        object = {}
        start_pos = file_handle.tell()
        use_size = read_size > 0

        while True:
            # Size-based termination: if we've consumed enough bytes, stop
            if use_size and file_handle.tell() >= start_pos + read_size:
                break

            result = cls.parse_once(file_handle, name_table, headers)
            if result is None:
                break  # None always terminates a struct

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
                    if key in object and isinstance(object[key], list):
                        object[key].append(val)
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


class FVector2D(StructProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        x = Struct.read_buffer(file_handle, c_float)
        y = Struct.read_buffer(file_handle, c_float)
        return {"X": x, "Y": y}


class FLinearColor(StructProperty):
    @classmethod
    def read_data(cls, file_handle, *args, **kwargs):
        r = Struct.read_buffer(file_handle, c_float)
        g = Struct.read_buffer(file_handle, c_float)
        b = Struct.read_buffer(file_handle, c_float)
        a = Struct.read_buffer(file_handle, c_float)
        return {"R": r, "G": g, "B": b, "A": a}


class ArrayProperty(UProperty):
    # Arrays of simple string values (TArray<FString>)
    STRING_ARRAY_KEYS = {
        "mAssets",
        "mCompletionUnlock",
        "mCompletionUnlockAfterComplete",
        "mItemHashes",
        "TextureNames",
    }
    # Arrays of name values (TArray<FName>)
    NAME_ARRAY_KEYS = {
        "BaseLayerNames",
    }
    # Arrays of int/object ref values (TArray<int> / TArray<ObjectRef>)
    INT_ARRAY_KEYS = {
        "WorstCaseItems",
        "Meshes",
    }

    @classmethod
    def read_data(cls, file_handle, name_table, headers: bool = True, key_name: str = "", read_size: int = -1, *args, **kwargs):
        elements_count = Struct.read_buffer(file_handle, c_uint32)
        data = []

        # Calculate per-element size for struct arrays
        data_bytes = read_size - 4 if read_size > 0 else -1  # subtract count field
        elem_size = data_bytes // elements_count if elements_count > 0 and data_bytes > 0 else -1

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
            if key_name not in warned_classes and key_name not in [
                "mItems", "mAssetGroups", "ReferencedObjects",
            ]:
                logging.getLogger("IJ2Database").warning(
                    f"Array type {key_name} is not officially supported for IJ2! Proceed with caution!"
                )
                warned_classes.add(key_name)
            subtype = StructProperty
            sub_args = (name_table, False)  # headers=False

        for i in range(elements_count):
            value = subtype.read_data(file_handle, *sub_args)
            data.append(value)

        return data


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
    "WeakUObjectHandleProperty": WeakUObjectHandleProperty,
    "ByteProperty": ByteProperty,
}

StructPropertyMap: Dict[str, Type[StructProperty]] = {
    "FGuid": FGuid,
    "FVector2D": FVector2D,
    "FLinearColor": FLinearColor,
}
