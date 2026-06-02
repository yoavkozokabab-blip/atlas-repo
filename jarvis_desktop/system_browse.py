"""Local-only native folder picker for JARVIS Desktop."""

from __future__ import annotations

import os
import queue
import threading
from typing import Any, Dict

PICKER_TIMEOUT_SECONDS = 120.0


def _pick_folder_native() -> str:
    """Open the operating-system folder picker and return its selected path."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        root.update_idletasks()
        root.update()
        return str(
            filedialog.askdirectory(
                parent=root,
                title="Choose a repository folder",
                mustexist=True,
            )
            or ""
        )
    finally:
        root.destroy()


def browse_folder(timeout_s: float = PICKER_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Return one native folder selection without blocking the server forever."""
    result: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1)

    def _run_picker() -> None:
        try:
            result.put(("selected", _pick_folder_native()))
        except Exception as exc:
            result.put(("unavailable", type(exc).__name__))

    thread = threading.Thread(target=_run_picker, name="jarvis-desktop-folder-picker", daemon=True)
    thread.start()
    try:
        status, value = result.get(timeout=max(0.1, float(timeout_s)))
    except queue.Empty:
        return {
            "ok": False,
            "supported": False,
            "cancelled": False,
            "code": "picker_timeout",
            "error": "The folder picker did not respond. Paste the repository path manually.",
        }

    if status != "selected":
        return {
            "ok": False,
            "supported": False,
            "cancelled": False,
            "code": "unsupported_browse_dialog",
            "reason_type": value,
            "error": "unsupported_browse_dialog",
            "message": "Paste the folder path manually.",
        }

    selected = os.path.abspath(value) if value else ""
    if not selected:
        return {"ok": True, "supported": True, "cancelled": True, "path": None}
    if not os.path.isdir(selected):
        return {
            "ok": False,
            "supported": True,
            "cancelled": False,
            "code": "picker_invalid_path",
            "error": "The selected folder is no longer available. Choose another folder or paste its path manually.",
        }
    return {"ok": True, "supported": True, "cancelled": False, "path": selected}
