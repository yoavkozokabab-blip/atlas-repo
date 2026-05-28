"""Realtime mid-utterance corrections (no execution)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CORRECTION_PREFIXES = (
    "no wait",
    "no ",
    "actually ",
    "i meant ",
    "sorry ",
    "correction ",
    "not that ",
    "scratch that ",
)


@dataclass(frozen=True)
class CorrectionResult:
    applied: bool
    stripped_text: str
    reason: str = ""


def apply_realtime_correction(text: str, *, previous_text: str = "") -> CorrectionResult:
    """
    Detect self-corrections and return reformulated command text.
    Does not mutate router state — reformulation only.
    """
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw:
        return CorrectionResult(applied=False, stripped_text=raw)
    for prefix in _CORRECTION_PREFIXES:
        if lower.startswith(prefix):
            rest = raw[len(prefix) :].strip()
            if rest:
                return CorrectionResult(
                    applied=True,
                    stripped_text=rest,
                    reason=f"correction_prefix:{prefix.strip()}",
                )
    # "open dashboard no open discord" → take trailing clause
    m = re.search(
        r"\b(?:no|not)\s+(?:wait\s+)?(?:open|show|run)\s+(.+)$",
        lower,
    )
    if m:
        tail = raw[raw.lower().find(m.group(0)) :].split(None, 2)
        if len(tail) >= 2:
            rebuilt = " ".join(tail[-2:]) if tail[0].lower() in {"no", "not"} else m.group(0)
            return CorrectionResult(
                applied=True,
                stripped_text=rebuilt.strip(),
                reason="inline_negation_rewrite",
            )
    if previous_text and lower.endswith("instead"):
        base = re.sub(r"\s+instead\s*$", "", raw, flags=re.I).strip()
        if base:
            return CorrectionResult(applied=True, stripped_text=base, reason="instead_clause")
    return CorrectionResult(applied=False, stripped_text=raw)
