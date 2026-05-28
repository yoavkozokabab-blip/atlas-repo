"""Clipboard read/write (predefined, redacted reads)."""

from __future__ import annotations

from computer_control.models import ClipboardSummary
from computer_control.safety import (
    ComputerControlSafetyError,
    ensure_control_enabled,
    summarize_clipboard_text,
    validate_clipboard_write,
)


def _clipboard_set(text: str) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    finally:
        root.destroy()


def _clipboard_get() -> str:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        return root.clipboard_get()
    except tk.TclError:
        return ""
    finally:
        root.destroy()


def get_clipboard_summary() -> ClipboardSummary:
    ensure_control_enabled()
    try:
        raw = _clipboard_get()
    except Exception as exc:
        return ClipboardSummary(text="", length=0, error=str(exc))
    if not raw:
        return ClipboardSummary(text="(empty)", length=0)
    text, truncated = summarize_clipboard_text(raw)
    return ClipboardSummary(
        text=text,
        length=len(raw),
        truncated=truncated,
        redacted=True,
    )


def copy_text_to_clipboard(text: str) -> ClipboardSummary:
    ensure_control_enabled()
    validate_clipboard_write(text)
    try:
        _clipboard_set(text)
    except Exception as exc:
        raise ComputerControlSafetyError(f"Could not write clipboard: {exc}") from exc
    display, _ = summarize_clipboard_text(text)
    return ClipboardSummary(
        text=display,
        length=len(text),
        truncated=False,
        redacted=True,
    )


def clear_clipboard() -> ClipboardSummary:
    ensure_control_enabled()
    try:
        _clipboard_set("")
    except Exception as exc:
        return ClipboardSummary(text="", length=0, error=str(exc))
    return ClipboardSummary(text="(cleared)", length=0)
