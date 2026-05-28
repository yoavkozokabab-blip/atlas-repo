"""Phase 66 validation framework tests."""

from __future__ import annotations

import pytest

from validation.framework import SCENARIOS_PER_CATEGORY


def test_scenarios_per_category_constant():
    assert SCENARIOS_PER_CATEGORY == 50


@pytest.mark.slow
def test_full_validation_runs():
    from validation.run_all_strict import run_all_strict_validations, STRICT_CATEGORY_COUNT

    measurements = run_all_strict_validations()
    assert len(measurements) == STRICT_CATEGORY_COUNT
    for m in measurements:
        assert m.total == 50
        total = (
            m.real_success_rate
            + m.mock_success_rate
            + m.degraded_success_rate
            + m.failure_rate
            + m.crash_rate
        )
        assert total == pytest.approx(100.0, abs=0.01)
        assert m.average_latency_ms >= 0
