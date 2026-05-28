"""Direct playback metrics — start/complete/timeout/recovery (Phase 59.5)."""

from __future__ import annotations

import threading
from dataclasses import dataclass

_lock = threading.Lock()
_forced_recovery_count = 0
_last: "DirectPlaybackMetrics | None" = None


@dataclass(frozen=True)
class DirectPlaybackMetrics:
    audio_started: bool = False
    playback_completed: bool = False
    playback_duration_ms: float = 0.0
    playback_timeout: bool = False
    forced_recovery_count: int = 0
    fallback_path: str = ""
    worker_thread_id: int = 0
    utterance_started: bool = False
    utterance_finished: bool = False


def record_playback_metrics(
    *,
    audio_started: bool,
    playback_completed: bool,
    playback_duration_ms: float,
    playback_timeout: bool = False,
    fallback_path: str = "",
    worker_thread_id: int = 0,
    utterance_started: bool = False,
    utterance_finished: bool = False,
) -> None:
    global _last
    with _lock:
        metrics = DirectPlaybackMetrics(
            audio_started=audio_started,
            playback_completed=playback_completed,
            playback_duration_ms=playback_duration_ms,
            playback_timeout=playback_timeout,
            forced_recovery_count=_forced_recovery_count,
            fallback_path=fallback_path,
            worker_thread_id=worker_thread_id,
            utterance_started=utterance_started,
            utterance_finished=utterance_finished,
        )
        _last = metrics


def record_forced_recovery(*, path: str = "") -> None:
    global _forced_recovery_count, _last
    with _lock:
        _forced_recovery_count += 1
        if _last is not None:
            _last = DirectPlaybackMetrics(
                audio_started=_last.audio_started,
                playback_completed=_last.playback_completed,
                playback_duration_ms=_last.playback_duration_ms,
                playback_timeout=_last.playback_timeout,
                forced_recovery_count=_forced_recovery_count,
                fallback_path=path or _last.fallback_path,
                worker_thread_id=_last.worker_thread_id,
                utterance_started=_last.utterance_started,
                utterance_finished=_last.utterance_finished,
            )


def get_last_playback_metrics() -> DirectPlaybackMetrics | None:
    with _lock:
        return _last


def format_playback_metrics() -> str:
    with _lock:
        metrics = _last
        count = _forced_recovery_count
    lines = ["Direct playback metrics (Phase 59.5):"]
    if metrics is None:
        lines.append("  last playback: n/a")
        lines.append(f"  forced recovery count: {count}")
        return "\n".join(lines)
    lines.extend(
        [
            f"  audio started: {'yes' if metrics.audio_started else 'no'}",
            f"  playback completed: {'yes' if metrics.playback_completed else 'no'}",
            f"  playback duration ms: {metrics.playback_duration_ms:.1f}",
            f"  playback timeout: {'yes' if metrics.playback_timeout else 'no'}",
            f"  forced recovery count: {count}",
            f"  fallback path: {metrics.fallback_path or 'none'}",
            f"  worker thread id: {metrics.worker_thread_id or 'n/a'}",
            f"  utterance started: {'yes' if metrics.utterance_started else 'no'}",
            f"  utterance finished: {'yes' if metrics.utterance_finished else 'no'}",
        ]
    )
    return "\n".join(lines)


def reset_playback_metrics_for_tests() -> None:
    global _forced_recovery_count, _last
    with _lock:
        _forced_recovery_count = 0
        _last = None
