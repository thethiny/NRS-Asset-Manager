"""
DearPyGui asset browser for NRS game assets.
"""

import os
import logging
from typing import Optional, Set

import dearpygui.dearpygui as dpg

from mk_utils.nrs.vfs.mount_manager import MountManager
from mk_utils.nrs.vfs.tree import VFSNode

logger = logging.getLogger("Browser")

mgr: Optional[MountManager] = None
_current_dir: str = ""
_file_entries: list = []
_selected_indices: Set[int] = set()
_last_clicked_index: Optional[int] = None


def _scan_directory(dir_path: str):
    global _current_dir, _file_entries, _selected_indices, _last_clicked_index
    _current_dir = dir_path
    _selected_indices = set()
    _last_clicked_index = None
    dpg.set_value("dir_label", f"Scanning {dir_path}...")

    if dpg.does_item_exist("file_list"):
        dpg.delete_item("file_list", children_only=True)

    validated: list = []
    candidates = sorted(f for f in os.listdir(dir_path) if f.lower().endswith(".xxx"))

    for name in candidates:
        full = os.path.join(dir_path, name)
        try:
            with open(full, "rb") as f:
                magic = int.from_bytes(f.read(4), "little")
            if magic == 0x9E2A83C1:
                validated.append((name, full))
        except (OSError, ValueError):
            pass

    _file_entries = validated

    for i, (name, full) in enumerate(validated):
        dpg.add_selectable(
            label=name,
            parent="file_list",
            tag=f"file_{i}",
            callback=_on_file_click,
            user_data=i,
        )

    dpg.set_value("dir_label", f"Folder: {dir_path}  ({len(validated)} files)")
    _update_mount_button()


def _on_file_click(sender, value, user_data):
    global _last_clicked_index
    idx = user_data
    ctrl = dpg.is_key_down(dpg.mvKey_Control) or dpg.is_key_down(dpg.mvKey_LControl) or dpg.is_key_down(dpg.mvKey_RControl)
    shift = dpg.is_key_down(dpg.mvKey_Shift) or dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)

    if shift and _last_clicked_index is not None:
        lo = min(_last_clicked_index, idx)
        hi = max(_last_clicked_index, idx)
        if not ctrl:
            _selected_indices.clear()
        for i in range(lo, hi + 1):
            _selected_indices.add(i)
    elif ctrl:
        if idx in _selected_indices:
            _selected_indices.discard(idx)
        else:
            _selected_indices.add(idx)
    else:
        _selected_indices.clear()
        _selected_indices.add(idx)

    _last_clicked_index = idx
    _refresh_file_selection()
    _update_mount_button()


def _refresh_file_selection():
    for i in range(len(_file_entries)):
        tag = f"file_{i}"
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, i in _selected_indices)


def _update_mount_button():
    count = len(_selected_indices)
    if count > 0:
        dpg.configure_item("mount_btn", label=f"Mount ({count})", enabled=True)
    else:
        dpg.configure_item("mount_btn", label="Mount", enabled=False)


def _on_mount_selected():
    assert mgr is not None
    if not _selected_indices:
        return

    dpg.configure_item("mount_btn", label="Mounting...", enabled=False)

    for idx in sorted(_selected_indices):
        if idx < len(_file_entries):
            _, full = _file_entries[idx]
            try:
                mgr.mount(full)
            except Exception as e:
                logger.error(f"Mount failed for {_file_entries[idx][0]}: {e}")

    _rebuild_tree()
    _update_status()
    _update_mount_button()


def _on_mount_all():
    global _selected_indices
    assert mgr is not None
    if not _file_entries:
        return
    _selected_indices = set(range(len(_file_entries)))
    _refresh_file_selection()
    _on_mount_selected()


def _rebuild_tree():
    if dpg.does_item_exist("tree_container"):
        dpg.delete_item("tree_container", children_only=True)

    assert mgr is not None
    root = mgr.tree
    for child in root.sorted_children():
        _render_node(child, "tree_container")


