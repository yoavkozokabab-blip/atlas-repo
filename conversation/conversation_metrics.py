"""Phase 59 conversational latency and interruption metrics."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_lock = threading.Lock()
_last: "ConversationTurnMetrics | None" = None
_history: list["ConversationTurnMetrics"] = []


@dataclass
class ConversationTurnMetrics:
    first_partial_stt_ms: float | None = None
    llm_first_token_ms: float | None = None
    tts_first_audio_ms: float | None = None
    interrupt_pause_ms: float | None = None
    perceived_conversational_delay_ms: float | None = None
    turn_id: int = 0
    interrupted: bool = False
    resumed: bool = False
    _started: float = field(default_factory=time.perf_counter, repr=False)
    _partial_marked: bool = field(default=False, repr=False)
    _llm_marked: bool = field(default=False, repr=False)
    _tts_marked: bool = field(default=False, repr=False)

    def mark_first_partial_stt(self) -> None:
        if not self._partial_marked:
            self._partial_marked = True
            self.first_partial_stt_ms = (time.perf_counter() - self._started) * 1000.0
            self._refresh_perceived()

    def mark_llm_first_token(self) -> None:
        if not self._llm_marked:
            self._llm_marked = True
            self.llm_first_token_ms = (time.perf_counter() - self._started) * 1000.0
            self._refresh_perceived()

    def mark_tts_first_audio(self) -> None:
        if not self._tts_marked:
            self._tts_marked = True
            self.tts_first_audio_ms = (time.perf_counter() - self._started) * 1000.0
            self._refresh_perceived()

    def mark_interrupt_pause(self, pause_ms: float) -> None:
        self.interrupt_pause_ms = pause_ms
        self.interrupted = True

    def mark_resumed(self) -> None:
        self.resumed = True

    def finish(self) -> None:
        self._refresh_perceived()

    def _refresh_perceived(self) -> None:
        parts = [
            v
            for v in (
                self.first_partial_stt_ms,
                self.llm_first_token_ms,
                self.tts_first_audio_ms,
            )
            if v is not None
        ]
        if parts:
            self.perceived_conversational_delay_ms = max(parts)


def begin_conversation_turn(*, turn_id: int = 0) -> ConversationTurnMetrics:
    global _last
    rec = ConversationTurnMetrics(turn_id=turn_id)
    with _lock:
        _last = rec
    return rec


def record_conversation_turn(rec: ConversationTurnMetrics) -> None:
    rec.finish()
    with _lock:
        _history.append(rec)
        if len(_history) > 24:
            del _history[:-24]


def get_last_conversation_metrics() -> ConversationTurnMetrics | None:
    with _lock:
        return _last


def get_conversation_metrics_history() -> list[ConversationTurnMetrics]:
    with _lock:
        return list(_history)


def _target(name: str, default: float) -> float:
    try:
        import config as cfg

        return float(getattr(cfg, name, default))
    except Exception:
        return default


def _fmt(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "n/a"


def _status(actual: float | None, target: float) -> str:
    if actual is None:
        return "n/a"
    return "OK" if actual <= target else "SLOW"


def show_interruption_metrics() -> str:
    from voice.interruption_manager import get_interruption_snapshot
    from voice.voice_latency_metrics import get_last_realtime_latency

    intr = get_interruption_snapshot()
    rt = get_last_realtime_latency()
    conv = get_last_conversation_metrics()
    target = _target("CONVERSATION_TARGET_INTERRUPT_PAUSE_MS", 100.0)
    pause_ms = None
    if conv and conv.interrupt_pause_ms is not None:
        pause_ms = conv.interrupt_pause_ms
    elif rt and rt.interruption_cancel_ms is not None:
        pause_ms = rt.interruption_cancel_ms
    lines = [
        "Interruption metrics (Phase 59):",
        f"  interrupt_pause_ms: {_fmt(pause_ms)} (target <{target:.0f}) [{_status(pause_ms, target)}]",
        f"  interruption_cancel_ms: {_fmt(rt.interruption_cancel_ms if rt else None)}",
        f"  interruption state: {intr.get('state', 'idle')}",
        f"  paused response chars: {intr.get('paused_response_chars', 0)}",
        f"  interrupted turns: {sum(1 for h in get_conversation_metrics_history() if h.interrupted)}",
        f"  resumed turns: {sum(1 for h in get_conversation_metrics_history() if h.resumed)}",
    ]
    return "\n".join(lines)


def show_conversation_runtime_metrics() -> str:
    conv = get_last_conversation_metrics()
    targets = {
        "first_partial_stt_ms": _target("CONVERSATION_TARGET_FIRST_PARTIAL_STT_MS", 150.0),
        "llm_first_token_ms": _target("CONVERSATION_TARGET_LLM_FIRST_TOKEN_MS", 250.0),
        "tts_first_audio_ms": _target("CONVERSATION_TARGET_TTS_FIRST_AUDIO_MS", 250.0),
        "perceived_conversational_delay_ms": _target("CONVERSATION_TARGET_PERCEIVED_DELAY_MS", 400.0),
    }
    lines = [
        "Conversation runtime metrics (Phase 59):",
        f"  first_partial_stt_ms: {_fmt(conv.first_partial_stt_ms if conv else None)} "
        f"(target <{targets['first_partial_stt_ms']:.0f})",
        f"  llm_first_token_ms: {_fmt(conv.llm_first_token_ms if conv else None)} "
        f"(target <{targets['llm_first_token_ms']:.0f})",
        f"  tts_first_audio_ms: {_fmt(conv.tts_first_audio_ms if conv else None)} "
        f"(target <{targets['tts_first_audio_ms']:.0f})",
        f"  perceived delay ms: {_fmt(conv.perceived_conversational_delay_ms if conv else None)} "
        f"(target <{targets['perceived_conversational_delay_ms']:.0f})",
    ]
    if get_conversation_metrics_history():
        lines.append(f"  recent turns tracked: {len(get_conversation_metrics_history())}")
    return "\n".join(lines)


def benchmark_full_duplex_conversation() -> str:
    from conversation.human_runtime import is_human_conversational_runtime_enabled
    from voice.duplex_runtime import show_duplex_runtime_status
    from voice.streaming_pipeline import get_pipeline_metrics

    metrics = get_pipeline_metrics()
    conv = get_last_conversation_metrics()
    lines = [
        "Full-duplex conversation benchmark (Phase 59):",
        f"  human runtime enabled: {'yes' if is_human_conversational_runtime_enabled() else 'no'}",
        show_duplex_runtime_status(),
        "",
        show_conversation_runtime_metrics(),
        "",
        show_interruption_metrics(),
        "",
        "Pipeline counters:",
        f"  partial updates: {metrics.get('partial_updates', 0)}",
        f"  predictions: {metrics.get('predictions', 0)}",
        f"  interruptions: {metrics.get('interruptions', 0)}",
        f"  responses: {metrics.get('responses', 0)}",
    ]
    if conv:
        lines.append(f"  last turn id: {conv.turn_id}")
    return "\n".join(lines)


def reset_conversation_metrics_for_tests() -> None:
    global _last, _history
    with _lock:
        _last = None
        _history = []
