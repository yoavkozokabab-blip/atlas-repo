"""Measured acceptance framework (Phase 66) — no estimated scores."""

from __future__ import annotations

import json
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from config import PROJECT_ROOT

SCENARIOS_PER_CATEGORY = 50

ScenarioFn = Callable[[], tuple[bool, str, bool]]  # passed, detail, recovered


@dataclass
class ScenarioRecord:
    category: str
    scenario_id: str
    passed: bool
    latency_ms: float
    crashed: bool
    recovered: bool
    failure_reason: str = ""
    detail: str = ""


@dataclass
class CategoryMeasurement:
    category: str
    scenarios: list[ScenarioRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.scenarios)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scenarios if s.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def crash_count(self) -> int:
        return sum(1 for s in self.scenarios if s.crashed)

    @property
    def recovery_count(self) -> int:
        return sum(1 for s in self.scenarios if s.recovered)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.passed / self.total, 2)

    @property
    def failure_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.failed / self.total, 2)

    @property
    def average_execution_time_ms(self) -> float:
        if not self.scenarios:
            return 0.0
        return round(sum(s.latency_ms for s in self.scenarios) / len(self.scenarios), 2)

    def top_failure_reasons(self, n: int = 5) -> list[tuple[str, int]]:
        reasons = [s.failure_reason for s in self.scenarios if not s.passed and s.failure_reason]
        return Counter(reasons).most_common(n)

    def recommended_fixes(self) -> list[str]:
        fixes: list[str] = []
        for reason, count in self.top_failure_reasons(8):
            low = reason.lower()
            if "disabled" in low or "not enabled" in low:
                fixes.append(f"Enable required feature flags ({count} failures referencing disabled state).")
            elif "mock" in low:
                fixes.append(f"Install/configure real runtime dependencies; mock path hit {count} times.")
            elif "playwright" in low or "browser" in low:
                fixes.append(f"Stabilize Playwright session and run `playwright install chromium` ({count} failures).")
            elif "tesseract" in low or "ocr" in low:
                fixes.append(f"Install Tesseract OCR and set TESSERACT_CMD ({count} failures).")
            elif "memory" in low or "retrieve" in low:
                fixes.append(f"Run repair memory store and verify MEMORY_ENABLED ({count} failures).")
            elif "intent" in low or "classif" in low:
                fixes.append(f"Fix intent routing phrases and operational command map ({count} failures).")
            elif "timeout" in low:
                fixes.append(f"Increase timeouts or reduce voice/TTS blocking work on hot path ({count} failures).")
            else:
                fixes.append(f"Investigate: {reason} ({count} occurrences).")
        # dedupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for f in fixes:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out[:8]


def run_scenario(category: str, scenario_id: str, fn: ScenarioFn) -> ScenarioRecord:
    start = time.perf_counter()
    crashed = False
    recovered = False
    passed = False
    detail = ""
    failure_reason = ""
    try:
        passed, detail, recovered = fn()
        if not passed:
            failure_reason = detail or "assertion_failed"
    except Exception as exc:
        crashed = True
        passed = False
        failure_reason = f"{type(exc).__name__}: {exc}"
        detail = traceback.format_exc()[-400:]
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return ScenarioRecord(
        category=category,
        scenario_id=scenario_id,
        passed=bool(passed),
        latency_ms=latency_ms,
        crashed=crashed,
        recovered=recovered,
        failure_reason=failure_reason[:300],
        detail=detail[:400],
    )


def run_category(category: str, scenarios: list[tuple[str, ScenarioFn]]) -> CategoryMeasurement:
    if len(scenarios) != SCENARIOS_PER_CATEGORY:
        raise ValueError(f"{category}: expected {SCENARIOS_PER_CATEGORY} scenarios, got {len(scenarios)}")
    measurement = CategoryMeasurement(category=category)
    for sid, fn in scenarios:
        measurement.scenarios.append(run_scenario(category, sid, fn))
    return measurement


def reports_dir() -> Path:
    return PROJECT_ROOT / "reports"


def write_raw_json(measurements: list[CategoryMeasurement], path: Path | None = None) -> Path:
    path = path or (reports_dir() / "phase66_validation_raw.json")
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios_per_category": SCENARIOS_PER_CATEGORY,
        "categories": [
            {
                "category": m.category,
                "total": m.total,
                "passed": m.passed,
                "failed": m.failed,
                "success_rate": m.success_rate,
                "failure_rate": m.failure_rate,
                "average_execution_time_ms": m.average_execution_time_ms,
                "crash_count": m.crash_count,
                "recovery_count": m.recovery_count,
                "scenarios": [asdict(s) for s in m.scenarios],
            }
            for m in measurements
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def format_real_world_report(measurements: list[CategoryMeasurement]) -> str:
    lines = [
        "# Real World Validation Report (Phase 66)",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Scenarios per category: {SCENARIOS_PER_CATEGORY} (measured, not estimated)",
        "",
        "## Summary",
        "",
        "| Category | Total | Pass | Fail | Success % | Failure % | Avg ms | Crashes | Recoveries |",
        "|----------|-------|------|------|-----------|-----------|--------|---------|------------|",
    ]
    for m in measurements:
        lines.append(
            f"| {m.category} | {m.total} | {m.passed} | {m.failed} | {m.success_rate} | "
            f"{m.failure_rate} | {m.average_execution_time_ms} | {m.crash_count} | {m.recovery_count} |"
        )
    lines.append("")
    for m in measurements:
        lines.extend(
            [
                f"## {m.category}",
                "",
                f"- **success_rate:** {m.success_rate}% ({m.passed}/{m.total})",
                f"- **failure_rate:** {m.failure_rate}% ({m.failed}/{m.total})",
                f"- **average_execution_time:** {m.average_execution_time_ms} ms",
                f"- **crash_count:** {m.crash_count}",
                f"- **recovery_count:** {m.recovery_count}",
                "",
                "### Top failure reasons",
            ]
        )
        tops = m.top_failure_reasons(10)
        if tops:
            for reason, cnt in tops:
                lines.append(f"- ({cnt}) {reason[:220]}")
        else:
            lines.append("- none")
        lines.extend(["", "### Recommended fixes"])
        recs = m.recommended_fixes()
        if recs:
            lines.extend([f"- {r}" for r in recs])
        else:
            lines.append("- none")
        lines.append("")
    return "\n".join(lines)


def write_real_world_report(measurements: list[CategoryMeasurement]) -> str:
    body = format_real_world_report(measurements)
    path = reports_dir() / "real_world_validation_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    write_raw_json(measurements)
    return body
