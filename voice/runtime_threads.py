"""Runtime thread diagnostics for operator console."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeThreadRow:
    role: str
    name: str
    alive: bool
    daemon: bool
    ident: int | None


def _row(role: str, thread: threading.Thread | None) -> RuntimeThreadRow:
    if thread is None:
        return RuntimeThreadRow(role=role, name="(none)", alive=False, daemon=False, ident=None)
    return RuntimeThreadRow(
        role=role,
        name=thread.name or role,
        alive=thread.is_alive(),
        daemon=bool(thread.daemon),
        ident=thread.ident,
    )


def collect_runtime_threads(tray_app: Any | None = None) -> list[RuntimeThreadRow]:
    rows: list[RuntimeThreadRow] = []

    wake_thread = None
    if tray_app is not None:
        detector = getattr(tray_app, "_wakeword_detector", None)
        wake_thread = getattr(detector, "_thread", None) if detector else None
    rows.append(_row("wake_listener", wake_thread))

    overlay_thread = None
    try:
        from ui.overlay_app import get_overlay_controller

        ctrl = get_overlay_controller()
        overlay_thread = getattr(ctrl, "_qt_thread", None)
    except Exception:
        pass
    rows.append(_row("overlay", overlay_thread))

    console_thread = None
    try:
        from ui.operator_console import get_operator_console

        oc = get_operator_console()
        console_thread = getattr(oc, "_thread", None) if oc else None
    except Exception:
        pass
    rows.append(_row("console", console_thread))

    tts_threads = [
        t
        for t in threading.enumerate()
        if (t.name or "").startswith("jarvis-tts") or "tts" in (t.name or "").lower()
    ]
    if tts_threads:
        for t in tts_threads[:3]:
            rows.append(_row("tts", t))
    else:
        rows.append(_row("tts", None))

    watchdog_thread = None
    if tray_app is not None:
        wdog = getattr(tray_app, "_watchdog", None)
        watchdog_thread = getattr(wdog, "_thread", None) if wdog else None
    rows.append(_row("watchdog", watchdog_thread))

    return rows


def format_runtime_threads(tray_app: Any | None = None) -> str:
    rows = collect_runtime_threads(tray_app)
    lines = ["Runtime threads"]
    for row in rows:
        state = "alive" if row.alive else "dead"
        lines.append(
            f"  {row.role}: name={row.name} state={state} daemon={row.daemon} ident={row.ident}"
        )
    return "\n".join(lines)
