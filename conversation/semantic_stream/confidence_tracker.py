"""Continuous intent confidence updates during partial speech."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import config as cfg

_lock = threading.Lock()
_history: list["ConfidenceSample"] = []


@dataclass(frozen=True)
class ConfidenceSample:
    intent: str
    confidence: float
    partial_text: str
    timestamp: float


@dataclass
class ConfidenceTimeline:
    latest_intent: str = ""
    latest_confidence: float = 0.0
    peak_confidence: float = 0.0
    peak_intent: str = ""
    samples: list[ConfidenceSample] = field(default_factory=list)
    stable: bool = False


def record_confidence(
    *,
    intent: str,
    confidence: float,
    partial_text: str,
) -> ConfidenceTimeline:
    global _history
    sample = ConfidenceSample(
        intent=intent,
        confidence=confidence,
        partial_text=partial_text[:200],
        timestamp=time.monotonic(),
    )
    with _lock:
        _history.append(sample)
        _history = _history[-20:]
        timeline = ConfidenceTimeline(samples=list(_history))
    if not timeline.samples:
        return timeline
    timeline.latest_intent = intent
    timeline.latest_confidence = confidence
    peak = max(timeline.samples, key=lambda s: s.confidence)
    timeline.peak_intent = peak.intent
    timeline.peak_confidence = peak.confidence
    if len(timeline.samples) >= 2:
        last_two = timeline.samples[-2:]
        min_conf = float(cfg.CONV_CONFIDENCE_STABILITY_THRESHOLD)
        timeline.stable = (
            last_two[0].intent == last_two[1].intent
            and last_two[0].confidence >= min_conf
            and last_two[1].confidence >= min_conf
            and abs(last_two[0].confidence - last_two[1].confidence) < 0.08
        )
    return timeline


def reset_confidence_tracker() -> None:
    global _history
    with _lock:
        _history.clear()
