"""JARVIS TTS-related thread diagnostics."""

from __future__ import annotations

import threading


def list_tts_threads() -> list[threading.Thread]:
    names = ("jarvis-tts", "jarvis-overlay", "jarvis-wake", "jarvis-op-tts")
    out: list[threading.Thread] = []
    for t in threading.enumerate():
        name = t.name or ""
        if any(name.startswith(n) for n in names) or "tts" in name.lower():
            out.append(t)
    return out


def format_tts_threads() -> str:
    threads = list_tts_threads()
    lines = ["TTS threads", f"  count: {len(threads)}"]
    if not threads:
        lines.append("  (no jarvis TTS threads alive)")
        return "\n".join(lines)
    for t in threads:
        lines.append(
            f"  - {t.name} daemon={t.daemon} alive={t.is_alive()} ident={t.ident}"
        )
    return "\n".join(lines)
