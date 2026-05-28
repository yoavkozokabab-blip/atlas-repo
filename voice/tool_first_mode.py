"""Tool-first runtime mode: console/HUD are primary; TTS is optional."""

from __future__ import annotations

TOOL_MODE_NOTICE = "Audio output deferred - tool mode active"


def is_tool_first_mode() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "TOOL_FIRST_MODE", False))
    except Exception:
        return False


def can_attempt_tts() -> bool:
    """TTS may run only when explicitly available and audible route is verified."""
    from voice.tts_output_policy import can_attempt_tts as _policy_can_attempt_tts

    return _policy_can_attempt_tts(voice_path="tool_first_mode")


def should_show_speak_phase() -> bool:
    return can_attempt_tts()


def format_tool_mode_status() -> str:
    from voice.audio_status import get_audio_status

    audio = get_audio_status()
    lines = [
        "Tool mode status",
        f"  TOOL_FIRST_MODE: {'yes' if is_tool_first_mode() else 'no'}",
        f"  Notice: {TOOL_MODE_NOTICE if is_tool_first_mode() else 'inactive'}",
        "  Primary control path: operator console + HUD",
        "  Voice input: available if microphone/STT runtime is available",
        f"  Verified audio backend: {audio.selected_verified_audio_backend or 'none'}",
        f"  TTS may run: {'yes' if can_attempt_tts() else 'no (deferred)'}",
        f"  Active TTS backend: {audio.active_backend}",
        "",
        "Phase 45 - Elite Code + Trading Investigation Engine",
        "  Capabilities:",
        "    - inspect project",
        "    - trace bugs",
        "    - compare backtest vs live",
        "    - read logs/reports/state",
        "    - produce findings and propose patches",
        "    - run tests and summarize evidence",
        "    - never apply destructive changes without approval",
    ]
    return "\n".join(lines)
