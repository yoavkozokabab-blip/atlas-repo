"""Phase 30 — startup health and settings status."""

from __future__ import annotations

import os
from pathlib import Path

from config import (
    BROWSER_DOM_ENABLED,
    DATA_DIR,
    FAST_VOICE_MODE,
    GUIDED_UI_ENABLED,
    OVERLAY_ENABLED,
    PATCH_APPLY_ENABLED,
    PROJECT_ROOT,
    TTS_ENGINE,
    VISION_ENABLED,
    VOICE_ENABLED,
    WAKE_WORD_ENABLED,
)
from voice.latency_tracker import get_last_latency


def _latency_line() -> str:
    rec = get_last_latency()
    if rec is None:
        return "  (no voice commands recorded yet)"
    return rec.format_status()


def startup_health_report() -> str:
    lines = [
        "JARVIS startup health",
        f"Project root: {PROJECT_ROOT}",
        f"Data dir exists: {DATA_DIR.is_dir()}",
        f"Voice enabled: {VOICE_ENABLED}",
        f"Fast voice: {FAST_VOICE_MODE}",
        f"TTS engine: {TTS_ENGINE}",
        f"Wake word: {WAKE_WORD_ENABLED}",
        f"Overlay: {OVERLAY_ENABLED}",
        f"Vision: {VISION_ENABLED}",
        f"Patch apply: {PATCH_APPLY_ENABLED}",
        f"Guided UI: {GUIDED_UI_ENABLED}",
        f"Browser DOM: {BROWSER_DOM_ENABLED}",
        "",
        "Latency (last command):",
        _latency_line(),
        "",
        "Log: reports/jarvis_logs/startup_latest.log",
    ]
    log = PROJECT_ROOT / "reports" / "jarvis_logs" / "startup_latest.log"
    if log.is_file():
        tail = log.read_text(encoding="utf-8", errors="replace")[-500:]
        lines.append(f"Startup log tail:\n{tail}")
    return "\n".join(lines)


def settings_status_report() -> str:
    env_path = PROJECT_ROOT / ".env"
    present = env_path.is_file()
    keys = [
        "VOICE_ENABLED",
        "FAST_VOICE_MODE",
        "TTS_ENGINE",
        "OVERLAY_ENABLED",
        "PATCH_APPLY_ENABLED",
        "BROWSER_DOM_ENABLED",
        "GUIDED_UI_ENABLED",
        "TASK_QUEUE_MAX_RUNTIME_SECONDS",
    ]
    lines = ["JARVIS settings status", f".env present: {present}", ""]
    for k in keys:
        lines.append(f"  {k}={os.getenv(k, '(default)')}")
    return "\n".join(lines)
