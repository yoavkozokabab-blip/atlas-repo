"""Phase 72 — tool-use router wiring tests.

Drives the real CommandRouter + classifier + actions, with an injected fake
provider (no live browser) so the safety contract is proven deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.intent_classifier import match_tool_use_command
from brain.router import CommandRouter
from core import confirmation
from core.types import ActionStatus, Intent
from tooluse import pending
from tooluse.contracts import Observation, PlanStep, StepKind, StepOutcome
from tooluse.recovery import RecoveryDecision
import actions.tool_use_actions as tua


# ---------------------------------------------------------------------------
# Fake provider (no network). Records the exact steps it was asked to execute.
# ---------------------------------------------------------------------------

class FakeProvider:
    def __init__(self, *, real: bool = True):
        self._real = real
        self._navigated = False
        self.executed: list[str] = []
        self.closed = False
        self.constructed = True

    def is_real(self) -> bool:
        return self._real

    def observe(self) -> Observation:
        if not self._real:
            return Observation(real=False, provider="unavailable")
        if not self._navigated:
            return Observation(
                real=True, provider="fake",
                url="https://www.marginalia-search.com/search?query=x",
                title="Search Results",
                links=[{"title": "Best", "url": "https://example.com/best"}],
                visible_text="results page with links and descriptions here",
            )
        return Observation(
            real=True, provider="fake",
            url="https://example.com/best", title="Best Result Page",
            headings=["Welcome"], visible_text="A substantial article body long enough to summarize.",
        )

    def execute(self, step: PlanStep) -> StepOutcome:
        self.executed.append(step.kind.value)
        if step.kind == StepKind.OPEN_RESULT:
            self._navigated = True
        return StepOutcome(ok=True, detail=f"did {step.kind.value}")

    def apply_recovery(self, decision: RecoveryDecision, step: PlanStep) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class ExplodingProvider:
    """Fails the test if constructed/used — proves 'no execution' paths."""
    def __init__(self):
        raise AssertionError("provider must not be constructed for this command")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    confirmation.clear_all()
    pending.reset_for_tests()
    from tooluse import audit
    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    audit.reset_for_tests()
    tua.set_tool_provider_factory(None)
    yield
    confirmation.clear_all()
    pending.reset_for_tests()
    tua.set_tool_provider_factory(None)


# ---------------------------------------------------------------------------
# 1. Intent classification
# ---------------------------------------------------------------------------

def test_intent_classification_of_three_commands():
    assert match_tool_use_command("plan tool task python release notes").intent == Intent.PLAN_TOOL_TASK
    assert match_tool_use_command("run tool task python release notes").intent == Intent.RUN_TOOL_TASK
    assert match_tool_use_command("research python release notes").intent == Intent.RUN_TOOL_TASK
    assert match_tool_use_command("look up mars facts and summarize").intent == Intent.RUN_TOOL_TASK
    assert match_tool_use_command("show last tool run").intent == Intent.SHOW_LAST_TOOL_RUN
    # goal captured
    assert match_tool_use_command("research mars facts").params["goal"] == "mars facts"
    # non-tool text is not hijacked
    assert match_tool_use_command("open chrome") is None
    assert match_tool_use_command("summarize this page") is None


def test_full_classify_routes_to_tool_intent():
    from brain.intent_classifier import classify
    assert classify("run tool task python release notes").intent == Intent.RUN_TOOL_TASK


# ---------------------------------------------------------------------------
# 2. Preview-only command does not execute
# ---------------------------------------------------------------------------

def test_plan_command_does_not_execute():
    tua.set_tool_provider_factory(ExplodingProvider)  # would raise if constructed
    router = CommandRouter()
    result = router.route("plan tool task python release notes")
    assert result.status == ActionStatus.SUCCESS
    assert "DRY RUN" in result.summary
    assert pending.get_last_run() is None  # nothing executed


# ---------------------------------------------------------------------------
# 3. Run requires confirmation
# ---------------------------------------------------------------------------

def test_run_requires_confirmation_before_execution():
    tua.set_tool_provider_factory(ExplodingProvider)  # must NOT be built pre-confirm
    router = CommandRouter()
    result = router.route("run tool task python release notes")
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert result.confirmation_id
    assert "DRY RUN" in result.summary  # full plan previewed
    assert pending.get_pinned_plan(result.confirmation_id) is not None
    assert pending.get_last_run() is None  # not executed yet


# ---------------------------------------------------------------------------
# 4. Forbidden goals block before execution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "run tool task buy a laptop",
    "run tool task book a hotel in paris",
    "research how to log in to my bank",
])
def test_forbidden_goals_blocked_before_execution(text, tmp_path):
    tua.set_tool_provider_factory(ExplodingProvider)
    router = CommandRouter()
    result = router.route(text)
    assert result.status == ActionStatus.BLOCKED
    assert pending.get_last_run() is None
    # blocked attempt is audited
    audit_file = Path(tmp_path) / "tool_use_audit.jsonl"
    assert audit_file.is_file()
    rows = [json.loads(l) for l in audit_file.read_text().splitlines() if l.strip()]
    assert any(r["event"] == "blocked" for r in rows)


# ---------------------------------------------------------------------------
# 5. Mock/unavailable provider cannot report success
# ---------------------------------------------------------------------------

def test_unavailable_provider_cannot_report_success():
    tua.set_tool_provider_factory(lambda: FakeProvider(real=False))
    router = CommandRouter()
    r1 = router.route("run tool task python release notes")
    assert r1.status == ActionStatus.CONFIRMATION_REQUIRED
    r2 = router.route("yes")
    assert r2.status == ActionStatus.BLOCKED      # NOT success
    assert "blocked_unavailable" in r2.summary or "unavailable" in r2.summary.lower()


# ---------------------------------------------------------------------------
# 6. Approved pinned plan is exactly what runs
# ---------------------------------------------------------------------------

def test_approved_pinned_plan_is_what_runs():
    fake = FakeProvider(real=True)
    tua.set_tool_provider_factory(lambda: fake)
    router = CommandRouter()
    r1 = router.route("run tool task python release notes")
    cid = r1.confirmation_id
    pinned = pending.get_pinned_plan(cid)
    pinned_kinds = [s.kind.value for s in pinned.steps]

    r2 = router.route("yes")
    assert r2.status == ActionStatus.SUCCESS
    # The provider executed exactly the pinned plan's steps, in order.
    assert fake.executed == pinned_kinds
    assert fake.closed is True
    # Pinned plan consumed after execution.
    assert pending.get_pinned_plan(cid) is None


# ---------------------------------------------------------------------------
# 7. Audit log includes per-step verification/status
# ---------------------------------------------------------------------------

def test_audit_log_has_per_step_verification(tmp_path):
    tua.set_tool_provider_factory(lambda: FakeProvider(real=True))
    router = CommandRouter()
    router.route("run tool task python release notes")
    router.route("yes")

    audit_file = Path(tmp_path) / "tool_use_audit.jsonl"
    rows = [json.loads(l) for l in audit_file.read_text().splitlines() if l.strip()]
    run_rows = [r for r in rows if r["event"] == "run"]
    assert run_rows, "expected a run audit record"
    rec = run_rows[-1]
    assert rec["final_status"] == "success"
    assert rec["approved"] is True
    assert len(rec["steps"]) == 4
    for step in rec["steps"]:
        assert "status" in step and "verification_ok" in step and "verification_reason" in step
    assert rec["plan_hash"]  # provenance present


# ---------------------------------------------------------------------------
# 8. Show last tool run is read-only
# ---------------------------------------------------------------------------

def test_show_last_tool_run_is_read_only():
    tua.set_tool_provider_factory(lambda: FakeProvider(real=True))
    router = CommandRouter()
    router.route("run tool task python release notes")
    router.route("yes")

    # show-last must not build a provider
    tua.set_tool_provider_factory(ExplodingProvider)
    result = router.route("show last tool run")
    assert result.status == ActionStatus.SUCCESS
    assert result.data.get("read_only") is True
    assert "task run" in result.summary.lower()


def test_show_last_when_none():
    tua.set_tool_provider_factory(ExplodingProvider)
    router = CommandRouter()
    result = router.route("show last tool run")
    assert result.status == ActionStatus.SUCCESS
    assert "no tool run" in result.summary.lower()
