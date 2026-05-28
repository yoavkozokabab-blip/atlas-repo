"""Human conversational runtime orchestrator (Phase 59 / 59.1)."""

from __future__ import annotations

import threading
import time
from typing import Any

from core.logger import setup_logger
from core.types import CommandResult, Intent

logger = setup_logger("jarvis.conversation.human_runtime")

_enabled = False
_lock = threading.Lock()
_session_active = False
_session_stats: dict[str, Any] = {
    "turns": 0,
    "partials": 0,
    "responses": 0,
    "last_text": "",
    "started_at": 0.0,
}

_STOP_PHRASES = frozenset(
    {
        "stop listening",
        "stop continuous listening",
        "goodbye jarvis",
        "exit conversation",
        "end conversation",
    }
)


def is_human_conversational_runtime_enabled() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", False)) and _enabled
    except Exception:
        return _enabled


def is_session_active() -> bool:
    with _lock:
        return _session_active


def get_session_snapshot() -> dict[str, Any]:
    with _lock:
        stats = dict(_session_stats)
        stats["session_active"] = _session_active
    try:
        from voice.continuous_mic import is_streaming_session_active
        from voice.streaming_pipeline import get_pipeline_metrics

        metrics = get_pipeline_metrics()
        stats["streaming_mic_active"] = is_streaming_session_active()
        stats["pipeline_partials"] = metrics.get("partial_updates", 0)
        stats["pipeline_responses"] = metrics.get("responses", 0)
        stats["pipeline_interruptions"] = metrics.get("interruptions", 0)
    except Exception:
        pass
    return stats


def enable_human_conversational_runtime() -> None:
    global _enabled
    try:
        import config as cfg

        if not getattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", False):
            logger.debug("Human conversational runtime disabled in config")
            return
    except Exception:
        return
    with _lock:
        _enabled = True
    logger.info("Human conversational runtime enabled (Phase 59)")


def uses_continuous_conversation() -> bool:
    try:
        import config as cfg

        if not is_human_conversational_runtime_enabled():
            return False
        return bool(getattr(cfg, "CONVERSATION_CONTINUOUS_MIC_ENABLED", True))
    except Exception:
        return is_human_conversational_runtime_enabled()


def should_start_human_session_after_wake(app: object | None = None) -> bool:
    del app
    if not uses_continuous_conversation():
        return False
    try:
        import config as cfg

        if getattr(cfg, "VOICE_RUNTIME_STABLE", False):
            return False
    except Exception:
        pass
    try:
        from voice.streaming_stt import is_streaming_stt_enabled

        return is_streaming_stt_enabled()
    except Exception:
        return False


def speak_result_conversationally(result: CommandResult) -> str:
    """Stream command summary through preemptive TTS with emotional prosody."""
    from conversation.emotional_speech import infer_speech_style
    from conversation.llm_streaming import stream_sentence_fragments
    from conversation.memory_runtime import record_conversational_turn
    from voice.interruption_manager import on_jarvis_speech_finished, on_jarvis_speech_started
    from voice.realtime_tts import split_sentences
    from voice.streaming_pipeline import get_streaming_pipeline

    text = (result.summary or "").strip()
    if not text:
        return ""
    style = infer_speech_style(
        text=text,
        intent=result.intent.value,
        status=result.status.value,
    )
    on_jarvis_speech_started(text)

    def _chunks():
        try:
            yield from stream_sentence_fragments(
                f"Summarize briefly for speech: {text[:400]}",
                system="Reply in one or two short spoken sentences.",
            )
        except Exception:
            for part in split_sentences(text):
                yield part

    provider = get_streaming_pipeline().speak_response_stream(
        _chunks(),
        emotion=style.emotion,
    )
    on_jarvis_speech_finished(interrupted=False)
    record_conversational_turn(
        user_text="",
        assistant_text=text,
        intent=result.intent.value,
        status=result.status.value,
        input_mode="voice",
        speech_style=style.label,
    )
    _increment_session_stat("responses")
    return provider or "conversational_summary"