def _render_node(node: VFSNode, parent_tag):
    if node.is_dir and node.children:
        label = f"{node.name}/ ({node.export_count})"
        with dpg.tree_node(label=label, parent=parent_tag, default_open=False) as tn:
            for child in node.sorted_children():
                _render_node(child, tn)
    elif node.export:
        exp = node.export
        label = f"[{exp.class_name}] {node.name}  ({exp.object_size} B)"
        dpg.add_selectable(
            label=label,
            parent=parent_tag,
            callback=_on_select_export,
            user_data=exp,
        )
    else:
        dpg.add_text(node.name, parent=parent_tag)


def _on_select_export(sender, value, user_data):
    exp = user_data
    detail = (
        f"Name: {exp.name}\n"
        f"Full Path: {exp.full_name}\n"
        f"Class: {exp.class_name}\n"
        f"Size: {exp.object_size} bytes\n"
        f"Offset: 0x{exp.object_offset:X}\n"
        f"Index: {exp.index}\n"
        f"Game: {exp.game}\n"
        f"Source: {os.path.basename(exp.source_xxx)}\n"
    )
    dpg.set_value("detail_text", detail)
    dpg.set_item_user_data("open_btn", exp)
    dpg.show_item("open_btn")


def _on_open_export(sender, value, user_data):
    if user_data is None:
        return
    assert mgr is not None
    exp = user_data
    try:
        data = mgr.open_export(exp)
        hex_lines = []
        for i in range(0, min(len(data), 256), 16):
            chunk = data[i:i+16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            hex_lines.append(f"{i:08X}  {hex_part:<48s}  {ascii_part}")
        preview = "\n".join(hex_lines)
        if len(data) > 256:
            preview += f"\n... ({len(data)} bytes total)"
        dpg.set_value("detail_text", preview)
        _update_status()
    except Exception as e:
        dpg.set_value("detail_text", f"Error reading export: {e}")


def _on_select_folder():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title="Select Asset Folder")
    root.destroy()
    if path and os.path.isdir(path):
        _scan_directory(path)


def _update_status():
    assert mgr is not None
    status = (
        f"Mounted: {mgr.mounted_count} packages | "
        f"Exports: {mgr.total_exports} | "
        f"Cache: {mgr._cache.size} midways ({mgr._cache.memory_usage // 1024} KB)"
    )
    dpg.set_value("status_text", status)


def launch_browser(initial_path: Optional[str] = None):
    global mgr
    mgr = MountManager()

    dpg.create_context()
    dpg.create_viewport(title="NRS Asset Browser", width=1280, height=768)

    with dpg.window(tag="main_window"):
        with dpg.group(horizontal=True):
            # Left panel — file list + mount button
            with dpg.child_window(width=300, tag="left_panel"):
                dpg.add_button(label="Select Folder", callback=_on_select_folder)
                dpg.add_text("No folder selected", tag="dir_label")
                dpg.add_separator()
                with dpg.child_window(tag="file_list", autosize_x=True, height=-40):
                    pass
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Mount", tag="mount_btn", callback=_on_mount_selected, enabled=False, width=140)
                    dpg.add_button(label="Mount All", callback=_on_mount_all, width=140)

            # Center panel — tree view
            with dpg.child_window(width=550, tag="center_panel"):
                dpg.add_text("Mount .xxx files to browse exports")
                with dpg.child_window(tag="tree_container", autosize_x=True):
                    pass

            # Right panel — details
            with dpg.child_window(tag="right_panel", autosize_x=True):
                dpg.add_text("Select an export to see details", tag="detail_text", wrap=400)
                dpg.add_button(
                    label="Open (Hex Preview)",
                    tag="open_btn",
                    callback=_on_open_export,
                    show=False,
                )

        dpg.add_separator()
        dpg.add_text("Ready", tag="status_text")

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)

    if initial_path and os.path.isdir(initial_path):
        _scan_directory(initial_path)

    dpg.start_dearpygui()
    dpg.destroy_context()
