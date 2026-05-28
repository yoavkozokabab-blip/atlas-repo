"""Multi-command decomposition from a single utterance (planning only)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SPLIT_RE = re.compile(
    r"\s+(?:and then|then also|and also|;\s*|,\s*then\s+)\s+",
    re.I,
)


@dataclass(frozen=True)
class DecomposedSegment:
    text: str
    index: int


@dataclass(frozen=True)
class MultiIntentPlan:
    segments: tuple[DecomposedSegment, ...]
    combined: bool


def decompose_utterance(text: str, *, max_segments: int = 3) -> MultiIntentPlan:
    """Split natural multi-command speech into ordered segments."""
    raw = (text or "").strip()
    if not raw:
        return MultiIntentPlan(segments=(), combined=False)
    parts = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
    if len(parts) <= 1:
        return MultiIntentPlan(
            segments=(DecomposedSegment(text=raw, index=0),),
            combined=False,
        )
    segs = tuple(
        DecomposedSegment(text=p, index=i) for i, p in enumerate(parts[:max_segments])
    )
    return MultiIntentPlan(segments=segs, combined=True)
