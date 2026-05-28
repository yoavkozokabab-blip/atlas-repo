"""Smoke test for Phase 54 autonomous investigation loops."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from assistant.investigation_scheduler import (
    _load as load_scheduler,
    reset_scheduler_for_tests,
    scheduler_tick,
    start_investigation_scheduler,
)
from brain.intent_classifier import classify_rules
from brain.operational_command_phrases import match_operational_priority_commands
from core.intent_validation import run_startup_intent_validation
from core.types import ActionStatus, CommandRequest, Intent
from runtime.background_tasks import reset_background_engine_for_tests


def _setup_isolated_data(tmp: Path) -> None:
    import config

    config.DATA_DIR = tmp / "data"
    config.SESSION_STATE_PATH = config.DATA_DIR / "session_state.json"
    import assistant.investigation_scheduler as sched

    sched.SCHEDULER_PATH = config.DATA_DIR / "investigation_scheduler.json"
    import assistant.hypothesis_engine as he

    he.HYPOTHESES_PATH = config.DATA_DIR / "hypotheses.json"
    import investigation.blocker_trends as bt

    bt.TRENDS_PATH = config.DATA_DIR / "blocker_trends.json"
    import assistant.intelligence_timeline as tl

    tl.TIMELINE_PATH = config.DATA_DIR / "intelligence_timeline.json"
    import investigation.divergence_clustering as dc

    dc.CLUSTERS_PATH = config.DATA_DIR / "divergence_clusters.json"
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
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    for phrase, intent in (
        ("run investigation cycle", Intent.RUN_INVESTIGATION_CYCLE),
        ("show blocker trends", Intent.SHOW_BLOCKER_TRENDS),
        ("show active hypotheses", Intent.SHOW_ACTIVE_HYPOTHESES),
        ("explain top hypothesis", Intent.EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS),
        ("show intelligence timeline", Intent.SHOW_INTELLIGENCE_TIMELINE),
        ("summarize autonomous findings", Intent.SUMMARIZE_AUTONOMOUS_FINDINGS),
        ("show investigation schedule", Intent.SHOW_INVESTIGATION_SCHEDULE),
        ("pause investigation loop", Intent.PAUSE_INVESTIGATION_LOOP),
        ("resume investigation loop", Intent.RESUME_INVESTIGATION_LOOP),
    ):
        _assert_intent(phrase, intent)

    tmp = Path(tempfile.mkdtemp()) / "phase54"
    _setup_isolated_data(tmp)
    reset_scheduler_for_tests()
    reset_background_engine_for_tests()

    registry = ActionRegistry()

    cycle_summary = _run_action(registry, "run investigation cycle", Intent.RUN_INVESTIGATION_CYCLE)
    assert "Investigation cycle complete" in cycle_summary
    ic_reports = list((tmp / "reports" / "autonomous_investigations").glob("*_cycle.json"))
    assert ic_reports, "cycle report not written"
    print(f"OK cycle report ({ic_reports[0].name})")

    _run_action(registry, "show blocker trends", Intent.SHOW_BLOCKER_TRENDS)
    assert (tmp / "data" / "blocker_trends.json").is_file()
    print("OK blocker trends persisted")

    _run_action(registry, "show active hypotheses", Intent.SHOW_ACTIVE_HYPOTHESES)
    assert (tmp / "data" / "hypotheses.json").is_file()
    print("OK hypotheses persisted")

    _run_action(registry, "explain top hypothesis", Intent.EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS)
    _run_action(registry, "show intelligence timeline", Intent.SHOW_INTELLIGENCE_TIMELINE)
    assert (tmp / "data" / "intelligence_timeline.json").is_file()
    print("OK intelligence timeline persisted")

    findings = _run_action(registry, "summarize autonomous findings", Intent.SUMMARIZE_AUTONOMOUS_FINDINGS)
    assert "Autonomous findings" in findings or "No autonomous" in findings
    print("OK summarize autonomous findings")

    schedule_before = load_scheduler()
    start_investigation_scheduler()
    scheduler_tick()
    schedule_after = load_scheduler()
    assert schedule_after.get("last_runs") or schedule_before.get("last_runs") is not None
    print("OK scheduler startup tick")

    _run_action(registry, "pause investigation loop", Intent.PAUSE_INVESTIGATION_LOOP)
    assert load_scheduler().get("paused") is True
    _run_action(registry, "resume investigation loop", Intent.RESUME_INVESTIGATION_LOOP)
    assert load_scheduler().get("paused") is False
    print("OK scheduler pause/resume persistence")

    reset_scheduler_for_tests()
    reloaded = load_scheduler()
    assert reloaded.get("paused") is False
    assert reloaded.get("last_runs")
    print("OK scheduler persistence survives reload")

    from assistant.notifications import get_notification_store

    notes = get_notification_store().list_notifications(limit=5)
    print(f"OK notifications available ({len(notes)})")

    print("SMOKE PASS phase54")


if __name__ == "__main__":
    main()