def handle_conversational_turn(user_text: str, *, app: object | None = None) -> dict[str, object]:
    """Process one conversational turn with overlapping STT/TTS/LLM streaming."""
    from conversation.llm_streaming import speak_streaming_response

    del app
    provider = speak_streaming_response(user_text, intent="conversational", input_mode="voice")
    _increment_session_stat("responses")
    return {"text": user_text, "provider": provider}


def _process_human_turn(text: str, *, app: object) -> bool:
    """Route turn to command handler or conversational LLM stream."""
    from brain.intent_classifier import classify_rules
    from voice.command_input import prepare_command_text

    prepared = prepare_command_text(text)
    if not prepared.strip():
        return True
    lower = prepared.strip().lower()
    if lower in _STOP_PHRASES:
        return False

    preview = classify_rules(prepared)
    try:
        from voice.tts_policy_trace import log_tts_policy_context

        log_tts_policy_context(
            stage="human_runtime.process_turn",
            voice_path="human_runtime",
            input_mode="wakeword",
            intent=preview.intent.value,
            extra={"route": "conversational" if preview.intent in {Intent.UNKNOWN, Intent.CLARIFY} else "command"},
        )
    except Exception:
        pass
    if preview.intent in {Intent.UNKNOWN, Intent.CLARIFY}:
        handle_conversational_turn(prepared, app=app)
        return True

    result = app.handle_text_command(
        prepared,
        input_mode="wakeword",
        transcribed_text=prepared,
        print_result=False,
    )
    if result and getattr(result, "summary", ""):
        _increment_session_stat("responses")
    return True


def _increment_session_stat(key: str, amount: int = 1) -> None:
    with _lock:
        _session_stats[key] = int(_session_stats.get(key) or 0) + amount


def _reset_session_stats() -> None:
    global _session_stats
    with _lock:
        _session_stats = {
            "turns": 0,
            "partials": 0,
            "responses": 0,
            "last_text": "",
            "started_at": time.time(),
        }


def run_human_conversation_session(
    *,
    app: object | None = None,
    audio_feed: object | None = None,
) -> dict[str, object]:
    """Active human conversation session — rolling STT, streaming responses, multi-turn."""
    global _session_active

    if app is None:
        raise ValueError("app is required for human conversation session")

    _reset_session_stats()
    with _lock:
        _session_active = True

    logger.info("Starting active human conversation session (Phase 59.1)")

    def _on_partial(text: str) -> None:
        _increment_session_stat("partials")
        try:
            from ui.overlay_app import notify_overlay_partial_transcript

            notify_overlay_partial_transcript(text)
        except Exception:
            pass

    def _on_turn(text: str) -> bool:
        _increment_session_stat("turns")
        with _lock:
            _session_stats["last_text"] = text[:200]
        logger.info("human session turn: %r", text[:80])
        return _process_human_turn(text, app=app)

    try:
        from voice.continuous_mic import run_continuous_mic_session

        result = run_continuous_mic_session(
            session_context=getattr(app, "session", None),
            on_partial=_on_partial,
            on_turn=_on_turn,
            audio_feed=audio_feed,
        )
        with _lock:
            _session_stats.update(
                {
                    "turns": result.get("turns", _session_stats.get("turns", 0)),
                    "partials": max(
                        int(_session_stats.get("partials") or 0),
                        int(result.get("partials") or 0),
                    ),
                    "responses": max(
                        int(_session_stats.get("responses") or 0),
                        int(result.get("responses") or 0),
                    ),
                }
            )
        merged = dict(result)
        merged.update(
            {
                "turns": _session_stats.get("turns", 0),
                "partials": _session_stats.get("partials", 0),
                "responses": _session_stats.get("responses", 0),
            }
        )
        logger.info(
            "Human conversation session ended turns=%s partials=%s responses=%s",
            merged.get("turns"),
            merged.get("partials"),
            merged.get("responses"),
        )
        return merged
    finally:
        with _lock:
            _session_active = False


