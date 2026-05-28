"""Smoke test for Phase 51 desktop awareness and classifier fixes."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from brain.intent_classifier import classify, classify_rules
from brain.operational_command_phrases import match_operational_priority_commands
from core.intent_validation import run_startup_intent_validation
from core.types import ActionStatus, CommandRequest, Intent
from runtime.dashboard_health import mark_dashboard_open_requested, probe_dashboard_health
import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei


def _setup_trading_env() -> None:
    import config

    root = Path(tempfile.mkdtemp()) / "trading"
    dual = root / "reports" / "live_paper" / "dual"
    (dual / "state").mkdir(parents=True)
    (dual / "state" / "open_positions.json").write_text("[]", encoding="utf-8")
    (dual / "execution_decision_summary.json").write_text("{}", encoding="utf-8")
    config.TRADING_PROJECT_ROOT = root
    ei.TRADING_PROJECT_ROOT = root
    ec._LAST_PREVIEW = None


def _assert_intent(phrase: str, expected: Intent, *, forbid_phase45: bool = False) -> None:
    op = match_operational_priority_commands(phrase)
    rules = classify_rules(phrase)
    hybrid = classify(phrase)
    for label, req in (("operational", op), ("rules", rules), ("classify", hybrid)):
        assert req is not None, (phrase, label)
        assert req.intent == expected, (phrase, label, req.intent, expected)
        if forbid_phase45:
            assert req.intent != Intent.PHASE45_STATUS, phrase
    print(f"OK classify {phrase!r} -> {expected.value}")


def _run(registry: ActionRegistry, phrase: str) -> None:
    req = classify_rules(phrase)
    action = registry._actions[req.intent.value]
    result = action.execute(CommandRequest(raw_text=phrase, intent=req.intent))
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary[:120])
    print(f"OK execute {phrase!r} -> {req.intent.value}")


def main() -> None:
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    for phrase, intent in (
        ("phase 49 status", Intent.PHASE49_STATUS),
        ("phase 50 status", Intent.PHASE50_STATUS),
        ("phase 45 status", Intent.PHASE45_STATUS),
        ("what windows are open", Intent.SHOW_OPEN_WINDOWS),
        ("list windows", Intent.SHOW_OPEN_WINDOWS),
    ):
        _assert_intent(
            phrase,
            intent,
            forbid_phase45=phrase in {"phase 49 status", "phase 50 status"},
        )

    registry = ActionRegistry()
    _setup_trading_env()

    for phrase in (
        "show screen system status",
        "show trading operations dashboard",
        "summarize my screen",
        "show memory state",
    ):
        _run(registry, phrase)

    mark_dashboard_open_requested()
    probe = probe_dashboard_health()
    assert probe.get("status") in {"starting", "degraded", "failed", "healthy"}, probe
    print(f"OK dashboard probe status={probe.get('status')}")

    print("SMOKE PASS phase51")


if __name__ == "__main__":
    main()
