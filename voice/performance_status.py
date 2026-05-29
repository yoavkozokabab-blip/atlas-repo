"""Voice performance settings loaded from .env (read-only display)."""

from __future__ import annotations


def voice_performance_settings() -> list[tuple[str, object]]:
    """Active voice speed/accuracy flags from config."""
    import config

    return [
        ("FAST_VOICE_MODE", config.FAST_VOICE_MODE),
        ("STT_LANGUAGE", config.STT_LANGUAGE),
        ("STT_MODEL", config.STT_MODEL),
        ("STT_COMPUTE_TYPE", config.STT_COMPUTE_TYPE or "(auto)"),
        ("STT_BEAM_SIZE", config.STT_BEAM_SIZE),
        ("STT_VAD_FILTER", config.STT_VAD_FILTER),
        ("STT_MAX_RECORD_SECONDS", config.STT_MAX_RECORD_SECONDS),
        ("STT_SILENCE_STOP_ENABLED", config.STT_SILENCE_STOP_ENABLED),
        ("STT_SILENCE_SECONDS", config.STT_SILENCE_SECONDS),
        ("WAKE_MAX_LISTEN_SECONDS", config.WAKE_MAX_LISTEN_SECONDS),
        ("WAKE_COOLDOWN_SECONDS", config.WAKE_COOLDOWN_SECONDS),
        ("WAKE_EARLY_STOP_ENABLED", config.WAKE_EARLY_STOP_ENABLED),
        ("TTS_ENGINE", config.TTS_ENGINE),
        ("TTS_FORCE_ENGINE", config.TTS_FORCE_ENGINE or "(none)"),
        ("TTS_VOICE", config.TTS_VOICE or "(default)"),
        ("TTS_RATE", config.TTS_RATE_RAW),
        ("TTS_MAX_CHARS", config.TTS_MAX_CHARS),
        ("TTS_ASYNC", config.TTS_ASYNC),
        ("WAKE_GREETING_ASYNC", config.WAKE_GREETING_ASYNC),
        ("VOICE_GRAMMAR_MIN_SCORE", config.VOICE_GRAMMAR_MIN_SCORE),
    ]


def format_voice_performance_status() -> str:
    from voice.stt_diagnostics import format_diagnostics_lines
    from voice.transcriber import get_stt_status

    from voice.fast_voice import format_wake_listen_diagnostics

    lines = ["Voice performance status", ""]
    for key, val in voice_performance_settings():
        lines.append(f"  {key}={val}")
    lines.append(f"  {format_wake_listen_diagnostics()}")
    stt = get_stt_status()
    lines.append("")
    lines.append("STT runtime")
    lines.append(f"  loaded_model: {stt.loaded_label or stt.model}")
    lp = stt.last_avg_logprob
    if isinstance(lp, (int, float)):
        lines.append(f"  last_avg_logprob: {lp:.3f}")
    if stt.last_recommendation:
        lines.append(f"  last_tip: {stt.last_recommendation}")
    lines.append("")
    lines.extend(format_diagnostics_lines())
    return "\n".join(lines)


def print_voice_performance_flags() -> None:
    print("--- Voice performance (.env) ---", flush=True)
    for key, val in voice_performance_settings():
        print(f"  {key}={val}", flush=True)
    print("--------------------------------", flush=True)
    print("", flush=True)
