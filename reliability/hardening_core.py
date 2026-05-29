"""Shared helpers for Phase 65 product hardening.

Sprint 1 changes (truthfulness audit):
- AcceptanceCase gains a `skipped` flag so fn() can return (None, reason)
  to signal SKIP rather than PASS or FAIL.
- TrackScore.pass_rate excludes skipped cases from the denominator.
- TrackScore.finalize_score() uses pass_rate directly — the previous +10
  bonus at ≥90% pass_rate was score inflation and has been removed (T-13).
- run_case() handles None as the first return value → SKIP.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from config import PROJECT_ROOT


@dataclass
class AcceptanceCase:
    name: str
    passed: bool
    detail: str = ""
    duration_ms: float = 0.0
    skipped: bool = False  # True when fn() returned (None, reason)


@dataclass
class TrackScore:
    track: str
    current_pct: float
    target_pct: float
    cases: list[AcceptanceCase] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def gap(self) -> float:
        return max(0.0, self.target_pct - self.current_pct)

    @property
    def pass_rate(self) -> float:
        """Pass rate over non-skipped cases only."""
        active = [c for c in self.cases if not c.skipped]
        if not active:
            return 0.0
        return 100.0 * sum(1 for c in active if c.passed) / len(active)

    def finalize_score(self) -> None:
        # Score == pass rate, no inflation bonus (T-13 fix).
        self.current_pct = round(min(100.0, max(0.0, self.pass_rate)), 1)


def run_case(name: str, fn) -> AcceptanceCase:
    """
    Run *fn* and return an AcceptanceCase.

    fn() must return one of:
      - (bool, str)       → PASS/FAIL with detail
      - (None, str)       → SKIP with reason (case excluded from pass_rate)
    Any exception is caught and recorded as FAIL.
    """
    start = time.perf_counter()
    skipped = False
    try:
        result = fn()
        ok, detail = result[0], result[1]
        if ok is None:
            skipped = True
            ok = False
            detail = detail or "skip"
        else:
            detail = detail or ("ok" if ok else "failed")
    except Exception as exc:
        ok = False
        detail = str(exc)[:300]
    return AcceptanceCase(
        name=name,
        passed=bool(ok),
        detail=detail,
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
        skipped=skipped,
    )


def write_report(path: Path, lines: list[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def format_track_report(score: TrackScore, *, extra_sections: list[str] | None = None) -> str:
    active = [c for c in score.cases if not c.skipped]
    skipped_count = len(score.cases) - len(active)
    passed_count = sum(1 for c in active if c.passed)
    lines = [
        f"# {score.track} Reliability Report",
        "",
        f"- current_score: {score.current_pct}%",
        f"- target_score: {score.target_pct}%",
        f"- gap: {score.gap}%",
        f"- pass_rate: {score.pass_rate:.1f}% ({passed_count}/{len(active)} active"
        + (f", {skipped_count} skipped" if skipped_count else "")
        + ")",
        "",
        "## Acceptance Results",
    ]
    for case in score.cases:
        if case.skipped:
            status = "SKIP"
        elif case.passed:
            status = "PASS"
        else:
            status = "FAIL"
        lines.append(f"- [{status}] {case.name} ({case.duration_ms} ms) — {case.detail[:200]}")
    if score.blockers:
        lines.extend(["", "## Primary Blockers", *[f"- {b}" for b in score.blockers]])
    if score.recommendations:
        lines.extend(["", "## Recommended Actions", *[f"- {r}" for r in score.recommendations]])
    if extra_sections:
        lines.extend(["", *extra_sections])
    return "\n".join(lines)


def reports_dir() -> Path:
    return PROJECT_ROOT / "reports"
