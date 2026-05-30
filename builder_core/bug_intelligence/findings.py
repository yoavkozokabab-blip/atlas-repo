"""Finding data model and scoring weights for Bug Intelligence.

A Finding is a single, line-anchored, explained suspicion about a source file.
It records *severity* (how bad it is if real) separately from *confidence*
(how sure the deterministic heuristic is). Nothing here is a proof of a bug —
each Finding is a review lead with evidence and reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# How damaging the issue would be if it is a real bug.
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
# How confident the deterministic heuristic is that this is real.
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}

_CONF_ORDER = {"high": 3, "medium": 2, "low": 1}


@dataclass
class Finding:
    """One explained, line-anchored suspicion."""

    rule: str
    title: str
    severity: str  # high | medium | low
    confidence: str  # high | medium | low
    line: int
    message: str  # the reasoning: *why* this looks wrong
    evidence: str = ""  # the offending source line(s)
    function: Optional[str] = None

    def weight(self) -> float:
        return (
            SEVERITY_WEIGHT.get(self.severity, 1)
            * CONFIDENCE_WEIGHT.get(self.confidence, 0.3)
        )

    def key(self) -> tuple:
        return (self.rule, self.line, self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "line": self.line,
            "function": self.function,
            "message": self.message,
            "evidence": self.evidence,
        }


def dedupe(findings: List[Finding]) -> List[Finding]:
    seen = set()
    out: List[Finding] = []
    for f in findings:
        if f.key() not in seen:
            out.append(f)
            seen.add(f.key())
    return out


def sort_findings(findings: List[Finding]) -> List[Finding]:
    """Highest severity, then highest confidence, then earliest line."""
    return sorted(
        findings,
        key=lambda f: (
            -SEVERITY_WEIGHT.get(f.severity, 0),
            -_CONF_ORDER.get(f.confidence, 0),
            f.line,
            f.rule,
        ),
    )


def overall_confidence(findings: List[Finding]) -> str:
    """The strongest confidence present, or 'low' when there are no findings."""
    best = 0
    for f in findings:
        best = max(best, _CONF_ORDER.get(f.confidence, 0))
    for label, rank in _CONF_ORDER.items():
        if rank == best:
            return label if findings else "low"
    return "low"


def confidence_breakdown(findings: List[Finding]) -> Dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        if f.confidence in counts:
            counts[f.confidence] += 1
    return counts
