"""Strict measured validation (Phase 66.1) — mock never counts as real."""

from __future__ import annotations

import json
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from config import PROJECT_ROOT

SCENARIOS_PER_CATEGORY = 50


class ScenarioStatus(str, Enum):
    REAL_PASS = "real_pass"
    MOCK_PASS = "mock_pass"
    DEGRADED_PASS = "degraded_pass"
    FAIL = "fail"
    CRASH = "crash"


class ProviderKind(str, Enum):
    REAL = "real"
    MOCK = "mock"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class StrictScenarioOutcome:
    status: ScenarioStatus
    provider: ProviderKind
    user_visible: bool = False
    external_action_performed: bool = False
    evidence_path: str = ""
    error_message: str = ""
    detail: str = ""
    recovered: bool = False


@dataclass
class StrictScenarioRecord:
    category: str
    scenario_id: str
    status: ScenarioStatus
    provider: ProviderKind
    user_visible: bool
    external_action_performed: bool
    evidence_path: str
    latency_ms: float
    error_message: str = ""
    detail: str = ""
    recovered: bool = False
    crashed: bool = False


StrictScenarioFn = Callable[[], StrictScenarioOutcome]


@dataclass
class StrictCategoryMeasurement:
    category: str
    scenarios: list[StrictScenarioRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.scenarios)

    def _count(self, status: ScenarioStatus) -> int:
        return sum(1 for s in self.scenarios if s.status == status)

    def _rate(self, status: ScenarioStatus) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self._count(status) / self.total, 2)

    @property
    def real_success_rate(self) -> float:
        return self._rate(ScenarioStatus.REAL_PASS)

    @property
    def mock_success_rate(self) -> float:
        return self._rate(ScenarioStatus.MOCK_PASS)

    @property
    def degraded_success_rate(self) -> float:
        return self._rate(ScenarioStatus.DEGRADED_PASS)

    @property
    def failure_rate(self) -> float:
        return self._rate(ScenarioStatus.FAIL)

    @property
    def crash_rate(self) -> float:
        return self._rate(ScenarioStatus.CRASH)

    @property
    def average_latency_ms(self) -> float:
        if not self.scenarios:
            return 0.0
        return round(sum(s.latency_ms for s in self.scenarios) / len(self.scenarios), 2)

    def top_real_blockers(self, n: int = 5) -> list[tuple[str, int]]:
        reasons = [
            s.error_message
            for s in self.scenarios
            if s.status in (ScenarioStatus.FAIL, ScenarioStatus.CRASH, ScenarioStatus.DEGRADED_PASS)
            and s.error_message
        ]
        return Counter(reasons).most_common(n)

    def recommended_fixes(self) -> list[str]:
        fixes: list[str] = []
        for reason, count in self.top_real_blockers(8):
            low = reason.lower()
            if "mock" in low:
                fixes.append(f"Replace mock fallback with real providers ({count}).")
            elif "playwright" in low or "browser_process" in low:
                fixes.append(f"Fix Playwright session visibility and process health ({count}).")
            elif "ocr" in low or "tesseract" in low:
                fixes.append(f"Install/configure Tesseract for real OCR ({count}).")
            elif "computer_control" in low or "disabled" in low:
                fixes.append(f"Enable COMPUTER_CONTROL_ENABLED and desktop operator ({count}).")
            elif "simulated" in low or "routing" in low:
                fixes.append(f"Run live voice hardware tests separately ({count}).")
            else:
                fixes.append(f"Address blocker: {reason} ({count}).")
        seen: set[str] = set()
        out: list[str] = []
        for f in fixes:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out[:8]


def run_strict_scenario(category: str, scenario_id: str, fn: StrictScenarioFn) -> StrictScenarioRecord:
    start = time.perf_counter()
    crashed = False
    outcome = StrictScenarioOutcome(
        status=ScenarioStatus.FAIL,
        provider=ProviderKind.UNAVAILABLE,
        error_message="not_run",
    )
    try:
        outcome = fn()
    except Exception as exc:
        crashed = True
        outcome = StrictScenarioOutcome(
            status=ScenarioStatus.CRASH,
            provider=ProviderKind.UNAVAILABLE,
            error_message=f"{type(exc).__name__}: {exc}"[:300],
            detail=traceback.format_exc()[-400:],
        )
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    if crashed:
        status = ScenarioStatus.CRASH
    else:
        status = outcome.status
    return StrictScenarioRecord(
        category=category,
        scenario_id=scenario_id,
        status=status,
        provider=outcome.provider,
        user_visible=outcome.user_visible,
        external_action_performed=outcome.external_action_performed,
        evidence_path=outcome.evidence_path,
        latency_ms=latency_ms,
        error_message=outcome.error_message[:300],
        detail=outcome.detail[:400],
        recovered=outcome.recovered,
        crashed=crashed,
    )


