"""
Game-agnostic data model for the VFS mount system.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ExportMeta:
    index: int
    name: str
    full_name: str
    path: str
    class_name: str
    outer_index: int
    object_size: int
    object_offset: int
    source_xxx: str
    companion: str = ""
    game: str = ""


@dataclass
class ImportMeta:
    index: int
    name: str
    full_name: str
    class_package: str
    class_name: str


@dataclass
class PackageMeta:
    file_name: str
    source_xxx: str
    companion: str
    game: str
    exports: List[ExportMeta] = field(default_factory=list)
    imports: List[ImportMeta] = field(default_factory=list)
    names: List[str] = field(default_factory=list)
