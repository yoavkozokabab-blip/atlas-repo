"""Standalone streaming STT test harness (Phase 59.6)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.streaming.test")


@dataclass(frozen=True)
class StreamingSttTestResult:
    ok: bool
    partial_updates: int
    first_partial_ms: float | None
    stream_alive: bool
    streaming_disabled: bool
    report: str
    error: str = ""


def _tone_chunk(seconds: float = 0.1, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def run_streaming_stt_test(
    *,
    listen_seconds: float = 8.0,
    use_live_mic: bool = True,
) -> StreamingSttTestResult:
    """
    Open mic (or synthetic feed), stream partials, print diagnostics.
  """
    from voice.streaming_stt.diagnostics import (
        begin_streaming_diagnostics,
        format_streaming_diagnostics,
        get_streaming_diagnostics,
    )
    from voice.streaming_stt.session_policy import (
        get_streaming_disable_reason,
        is_streaming_stt_enabled_for_session,
        partial_timeout_count,
        reset_streaming_session,
    )
    from voice.streaming_stt.stream_session import StreamingSttSession, is_streaming_stt_enabled

    if not is_streaming_stt_enabled():
        return StreamingSttTestResult(
            ok=False,
            partial_updates=0,
            first_partial_ms=None,
            stream_alive=False,
            streaming_disabled=True,
            report="Streaming STT is disabled (config or session policy).",
            error="streaming_disabled",
        )

    reset_streaming_session()
    begin_streaming_diagnostics()

    partials: list[str] = []

    def _on_partial(text: str) -> None:
        partials.append(text)

    if use_live_mic:
        session = StreamingSttSession(on_partial=_on_partial)
    else:
        feed_idx = {"n": 0}

        def _feed() -> np.ndarray:
            feed_idx["n"] += 1
            return _tone_chunk(0.1)

        session = StreamingSttSession(audio_feed=_feed, on_partial=_on_partial)

    t0 = time.perf_counter()
    error = ""
    result = None
    try:
        result = session.run_until_endpoint(max_seconds=listen_seconds)
    except Exception as exc:
        error = str(exc)
        logger.warning("streaming STT test failed: %s", exc)
    elapsed = time.perf_counter() - t0

    diag = get_streaming_diagnostics()
    first_ms = diag.first_partial_ms if diag is not None else None
    report_lines = [
        f"Streaming STT test ({'live mic' if use_live_mic else 'synthetic feed'}):",
        f"  elapsed s: {elapsed:.1f}",
        f"  partial updates: {result.partial_updates if result else len(partials)}",
        f"  final text: {(result.text if result else '')[:120]!r}",
        f"  session streaming enabled: {'yes' if is_streaming_stt_enabled_for_session() else 'no'}",
        f"  partial timeout count: {partial_timeout_count()}",
    ]
    if get_streaming_disable_reason():
        report_lines.append(f"  disable reason: {get_streaming_disable_reason()}")
    report_lines.append("")
    report_lines.append(format_streaming_diagnostics())

    stream_alive = is_streaming_stt_enabled_for_session()
    audio_ok = bool(diag and diag.audio_frames_received)
    partial_ok = bool(result and (result.partial_updates > 0 or partials))
    ok = stream_alive and audio_ok and (partial_ok or error == "") and not error

    return StreamingSttTestResult(
        ok=ok,
        partial_updates=result.partial_updates if result else len(partials),
        first_partial_ms=first_ms,
        stream_alive=stream_alive,
        streaming_disabled=not stream_alive,
        report="\n".join(report_lines),
        error=error,
    )
