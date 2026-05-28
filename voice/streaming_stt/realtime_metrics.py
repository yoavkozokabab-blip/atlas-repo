"""Realtime STT latency metrics for overlay HUD."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_lock = threading.Lock()
_metrics: "RealtimeSttMetrics | None" = None


@dataclass
class RealtimeSttMetrics:
    partial_interval_ms: float = 0.0
    last_partial_ms: float = 0.0
    last_decode_ms: float = 0.0
    buffer_seconds: float = 0.0
    partial_count: int = 0
    prefetch_intent: str = ""
    prefetch_confidence: float = 0.0
    endpoint_silence_ms: float = 0.0
    gpu_first: bool = False
    stream_active: bool = False
    updated_at: float = field(default_factory=time.monotonic)

    def as_hud_dict(self) -> dict[str, str]:
        return {
            "stt_partial_ms": f"{self.last_partial_ms:.0f}",
            "stt_decode_ms": f"{self.last_decode_ms:.0f}",
            "stt_buffer_s": f"{self.buffer_seconds:.1f}",
            "stt_prefetch": self.prefetch_intent or "—",
            "stt_stream": "ON" if self.stream_active else "OFF",
        }


def publish_metrics(metrics: RealtimeSttMetrics) -> None:
    global _metrics
    metrics.updated_at = time.monotonic()
    with _lock:
        _metrics = metrics
    try:
        from ui.overlay_app import notify_overlay_realtime_stt_metrics

        notify_overlay_realtime_stt_metrics(metrics)
    except Exception:
        pass


def get_realtime_metrics() -> RealtimeSttMetrics | None:
    with _lock:
        return _metrics


def reset_realtime_metrics() -> None:
    global _metrics
    with _lock:
        _metrics = None
