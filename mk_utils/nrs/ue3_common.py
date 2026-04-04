import os
import logging

from ctypes import c_ubyte, c_uint32, c_uint16
from typing import Any, Iterable, List, Tuple, Type, TypedDict

from mk_utils.utils.filereader import FileReader
from mk_utils.utils.structs import Struct
from requests.utils import CaseInsensitiveDict


class GUID(Struct):
    __slots__ = ()
    _fields_ = [
        ("Data1", c_uint32),
        ("Data2", c_uint16),
        ("Data3", c_uint16),
        ("Data4", c_ubyte * 8),
    ]

    def __str__(self):
        d1 = f"{self.Data1:08X}"
        d2 = f"{self.Data2:04X}"
        d3 = f"{self.Data3:04X}"
        d4 = "".join(f"{b:02X}" for b in self.Data4)
        return f"{d1}-{d2}-{d3}-{d4[:4]}-{d4[4:]}"

class UETableEntryBase:
    @property
    def file_name(self):
        raise NotImplementedError(f"Abstract Class Method not implemented!")

    @property
    def file_dir(self):
        raise NotImplementedError(f"Abstract Class Method not implemented!")

    @property
    def full_name(self): 
        raise NotImplementedError(f"Abstract Class Method not implemented!")

    @property
    def path(self): 
        raise NotImplementedError(f"Abstract Class Method not implemented!")

class ClassHandler(FileReader):
    HANDLED_TYPES: Iterable = {}

    def __init__(self, file_path, name_table: List[str]) -> None:
        super().__init__(file_path)

        self.name_table = name_table

    def parse(self):
        raise NotImplementedError(f"Implement me")

    @classmethod
    def make_save_path(cls, export: UETableEntryBase, asset_name: str, save_path: str):
        if not save_path:
            raise ValueError(f"Missing save_path!")

        save_path = os.path.join(save_path, asset_name, "parsed_exports", export.path.lstrip("/"))
        os.makedirs(save_path, exist_ok=True)
        return os.path.join(save_path, export.file_name)

    def save(self, data: Any, export: UETableEntryBase, asset_name: str, save_path: str, asset_instance) -> str:
        raise NotImplementedError(f"Implement me")

    @classmethod
    def register_handlers(cls):
        for type_ in cls.HANDLED_TYPES:
            logging.getLogger("ClassHandler").debug(f"Type {type_} handled by {cls}.")
            assign_handlers(cls, type_)


class ClassHandlerItemType(TypedDict):
    handler_class: Type[ClassHandler]
    args: Tuple[Any, ...]


ClassHandlerType = CaseInsensitiveDict[ClassHandlerItemType]
class_handlers: ClassHandlerType = CaseInsensitiveDict()


def assign_handlers(handler: Type[ClassHandler], handler_class: str, *handler_args: Any):
    if handler_class in class_handlers:
        raise ValueError(f"Clashing with handler {handler_class}")

    class_handlers[handler_class] = {
        "handler_class": handler,
        "args": handler_args,
    }


def get_handlers(): # TODO: This should accept a GAME and handle the registration and class_handlers should be per game
    return class_handlers
