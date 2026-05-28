"""Compact spoken summaries for read-only diagnostic commands (Phase 59.5)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types import CommandResult

# Intents that return long text blocks — never read the full summary aloud.
DIAGNOSTIC_READONLY_INTENTS: frozenset[str] = frozenset(
    {
        "show_tts_debug",
        "show_tts_status",
        "show_audio_status",
        "show_wake_diagnostics",
        "show_tts_threads",
        "run_diagnostics",
        "run_safe_diagnostics",
        "show_realtime_provider_status",
        "phase56_status",
        "phase57_status",
        "show_voice_latency",
    }
)

_SKIP_SPEAK_DATA_KEYS = frozenset({"skip_speak", "already_spoken", "no_speak"})


def is_read_only_diagnostic_result(result: "CommandResult") -> bool:
    data = result.data or {}
    if data.get("read_only"):
        return True
    return result.intent.value in DIAGNOSTIC_READONLY_INTENTS


def should_skip_result_speech(result: "CommandResult") -> bool:
    data = result.data or {}
    if any(data.get(key) for key in _SKIP_SPEAK_DATA_KEYS):
        return True
    try:
        import config as cfg

        if data.get("read_only") and not getattr(cfg, "TTS_READ_ONLY_COMPACT_SPEAK", True):
            return True
    except Exception:
        pass
    return False


def _parse_keyed_lines(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("speak_enabled:") and ": " not in stripped:
            if stripped.startswith("  ") and ":" in stripped:
                key, _, value = stripped.strip().partition(":")
                fields[key.strip().lower()] = value.strip()
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            fields[key.strip().lower()] = value.strip()
    return fields


def compact_spoken_summary_for_result(result: "CommandResult") -> str:
    """One short spoken line for diagnostics; full text stays in console/overlay."""
    intent = result.intent.value
    full = (result.summary or "").strip()
    if not full:
        return ""

    if intent == "show_tts_debug":
        return _compact_tts_debug_summary(full)
    if intent == "show_audio_status":
        return _compact_audio_status_summary(full)
    if intent in {"show_tts_status", "show_tts_threads"}:
        return _compact_keyed_block_summary(full, title="TTS status")
    if intent in DIAGNOSTIC_READONLY_INTENTS:
        return _compact_keyed_block_summary(full, title="Diagnostics ready")

    if is_read_only_diagnostic_result(result):
        return _compact_keyed_block_summary(full, title="Status ready")
    return ""


def _compact_tts_debug_summary(full: str) -> str:
    fields = _parse_keyed_lines(full)
    parts: list[str] = []
    if fields.get("speak_enabled") == "yes":
        parts.append("speech enabled")
    elif fields.get("speak_enabled") == "no":
        parts.append("speech muted")
    mode = fields.get("audio_mode")
    if mode:
        parts.append(f"{mode} audio")
    backend = fields.get("verified backend") or fields.get("backend")
    if backend:
        parts.append(f"verified backend {backend}")
    reason = fields.get("last suppression reason") or fields.get("reason")
    if reason and reason not in {"allowed", "conversational_runtime_local_fallback"}:
        parts.append(f"last block {reason}")
    elif fields.get("allowed") == "yes":
        parts.append("output allowed")
    completed = fields.get("playback completed")
    timeout = fields.get("playback timeout")
    if completed == "yes" and timeout != "yes":
        parts.append("last playback clean")
    elif timeout == "yes":
        parts.append("last playback timed out")
    if not parts:
        return "TTS debug ready. See console for details."
    return "TTS debug. " + ", ".join(parts[:5]) + "."


def _compact_audio_status_summary(full: str) -> str:
    fields = _parse_keyed_lines(full)
    parts: list[str] = ["Audio status"]
    if fields.get("tts enabled"):
        parts.append(f"TTS {fields['tts enabled']}")
    vb = fields.get("verified backend")
    if vb:
        parts.append(f"verified {vb}")
    if fields.get("playback audible confirmed") == "yes":
        parts.append("audible confirmed")
    return ", ".join(parts[:4]) + "."


def _compact_keyed_block_summary(full: str, *, title: str) -> str:
    fields = _parse_keyed_lines(full)
    if not fields:
        lead = re.split(r"[.\n]", full, maxsplit=1)[0].strip()
        if lead and len(lead) <= 120:
            return lead if lead.endswith(".") else f"{lead}."
        return f"{title}. See console for details."
    picks: list[str] = []
    for key in (
        "speak_enabled",
        "tts enabled",
        "audio_mode",
        "verified backend",
        "allowed",
        "playback completed",
    ):
        val = fields.get(key)
        if val:
            picks.append(f"{key} {val}")
        if len(picks) >= 3:
            break
    if picks:
        return f"{title}. " + ", ".join(picks) + "."
    return f"{title}. See console for details."


def speak_compact_diagnostic(text: str) -> bool:
    """Same direct COM-thread path as test direct tts."""
    safe = (text or "").strip()
    if not safe:
        return False
    try:
        import config as cfg
        from voice.pyttsx3_completion import run_direct_tts_isolated_test

        result = run_direct_tts_isolated_test(safe[:240], rate_raw=getattr(cfg, "TTS_RATE_RAW", ""))
        return bool(result.ok)
    except Exception:
        return False
