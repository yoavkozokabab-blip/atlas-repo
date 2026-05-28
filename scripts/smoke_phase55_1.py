"""Smoke test for Phase 55.1 root cause action wiring."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from brain.operational_command_phrases import match_operational_priority_commands
from core.intent_validation import run_startup_intent_validation, validate_phase55_runtime_wiring
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from runtime.background_tasks import reset_background_engine_for_tests


def _setup_isolated_data(tmp: Path) -> None:
    import config

    config.DATA_DIR = tmp / "data"
    config.SESSION_STATE_PATH = config.DATA_DIR / "session_state.json"
    import assistant.root_cause_engine as rce

    rce.ROOT_CAUSES_PATH = config.DATA_DIR / "root_causes.json"
    import assistant.verification_plans as vp

    vp.PLANS_PATH = config.DATA_DIR / "verification_plans.json"
    import assistant.evidence_collector as ec

    ec.EVIDENCE_PATH = config.DATA_DIR / "root_cause_evidence.json"
    import assistant.confidence_tracking as ct

    ct.CONFIDENCE_PATH = config.DATA_DIR / "confidence_history.json"
    import assistant.hypothesis_engine as he

    he.HYPOTHESES_PATH = config.DATA_DIR / "hypotheses.json"
    import investigation.blocker_trends as bt

    bt.TRENDS_PATH = config.DATA_DIR / "blocker_trends.json"


def _run_through_runtime(phrase: str, expected: Intent) -> str:
    req = match_operational_priority_commands(phrase)
    assert req is not None, phrase
    assert req.intent == expected, (phrase, req.intent, expected)

    gate = validate_intent(req)
    assert gate is None, (phrase, gate.summary if gate else None)

    result = ActionRegistry().execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary)
    assert "not implemented" not in result.summary.lower(), (phrase, result.summary)
    print(f"OK runtime {phrase!r}")
    return result.summary


def main() -> None:
    os.environ["JARVIS_SKIP_INVESTIGATION_SCHEDULER"] = "1"

    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    wiring_issues = validate_phase55_runtime_wiring()
    assert not wiring_issues, [i.format() for i in wiring_issues]
    print("OK validate_phase55_runtime_wiring")

    tmp = Path(tempfile.mkdtemp()) / "phase55_1"
    _setup_isolated_data(tmp)
    reset_background_engine_for_tests()

    for phrase, intent in (
        ("summarize root causes", Intent.SUMMARIZE_ROOT_CAUSES),
        ("show confidence evolution", Intent.SHOW_CONFIDENCE_EVOLUTION),
        ("show verification plans", Intent.SHOW_VERIFICATION_PLANS),
        ("verify root causes", Intent.VERIFY_ROOT_CAUSES),
        ("explain why trades are blocked", Intent.EXPLAIN_WHY_TRADES_ARE_BLOCKED),
    ):
        summary = _run_through_runtime(phrase, intent)
        assert summary.strip(), phrase

    print("SMOKE PASS phase55_1")


if __name__ == "__main__":
    main()
