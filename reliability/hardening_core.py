"""Shared helpers for Phase 65 product hardening."""

from __future__ import annotations

import json
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
        if not self.cases:
            return 0.0
        return 100.0 * sum(1 for c in self.cases if c.passed) / len(self.cases)

    def finalize_score(self) -> None:
        rate = self.pass_rate
        # Blend structural checks with pass rate for conservative scoring.
        self.current_pct = round(min(100.0, max(0.0, rate * 0.85 + (10 if rate >= 90 else 0))), 1)


def run_case(name: str, fn) -> AcceptanceCase:
    start = time.perf_counter()
    try:
        ok, detail = fn()
        detail = detail or ("ok" if ok else "failed")
    except Exception as exc:
        ok = False
        detail = str(exc)[:300]
    return AcceptanceCase(
        name=name,
        passed=bool(ok),
        detail=detail,
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )


def write_report(path: Path, lines: list[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def format_track_report(score: TrackScore, *, extra_sections: list[str] | None = None) -> str:
    lines = [
        f"# {score.track} Reliability Report",
        "",
        f"- current_score: {score.current_pct}%",
        f"- target_score: {score.target_pct}%",
        f"- gap: {score.gap}%",
        f"- pass_rate: {score.pass_rate:.1f}% ({sum(1 for c in score.cases if c.passed)}/{len(score.cases)})",
        "",
        "## Acceptance Results",
    ]
    for case in score.cases:
        status = "PASS" if case.passed else "FAIL"
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
