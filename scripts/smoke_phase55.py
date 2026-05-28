"""Smoke test for Phase 55 autonomous root cause verification."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from assistant.confidence_tracking import _load as load_confidence
from assistant.root_cause_engine import _load as load_root_causes
from brain.intent_classifier import classify_rules
from brain.operational_command_phrases import match_operational_priority_commands
from core.intent_validation import run_startup_intent_validation
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
    import assistant.investigation_graph as ig

    ig.GRAPH_PATH = config.DATA_DIR / "investigation_graph.json"
    import assistant.hypothesis_engine as he

    he.HYPOTHESES_PATH = config.DATA_DIR / "hypotheses.json"
    import investigation.blocker_trends as bt

    bt.TRENDS_PATH = config.DATA_DIR / "blocker_trends.json"
    import assistant.intelligence_timeline as tl

    tl.TIMELINE_PATH = config.DATA_DIR / "intelligence_timeline.json"
    import assistant.investigation_cycles as ic

    ic.CYCLE_REPORT_DIR = tmp / "reports" / "autonomous_investigations"
    import assistant.notifications as nt

    nt.NOTIFICATIONS_PATH = config.DATA_DIR / "notifications.json"


def _assert_intent(phrase: str, expected: Intent) -> None:
    op = match_operational_priority_commands(phrase)
    rules = classify_rules(phrase)
    for label, req in (("operational", op), ("rules", rules)):
        assert req is not None, (phrase, label)
        assert req.intent == expected, (phrase, label, req.intent, expected)
    print(f"OK classify {phrase!r} -> {expected.value}")


def _run_action(registry: ActionRegistry, phrase: str, intent: Intent) -> str:
    action = registry._actions[intent.value]
    result = action.execute(CommandRequest(raw_text=phrase, intent=intent))
    assert result.status == ActionStatus.SUCCESS, (phrase, result.summary)
    print(f"OK action {phrase!r}")
    return result.summary


def main() -> None:
    os.environ["JARVIS_SKIP_INVESTIGATION_SCHEDULER"] = "1"
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    for phrase, intent in (
        ("summarize root causes", Intent.SUMMARIZE_ROOT_CAUSES),
        ("explain dominant root cause", Intent.EXPLAIN_DOMINANT_ROOT_CAUSE),
        ("show verification plans", Intent.SHOW_VERIFICATION_PLANS),
        ("verify root causes", Intent.VERIFY_ROOT_CAUSES),
        ("show confidence evolution", Intent.SHOW_CONFIDENCE_EVOLUTION),
        ("show contradictory evidence", Intent.SHOW_CONTRADICTORY_EVIDENCE),
        ("suggest experiments", Intent.SUGGEST_EXPERIMENTS),
        ("show root cause graph", Intent.SHOW_ROOT_CAUSE_GRAPH),
    ):
        _assert_intent(phrase, intent)

    tmp = Path(tempfile.mkdtemp()) / "phase55"
    _setup_isolated_data(tmp)
    reset_background_engine_for_tests()
    registry = ActionRegistry()

    _run_action(registry, "summarize root causes", Intent.SUMMARIZE_ROOT_CAUSES)
    assert (tmp / "data" / "root_causes.json").is_file()
    print("OK root causes persisted")

    _run_action(registry, "explain dominant root cause", Intent.EXPLAIN_DOMINANT_ROOT_CAUSE)
    _run_action(registry, "show verification plans", Intent.SHOW_VERIFICATION_PLANS)
    assert (tmp / "data" / "verification_plans.json").is_file()
    print("OK verification plans persisted")

    _run_action(registry, "verify root causes", Intent.VERIFY_ROOT_CAUSES)
    assert (tmp / "data" / "root_cause_evidence.json").is_file()
    print("OK evidence collection persisted")

    _run_action(registry, "show confidence evolution", Intent.SHOW_CONFIDENCE_EVOLUTION)
    confidence_before = load_confidence()
    assert confidence_before.get("series")
    print("OK confidence evolution recorded")

    _run_action(registry, "show contradictory evidence", Intent.SHOW_CONTRADICTORY_EVIDENCE)
    _run_action(registry, "suggest experiments", Intent.SUGGEST_EXPERIMENTS)
    _run_action(registry, "show root cause graph", Intent.SHOW_ROOT_CAUSE_GRAPH)
    assert (tmp / "data" / "investigation_graph.json").is_file()
    print("OK investigation graph persisted")

    root_before = load_root_causes()
    confidence_series_before = dict(load_confidence().get("series") or {})

    import assistant.root_cause_engine as rce
    import assistant.confidence_tracking as ct

    rce._load = rce._load
    reloaded_root = load_root_causes()
    reloaded_conf = load_confidence()
    assert reloaded_root.get("candidates"), "root causes lost after reload"
    assert reloaded_conf.get("series"), "confidence history lost after reload"
    if confidence_series_before:
        rid = next(iter(confidence_series_before))
        assert rid in (reloaded_conf.get("series") or {}), "confidence series missing after reload"
    print("OK persistence survives restart")

    print("SMOKE PASS phase55")


if __name__ == "__main__":
    main()
