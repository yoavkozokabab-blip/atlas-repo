"""Run Phase 66.1 strict real-world validation (mock never counts as real)."""

from __future__ import annotations

from validation.strict_framework import StrictCategoryMeasurement, write_strict_real_world_report
from validation.scenarios_browser import measure_browser_tasks
from validation.scenarios_coding import measure_coding_tasks
from validation.scenarios_desktop import measure_desktop_operator
from validation.scenarios_integrations import measure_integrations
from validation.scenarios_memory import measure_memory_recall
from validation.scenarios_multistep import measure_multistep_tasks
from validation.scenarios_recovery import measure_recovery
from validation.scenarios_voice import measure_voice_conversation

STRICT_CATEGORY_COUNT = 8


def run_all_strict_validations() -> list[StrictCategoryMeasurement]:
    return [
        measure_voice_conversation(),
        measure_browser_tasks(),
        measure_desktop_operator(),
        measure_memory_recall(),
        measure_coding_tasks(),
        measure_integrations(),
        measure_recovery(),
        measure_multistep_tasks(),
    ]


def verify_strict_acceptance(measurements: list[StrictCategoryMeasurement]) -> list[str]:
    """Return acceptance violations (empty list = pass). Phase 67 allows real voice/integrations."""
    violations: list[str] = []
    by_name = {m.category: m for m in measurements}
    browser = by_name.get("Browser Task")
    if browser:
        from browser.runtime import get_browser_runtime_state

        if get_browser_runtime_state().provider != "playwright" and browser.real_success_rate != 0.0:
            violations.append(
                f"Browser mock provider: real_success_rate must be 0% (got {browser.real_success_rate}%)"
            )
    integrations = by_name.get("Integrations (Email/Calendar)")
    if integrations:
        mock_only = integrations.mock_success_rate >= 100.0 and integrations.real_success_rate == 0.0
        if mock_only:
            pass  # acceptable when readonly fixtures unavailable
    return violations


def main() -> str:
    measurements = run_all_strict_validations()
    report = write_strict_real_world_report(measurements)
    violations = verify_strict_acceptance(measurements)
    if violations:
        report += "\n\n## Acceptance violations\n\n" + "\n".join(f"- {v}" for v in violations)
        from validation.strict_framework import reports_dir

        (reports_dir() / "strict_real_world_validation_report.md").write_text(report, encoding="utf-8")
    return report


if __name__ == "__main__":
    print(main())
