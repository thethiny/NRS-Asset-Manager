"""
VFS Mount Manager.

Mounts .xxx files, extracts metadata, and provides a virtual filesystem
for browsing game assets. Midway buffers are cached on-demand only when
an export is actually opened.
"""

import logging
import os
from typing import Dict, List, Optional

from mk_utils.nrs.vfs.interface import ExportMeta, ImportMeta, PackageMeta
from mk_utils.nrs.vfs.tree import VFSNode
from mk_utils.nrs.vfs.cache import MidwayCache

logger = logging.getLogger("VFS")

GAME_NAMES = {
    "IJ2UE3Asset": "IJ2",
    "MK11UE3Asset": "MK11",
}

NRS_MAGIC = 0x9E2A83C1


def _detect_game(path: str):
    from main import detect_game, _find_companion
    asset_class, version = detect_game(path)
    companion = _find_companion(path)
    game: str = GAME_NAMES.get(asset_class.__name__, asset_class.__name__)
    return asset_class, companion, game


def _extract_metadata(midway, xxx_path: str, companion: str, game: str) -> PackageMeta:
    exports = []
    for i, exp in enumerate(midway.export_table):
        class_name = ""
        if hasattr(exp, "class_") and exp.class_:
            class_name = exp.class_.name
        exports.append(ExportMeta(
            index=i,
            name=exp.name if hasattr(exp, "name") else "",
            full_name=exp.full_name,
            path=exp.path,
            class_name=class_name,
            outer_index=exp.outer_index,
            object_size=exp.object_size,
            object_offset=exp.object_offset,
            source_xxx=xxx_path,
            companion=companion,
            game=game,
        ))

    imports = []
    for i, imp in enumerate(midway.import_table):
        class_pkg = ""
        class_nm = ""
        if hasattr(imp, "class_package_resolved"):
            class_pkg = imp.class_package_resolved or ""
        if hasattr(imp, "class_name_resolved"):
            class_nm = imp.class_name_resolved or ""
        elif hasattr(imp, "name") and hasattr(imp, "package"):
            class_nm = imp.name or ""
        imports.append(ImportMeta(
            index=i,
            name=imp.name if hasattr(imp, "name") else "",
            full_name=imp.full_name,
            class_package=class_pkg,
            class_name=class_nm,
        ))

    names = list(midway.name_table) if hasattr(midway, "name_table") else []

    return PackageMeta(
        file_name=midway.file_name,
        source_xxx=xxx_path,
        companion=companion,
        game=game,
        exports=exports,
        imports=imports,
        names=names,
    )


class MountManager:
    def __init__(self, max_cached_midways: int = 4):
        self._mounted: Dict[str, PackageMeta] = {}
        self._cache = MidwayCache(max_cached_midways)
        self._tree = VFSNode("/", is_dir=True)

    @property
    def tree(self) -> VFSNode:
        return self._tree

    @property
    def mounted_count(self) -> int:
        return len(self._mounted)

    @property
    def total_exports(self) -> int:
        return sum(len(m.exports) for m in self._mounted.values())

    def mount(self, xxx_path: str) -> PackageMeta:
        xxx_path = os.path.abspath(xxx_path)
        if xxx_path in self._mounted:
            return self._mounted[xxx_path]

        asset_class, companion, game = _detect_game(xxx_path)
        asset = asset_class(xxx_path, companion)
        midway = asset.parse_all(skip_bulk=True)

        meta = _extract_metadata(midway, xxx_path, companion, game)
        self._mounted[xxx_path] = meta
        self._insert_into_tree(meta)

        logger.info(f"Mounted [{game}] {meta.file_name}: {len(meta.exports)} exports")
        return meta

    def mount_directory(self, dir_path: str) -> List[PackageMeta]:
        results = []
        for name in sorted(os.listdir(dir_path)):
            if not name.lower().endswith(".xxx"):
                continue
            full = os.path.join(dir_path, name)
            try:
                with open(full, "rb") as f:
                    magic = int.from_bytes(f.read(4), "little")
                if magic != NRS_MAGIC:
                    continue
                results.append(self.mount(full))
            except Exception as e:
                logger.warning(f"Failed to mount {name}: {e}")
        return results

    def unmount(self, xxx_path: str):
        xxx_path = os.path.abspath(xxx_path)
        meta = self._mounted.pop(xxx_path, None)
        if meta is None:
            return
        self._cache.evict(xxx_path)
        self._tree.remove_children_from_source(xxx_path)
        logger.info(f"Unmounted {meta.file_name}")

    def ls(self, vfs_path: str = "/") -> List[VFSNode]:
        node = self._tree.resolve(vfs_path)
        if node is None:
            return []
        return node.sorted_children()

    def render_tree(self, vfs_path: str = "/", max_depth: int = -1) -> str:
        node = self._tree.resolve(vfs_path)
        if node is None:
            return f"Path not found: {vfs_path}"
        return node.render_tree(max_depth)

    def open_export(self, export: ExportMeta) -> bytes:
        buf = self._cache.get(export.source_xxx)
        if buf is None:
            asset_class, companion, game = _detect_game(export.source_xxx)
            asset = asset_class(export.source_xxx, companion)
            asset.parse(skip_bulk=True)
            midway_obj = asset.to_midway(skip_bulk=True)
            buf = bytes(midway_obj.mm[:])
            self._cache.put(export.source_xxx, buf)
            logger.info(f"Cached midway for {os.path.basename(export.source_xxx)} ({len(buf)} bytes)")
        return buf[export.object_offset:export.object_offset + export.object_size]

    def find_export(self, name_pattern: str) -> List[ExportMeta]:
        import fnmatch
        results = []
        for meta in self._mounted.values():
            for exp in meta.exports:
                if fnmatch.fnmatch(exp.full_name, name_pattern) or fnmatch.fnmatch(exp.name, name_pattern):
                    results.append(exp)
        return results

    def _insert_into_tree(self, meta: PackageMeta):
        game_node = self._tree.get_or_create_child(meta.game, is_dir=True)
        pkg_node = game_node.get_or_create_child(meta.file_name, is_dir=True)

        for exp in meta.exports:
            path_parts = exp.path.strip("/").split("/") if exp.path.strip("/") else []
            current = pkg_node
            for part in path_parts:
                current = current.get_or_create_child(part, is_dir=True)
            current.get_or_create_child(exp.name, is_dir=False, export=exp)

    def __str__(self) -> str:
        lines = [f"VFS: {self.mounted_count} packages, {self.total_exports} exports"]
        for xxx_path, meta in self._mounted.items():
            lines.append(f"  [{meta.game}] {meta.file_name}: {len(meta.exports)} exports")
        lines.append(f"  Cache: {self._cache.size} midways ({self._cache.memory_usage // 1024}KB)")
        return "\n".join(lines)
