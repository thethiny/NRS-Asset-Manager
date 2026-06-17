"""
VFS tree node model.
"""

from __future__ import annotations
from typing import Dict, Optional, List

from mk_utils.nrs.vfs.interface import ExportMeta


class VFSNode:
    __slots__ = ("name", "is_dir", "export", "children", "parent")

    def __init__(self, name: str, is_dir: bool = True, export: Optional[ExportMeta] = None,
                 parent: Optional["VFSNode"] = None):
        self.name = name
        self.is_dir = is_dir
        self.export = export
        self.children: Dict[str, VFSNode] = {}
        self.parent = parent

    def get_or_create_child(self, name: str, is_dir: bool = True,
                            export: Optional[ExportMeta] = None) -> "VFSNode":
        if name not in self.children:
            self.children[name] = VFSNode(name, is_dir=is_dir, export=export, parent=self)
        return self.children[name]

    def resolve(self, path: str) -> Optional["VFSNode"]:
        parts = [p for p in path.strip("/").split("/") if p]
        node: Optional[VFSNode] = self
        for p in parts:
            if node is None:
                return None
            node = node.children.get(p)
        return node

    @property
    def vfs_path(self) -> str:
        parts: List[str] = []
        node: Optional[VFSNode] = self
        while node is not None and node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(parts)) if parts else "/"

    @property
    def child_count(self) -> int:
        return len(self.children)

    @property
    def export_count(self) -> int:
        count = 0
        if self.export is not None:
            count = 1
        for child in self.children.values():
            count += child.export_count
        return count

    def sorted_children(self) -> List["VFSNode"]:
        return sorted(self.children.values(), key=lambda n: (not n.is_dir, n.name.lower()))

    def render_tree(self, max_depth: int = -1, _prefix: str = "", _depth: int = 0) -> str:
        if max_depth >= 0 and _depth > max_depth:
            return ""

        lines: List[str] = []
        if _depth == 0:
            lines.append(self.name)

        children = self.sorted_children()
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            connector = "+-- " if is_last else "|-- "

            label = child.name
            if child.export:
                label += f"  [{child.export.class_name}] ({child.export.object_size} bytes)"
            elif child.is_dir and child.children:
                label += f"/ ({child.export_count} exports)"

            lines.append(f"{_prefix}{connector}{label}")

            if child.children and (max_depth < 0 or _depth + 1 < max_depth):
                extension = "    " if is_last else "|   "
                subtree = child.render_tree(max_depth, _prefix + extension, _depth + 1)
                if subtree:
                    lines.append(subtree)

        return "\n".join(lines)

    def remove_children_from_source(self, source_xxx: str):
        to_remove = [
            name for name, child in self.children.items()
            if child.export and child.export.source_xxx == source_xxx
        ]
        for name in to_remove:
            del self.children[name]
        for child in list(self.children.values()):
            child.remove_children_from_source(source_xxx)
        self._prune_empty_dirs()

    def _prune_empty_dirs(self):
        to_remove = [
            name for name, child in self.children.items()
            if child.is_dir and not child.children and child.export is None
        ]
        for name in to_remove:
            del self.children[name]
        for child in self.children.values():
            child._prune_empty_dirs()

    def __repr__(self) -> str:
        return f"VFSNode({self.name!r}, is_dir={self.is_dir}, children={len(self.children)})"
