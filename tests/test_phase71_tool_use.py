"""Phase 71 — Real Tool-Use Foundation tests.

These tests prove the SAFETY CONTRACT deterministically, with a scripted fake
provider (no live browser).  A separate smoke script exercises the real
Playwright provider end-to-end.
"""

from __future__ import annotations

import pytest

from tooluse.contracts import (
    ForbiddenGoalError,
    Observation,
    PlanStep,
    RiskLevel,
    RunStatus,
    StepKind,
    StepOutcome,
    StepStatus,
)
from tooluse.executor import ToolUseExecutor, approve_all, deny_all
from tooluse.planner import build_search_open_summarize_plan
from tooluse.recovery import RecoveryDecision, RecoveryKind
from tooluse.verifier import verify_step


# ---------------------------------------------------------------------------
# Fake provider — scripted, deterministic, used ONLY in tests.
# ---------------------------------------------------------------------------

class FakeProvider:
    def __init__(self, *, real: bool = True, open_result_fails_first: bool = False):
        self._real = real
        self.closed = False
        self._navigated = False
        self._open_attempts = 0
        self._open_result_fails_first = open_result_fails_first
        self.recovery_calls: list[str] = []

    def is_real(self) -> bool:
        return self._real

    def observe(self) -> Observation:
        if not self._real:
            return Observation(real=False, provider="unavailable")
        if not self._navigated:
            # On the search-results page.
            return Observation(
                real=True, provider="fake",
                url="https://duckduckgo.com/html/?q=test",
                title="Search Results",
                links=[{"title": "Best Result", "url": "https://example.com/best"}],
                visible_text="results page with several links and descriptions here",
            )
        return Observation(
            real=True, provider="fake",
            url="https://example.com/best",
            title="Best Result Page",
            headings=["Welcome", "About"],
            visible_text="This is a substantial article body with enough text to summarize properly.",
        )

    def execute(self, step: PlanStep) -> StepOutcome:
        if step.kind == StepKind.OPEN_RESULT:
            self._open_attempts += 1
            if self._open_result_fails_first and self._open_attempts == 1:
                return StepOutcome(ok=False, detail="first open failed")
            self._navigated = True
            return StepOutcome(ok=True, detail="opened")
        return StepOutcome(ok=True, detail=f"did {step.kind.value}")

    def apply_recovery(self, decision: RecoveryDecision, step: PlanStep) -> None:
        self.recovery_calls.append(decision.kind.value)
        if decision.kind == RecoveryKind.NEXT_CANDIDATE:
            self._navigated = True  # recovery succeeds on retry

    def close(self) -> None:
        self.closed = True


def _plan():
    return build_search_open_summarize_plan("python release notes")


# ---------------------------------------------------------------------------
# Planner — dry run + forbidden guard
# ---------------------------------------------------------------------------

def test_plan_is_dry_run_and_has_expected_shape():
    plan = _plan()
    assert plan.is_dry_run is True
    kinds = [s.kind for s in plan.steps]
    assert kinds == [StepKind.OPEN_SESSION, StepKind.SEARCH, StepKind.OPEN_RESULT, StepKind.SUMMARIZE]
    # External steps require approval; the read-only summary does not.
    assert all(s.requires_approval for s in plan.steps if s.is_external)
    assert plan.steps[-1].requires_approval is False


@pytest.mark.parametrize("goal", [
    "buy me a laptop", "book a hotel", "order groceries",
    "submit the form", "log in to my bank", "download the installer",
    "delete my account", "send this email",
])
def test_forbidden_goals_are_rejected(goal):
    with pytest.raises(ForbiddenGoalError):
        build_search_open_summarize_plan(goal)


def test_planner_never_emits_irreversible_steps():
    plan = _plan()
    assert all(s.risk != RiskLevel.IRREVERSIBLE for s in plan.steps)


# ---------------------------------------------------------------------------
# Approval gate
# ---------------------------------------------------------------------------

def test_deny_all_blocks_first_external_step():
    run = ToolUseExecutor(FakeProvider(), approver=deny_all).run(_plan())
    assert run.status == RunStatus.APPROVAL_DENIED
    assert run.steps[0].status == StepStatus.APPROVAL_DENIED
    # Nothing past the first external step executed.
    assert len(run.steps) == 1


def test_approval_required_for_every_external_step():
    seen: list[str] = []

    def approver(step: PlanStep) -> bool:
        seen.append(step.kind.value)
        return True

    ToolUseExecutor(FakeProvider(), approver=approver).run(_plan())
    # All three external steps were presented for approval (summary is not).
    assert seen == ["open_session", "search", "open_result"]


# ---------------------------------------------------------------------------
# No mock success
# ---------------------------------------------------------------------------

def test_unreal_provider_blocks_never_succeeds():
    run = ToolUseExecutor(FakeProvider(real=False), approver=approve_all).run(_plan())
    assert run.status == RunStatus.BLOCKED_UNAVAILABLE
    assert run.ok is False
    # The very first external step is blocked, not reported as success.
    assert run.steps[0].status == StepStatus.BLOCKED_UNAVAILABLE


# ---------------------------------------------------------------------------
# Happy path (real provider, approved) — verified success
# ---------------------------------------------------------------------------

def test_full_run_succeeds_with_real_provider_and_approval():
    provider = FakeProvider(real=True)
    run = ToolUseExecutor(provider, approver=approve_all).run(_plan())
    assert run.status == RunStatus.SUCCESS
    assert [r.status for r in run.steps] == [StepStatus.SUCCESS] * 4
    assert all(r.verification and r.verification.ok for r in run.steps)
    assert "Best Result Page" in run.summary
    assert provider.closed is True  # session always cleaned up


# ---------------------------------------------------------------------------
# Recovery on UI-change / failed navigation
# ---------------------------------------------------------------------------

def test_open_result_recovers_via_next_candidate():
    provider = FakeProvider(real=True, open_result_fails_first=True)
    run = ToolUseExecutor(provider, approver=approve_all).run(_plan())
    assert run.status == RunStatus.SUCCESS
    open_step = next(r for r in run.steps if r.step.kind == StepKind.OPEN_RESULT)
    assert open_step.recovery_attempts >= 1
    assert "next_candidate" in provider.recovery_calls


# ---------------------------------------------------------------------------
# Verifier unit checks
# ---------------------------------------------------------------------------

def test_verifier_rejects_open_result_still_on_search_engine():
    step = PlanStep(3, StepKind.OPEN_RESULT, "open", RiskLevel.EXTERNAL, True)
    before = Observation(real=True, provider="fake", url="https://duckduckgo.com/html/?q=x")
    after = Observation(real=True, provider="fake", url="https://duckduckgo.com/html/?q=x", title="Results")
    assert verify_step(step, before, after).ok is False


def test_verifier_accepts_navigation_off_search_engine():
    step = PlanStep(3, StepKind.OPEN_RESULT, "open", RiskLevel.EXTERNAL, True)
    before = Observation(real=True, provider="fake", url="https://duckduckgo.com/html/?q=x")
    after = Observation(real=True, provider="fake", url="https://example.com/a", title="Example")
    assert verify_step(step, before, after).ok is True


def test_verifier_requires_real_provider_for_external_step():
    step = PlanStep(2, StepKind.SEARCH, "search", RiskLevel.EXTERNAL, True)
    before = Observation(real=False, provider="unavailable")
    after = Observation(real=False, provider="unavailable")
    assert verify_step(step, before, after).ok is False
