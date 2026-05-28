"""Overlay guidance for repeated empty wake transcripts."""

from __future__ import annotations

from voice.stt_diagnostics import record_empty_wake_guidance, snapshot

PRIMARY_EMPTY_WAKE_MSG = "I heard the wake word, but not the command."
EMPTY_WAKE_HINT = "Try saying: open dashboard"
EMPTY_WAKE_RETRY_HINT = "Say clearly: show jarvis status — or: show voice debug"


def empty_wake_overlay_message() -> str:
    snap = snapshot()
    if snap.consecutive_empty_wake >= 3:
        return f"{PRIMARY_EMPTY_WAKE_MSG}\n{EMPTY_WAKE_RETRY_HINT}"
    if snap.consecutive_empty_wake >= 2:
        return f"{PRIMARY_EMPTY_WAKE_MSG}\n{EMPTY_WAKE_HINT}"
    return PRIMARY_EMPTY_WAKE_MSG


def notify_empty_wake_transcript() -> str:
    record_empty_wake_guidance()
    return empty_wake_overlay_message()