def start_human_conversation_session_after_wake(app: object) -> threading.Thread | None:
    """Non-blocking handoff from wakeword into active conversation session."""
    from voice.continuous_mic import start_streaming_session

    _reset_session_stats()
    with _lock:
        _session_active = True

    def _on_partial(text: str) -> None:
        _increment_session_stat("partials")

    def _on_turn(text: str) -> bool:
        _increment_session_stat("turns")
        with _lock:
            _session_stats["last_text"] = text[:200]
        return _process_human_turn(text, app=app)

    def _on_finished(result: dict[str, object]) -> None:
        global _session_active
        with _lock:
            _session_active = False
            _session_stats.update(
                {
                    "turns": result.get("turns", _session_stats.get("turns", 0)),
                    "partials": max(
                        int(_session_stats.get("partials") or 0),
                        int(result.get("partials") or 0),
                    ),
                    "responses": max(
                        int(_session_stats.get("responses") or 0),
                        int(result.get("responses") or 0),
                    ),
                }
            )
        logger.info("Background human session finished: %s", result)

    return start_streaming_session(
        session_context=getattr(app, "session", None),
        on_partial=_on_partial,
        on_turn=_on_turn,
        on_finished=_on_finished,
    )


def show_conversation_runtime() -> str:
    from assistant.conversation_state import show_conversation_state
    from conversation.conversation_metrics import show_conversation_runtime_metrics
    from conversation.memory_runtime import show_conversational_memory
    from voice.continuous_mic import _partial_interval_ms, _session_idle_seconds, _turn_max_seconds
    from voice.duplex_runtime import show_duplex_runtime_status

    snap = get_session_snapshot()
    lines = [
        "Human conversational runtime (Phase 59.1):",
        f"  enabled: {'yes' if is_human_conversational_runtime_enabled() else 'no'}",
        f"  continuous mic: {'yes' if uses_continuous_conversation() else 'no'}",
        f"  session active: {'yes' if snap.get('session_active') else 'no'}",
        f"  streaming mic active: {'yes' if snap.get('streaming_mic_active') else 'no'}",
        f"  partial interval ms: {_partial_interval_ms():.0f}",
        f"  turn max seconds: {_turn_max_seconds():.0f}",
        f"  idle timeout seconds: {_session_idle_seconds():.0f}",
        f"  session turns: {snap.get('turns', 0)}",
        f"  session partials: {snap.get('partials', 0)}",
        "",
        show_conversation_runtime_metrics(),
        "",
        show_duplex_runtime_status(),
        "",
        f"  pipeline partials: {snap.get('pipeline_partials', 0)}",
        f"  pipeline interruptions: {snap.get('pipeline_interruptions', 0)}",
        f"  pipeline responses: {snap.get('pipeline_responses', 0)}",
        "",
        show_conversational_memory(),
        "",
        show_conversation_state(),
    ]
    try:
        from assistant.idle_proactive import show_idle_proactive_status

        lines.extend(["", show_idle_proactive_status()])
    except Exception:
        pass
    try:
        from voice.tts_output_policy import format_tts_output_diagnostics

        lines.extend(["", format_tts_output_diagnostics()])
    except Exception:
        pass
    return "\n".join(lines)


def phase59_status() -> str:
    return show_conversation_runtime()


def activate_session_for_tests() -> None:
    """Mark an active human session for unit tests (Phase 59.2)."""
    global _session_active
    with _lock:
        _session_active = True


def reset_human_runtime_for_tests() -> None:
    global _enabled, _session_active
    with _lock:
        _enabled = False
        _session_active = False
    _reset_session_stats()
    try:
        from voice.continuous_mic import reset_continuous_mic_for_tests

        reset_continuous_mic_for_tests()
    except Exception:
        pass
