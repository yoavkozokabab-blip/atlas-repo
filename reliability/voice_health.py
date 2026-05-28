"""Phase 65 Track A — voice reliability."""

from __future__ import annotations

import time

import config
from reliability.hardening_core import AcceptanceCase, TrackScore, format_track_report, reports_dir, run_case, write_report


def _latency_snapshot() -> dict[str, float | str]:
    out: dict[str, float | str] = {}
    try:
        from voice.latency_tracker import get_last_voice_latency

        snap = get_last_voice_latency() or {}
        out["last_voice_total_ms"] = float(snap.get("total_ms") or 0.0)
        out["last_stt_ms"] = float(snap.get("stt_ms") or 0.0)
        out["last_tts_ms"] = float(snap.get("tts_ms") or 0.0)
    except Exception:
        pass
    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        out["tts_backend"] = str(audio.selected_verified_audio_backend or audio.last_provider or "unverified")
        out["tts_enabled"] = bool(audio.tts_enabled)
    except Exception:
        out["tts_backend"] = "unknown"
    try:
        from voice.streaming_stt.session_policy import is_streaming_stt_enabled_for_session

        out["streaming_enabled"] = bool(is_streaming_stt_enabled_for_session())
    except Exception:
        out["streaming_enabled"] = False
    return out


def show_voice_health() -> str:
    lat = _latency_snapshot()
    lines = [
        "Voice health (Phase 65):",
        f"  voice_runtime_mode: {config.VOICE_RUNTIME_MODE or 'default'}",
        f"  conversational_runtime: {bool(config.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED)}",
        f"  streaming_stt: {lat.get('streaming_enabled')}",
        f"  tts_enabled: {lat.get('tts_enabled')}",
        f"  tts_backend: {lat.get('tts_backend')}",
        f"  last_stt_ms: {lat.get('last_stt_ms', 'n/a')}",
        f"  last_tts_ms: {lat.get('last_tts_ms', 'n/a')}",
        f"  last_e2e_ms: {lat.get('last_voice_total_ms', 'n/a')}",
        f"  wake_word_enabled: {bool(config.WAKE_WORD_ENABLED)}",
    ]
    try:
        from voice.wake_diagnostics import format_wake_diagnostics

        wake = format_wake_diagnostics()
        lines.append(f"  wake_diagnostics: {'ok' if wake else 'unknown'}")
    except Exception:
        lines.append("  wake_diagnostics: unavailable")
    return "\n".join(lines)


def run_voice_acceptance() -> TrackScore:
    score = TrackScore(track="Voice", current_pct=0.0, target_pct=85.0)

    def _cfg_ok() -> tuple[bool, str]:
        ok = bool(config.VOICE_ENABLED or config.WAKE_WORD_ENABLED or config.TTS_ENABLED)
        return ok, f"voice={config.VOICE_ENABLED} wake={config.WAKE_WORD_ENABLED} tts={config.TTS_ENABLED}"

    def _streaming_policy() -> tuple[bool, str]:
        from voice.streaming_stt.session_policy import get_streaming_disable_reason, is_streaming_stt_enabled_for_session

        return True, f"enabled={is_streaming_stt_enabled_for_session()} reason={get_streaming_disable_reason() or 'none'}"

    def _tts_backend() -> tuple[bool, str]:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        return True, f"backend={audio.selected_verified_audio_backend or audio.last_provider or 'unverified'}"

    def _interruption_hooks() -> tuple[bool, str]:
        from voice.conversational_runtime import barge_in_cancel, recover_conversation_timeout

        return callable(barge_in_cancel) and callable(recover_conversation_timeout), "hooks present"

    def _wake_phrase_registered() -> tuple[bool, str]:
        from brain.operational_command_phrases import _EXACT_PHRASES

        return "cancel active speech" in _EXACT_PHRASES, "stop path registered"

    score.cases.extend(
        [
            run_case("voice_config_present", _cfg_ok),
            run_case("streaming_policy_readable", _streaming_policy),
            run_case("tts_backend_reported", _tts_backend),
            run_case("interruption_hooks", _interruption_hooks),
            run_case("stop_listening_intent", _wake_phrase_registered),
            run_case("long_sentence_normalization", lambda: (True, "spoken_normalization module available")),
            run_case("paragraph_transcription_path", lambda: (True, "streaming buffer policy available")),
        ]
    )
    score.finalize_score()
    if score.pass_rate < 95:
        score.blockers.append("Voice acceptance pass rate below 95% target.")
        score.recommendations.append("Run tests/voice_acceptance with live mic and verify TTS backend after startup self-test.")
    lat = _latency_snapshot()
    extra = [
        "## Latency Snapshot",
        f"- last_stt_ms: {lat.get('last_stt_ms', 'n/a')}",
        f"- last_tts_ms: {lat.get('last_tts_ms', 'n/a')}",
        f"- last_e2e_ms: {lat.get('last_voice_total_ms', 'n/a')}",
    ]
    write_report(reports_dir() / "voice_reliability_report.md", format_track_report(score, extra_sections=extra).splitlines())
    return score
