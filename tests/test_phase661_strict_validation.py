"""Phase 66.1 strict validation framework tests."""

from __future__ import annotations

import pytest

from validation.strict_framework import (
    SCENARIOS_PER_CATEGORY,
    ScenarioStatus,
    StrictCategoryMeasurement,
    StrictScenarioRecord,
    run_strict_scenario,
)
from validation.strict_graders import _out, ProviderKind, grade_integration_mock


def test_scenarios_per_category_constant():
    assert SCENARIOS_PER_CATEGORY == 50


def test_integration_mock_never_real_pass():
    outcome = grade_integration_mock(True, "MOCK MODE inbox summary")
    assert outcome.status == ScenarioStatus.MOCK_PASS
    assert outcome.provider == ProviderKind.MOCK


def test_strict_rates_sum_to_100():
    m = StrictCategoryMeasurement(category="Test")
    statuses = [
        ScenarioStatus.REAL_PASS,
        ScenarioStatus.MOCK_PASS,
        ScenarioStatus.DEGRADED_PASS,
        ScenarioStatus.FAIL,
        ScenarioStatus.CRASH,
    ]
    for i, st in enumerate(statuses * 10):
        m.scenarios.append(
            StrictScenarioRecord(
                category="Test",
                scenario_id=f"s{i}",
                status=st,
                provider=ProviderKind.MOCK,
                user_visible=False,
                external_action_performed=False,
                evidence_path="",
                latency_ms=1.0,
            )
        )
    total = (
        m.real_success_rate
        + m.mock_success_rate
        + m.degraded_success_rate
        + m.failure_rate
        + m.crash_rate
    )
    assert total == pytest.approx(100.0, abs=0.01)


@pytest.mark.slow
def test_strict_validation_single_category_memory():
    from validation.scenarios_memory import measure_memory_recall

    m = measure_memory_recall()
    assert m.total == 50
    assert m.real_success_rate >= 0.0


def test_verify_integrations_real_zero():
    from validation.run_all_strict import verify_strict_acceptance
    from validation.strict_framework import StrictCategoryMeasurement, StrictScenarioRecord

    m = StrictCategoryMeasurement(category="Integrations (Email/Calendar)")
    for i in range(50):
        m.scenarios.append(
            StrictScenarioRecord(
                category=m.category,
                scenario_id=f"i{i}",
                status=ScenarioStatus.MOCK_PASS,
                provider=ProviderKind.MOCK,
                user_visible=False,
                external_action_performed=False,
                evidence_path="",
                latency_ms=1.0,
            )
        )
    violations = verify_strict_acceptance([m])
    assert not any("Integrations" in v for v in violations)