def run_strict_category(category: str, scenarios: list[tuple[str, StrictScenarioFn]]) -> StrictCategoryMeasurement:
    if len(scenarios) != SCENARIOS_PER_CATEGORY:
        raise ValueError(f"{category}: expected {SCENARIOS_PER_CATEGORY} scenarios, got {len(scenarios)}")
    m = StrictCategoryMeasurement(category=category)
    for sid, fn in scenarios:
        m.scenarios.append(run_strict_scenario(category, sid, fn))
    return m


def reports_dir() -> Path:
    return PROJECT_ROOT / "reports"


def write_strict_raw_json(measurements: list[StrictCategoryMeasurement], path: Path | None = None) -> Path:
    path = path or (reports_dir() / "phase66_strict_validation_raw.json")
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios_per_category": SCENARIOS_PER_CATEGORY,
        "primary_score": "real_success_rate_only",
        "categories": [
            {
                "category": m.category,
                "total": m.total,
                "real_success_rate": m.real_success_rate,
                "mock_success_rate": m.mock_success_rate,
                "degraded_success_rate": m.degraded_success_rate,
                "failure_rate": m.failure_rate,
                "crash_rate": m.crash_rate,
                "average_latency_ms": m.average_latency_ms,
                "scenarios": [asdict(s) for s in m.scenarios],
            }
            for m in measurements
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def format_strict_report(measurements: list[StrictCategoryMeasurement]) -> str:
    lines = [
        "# Strict Real World Validation Report (Phase 66.1)",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Scenarios per category: {SCENARIOS_PER_CATEGORY}",
        "",
        "**Primary readiness score: real_success_rate only.**",
        "Mock fallback, simulated routing, and degraded passes do not count as real product success.",
        "",
        "## Summary",
        "",
        "| Category | Real % | Mock % | Degraded % | Fail % | Crash % | Avg latency | Top blocker |",
        "|----------|--------|--------|------------|--------|---------|-------------|-------------|",
    ]
    for m in measurements:
        blocker = m.top_real_blockers(1)
        top = blocker[0][0][:60] if blocker else "none"
        lines.append(
            f"| {m.category} | {m.real_success_rate} | {m.mock_success_rate} | {m.degraded_success_rate} | "
            f"{m.failure_rate} | {m.crash_rate} | {m.average_latency_ms} | {top} |"
        )
    lines.append("")
    for m in measurements:
        lines.extend(
            [
                f"## {m.category}",
                "",
                f"- **real_success_rate (primary):** {m.real_success_rate}%",
                f"- **mock_success_rate:** {m.mock_success_rate}%",
                f"- **degraded_success_rate:** {m.degraded_success_rate}%",
                f"- **failure_rate:** {m.failure_rate}%",
                f"- **crash_rate:** {m.crash_rate}%",
                f"- **average_latency:** {m.average_latency_ms} ms",
                "",
                "### Top real blockers",
            ]
        )
        tops = m.top_real_blockers(10)
        if tops:
            for reason, cnt in tops:
                lines.append(f"- ({cnt}) {reason[:220]}")
        else:
            lines.append("- none")
        lines.extend(["", "### Recommended fixes"])
        recs = m.recommended_fixes()
        lines.extend([f"- {r}" for r in recs] if recs else ["- none"])
        lines.append("")
    return "\n".join(lines)


def write_strict_real_world_report(measurements: list[StrictCategoryMeasurement]) -> str:
    body = format_strict_report(measurements)
    path = reports_dir() / "strict_real_world_validation_report.md"
    path.write_text(body, encoding="utf-8")
    write_strict_raw_json(measurements)
    return body
