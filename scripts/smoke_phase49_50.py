"""Smoke test for Phase 49/50 operational layer."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.intent_validation import run_startup_intent_validation
from core.types import ActionStatus, CommandRequest, Intent
import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei
import investigation.patch_apply as pa


def _fixture(root: Path) -> None:
    state = root / "reports" / "live_paper" / "dual" / "state"
    dual = state.parent
    state.mkdir(parents=True)
    (state / "open_positions.json").write_text("[]", encoding="utf-8")
    (dual / "execution_decision_summary.json").write_text(
        '{"execution_mode":"paper","open_risk_fraction_daily":0.05,"reason_if_no_attempt":"adapter_disabled"}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter":"ExecutionDisabledAdapter","execution_mode":"paper","dry_run":true}',
        encoding="utf-8",
    )
    services = root / "services"
    services.mkdir(parents=True)
    (services / "live_paper_engine.py").write_text("# engine\n", encoding="utf-8")
    (services / "live_dual_paper_cycle.py").write_text("# cycle\n", encoding="utf-8")


def _setup_trading_env() -> None:
    import config

    root = Path(tempfile.mkdtemp()) / "trading"
    _fixture(root)
    config.TRADING_PROJECT_ROOT = root
    ei.TRADING_PROJECT_ROOT = root
    pa.STATE_PATH = Path(tempfile.mkdtemp()) / "patch_state.json"
    ec._LAST_PREVIEW = None


def _run(registry: ActionRegistry, phrase: str, *, confirmed: bool = False) -> None:
    req = classify_rules(phrase)
    assert req.intent != Intent.UNKNOWN, (phrase, req.intent)
    assert req.intent != Intent.RUN_WORKFLOW, (phrase, req.intent)
    action = registry._actions[req.intent.value]
    result = action.execute(
        CommandRequest(raw_text=phrase, intent=req.intent, confirmed=confirmed)
    )
    if result.status == ActionStatus.CONFIRMATION_REQUIRED and confirmed:
        result = action.execute(
            CommandRequest(raw_text=phrase, intent=req.intent, confirmed=True)
        )
    assert result.status in {ActionStatus.SUCCESS, ActionStatus.CONFIRMATION_REQUIRED}, (
        phrase,
        result.status,
        result.summary[:120],
    )
    print(f"OK {phrase} -> {req.intent.value} status={result.status.value}")


def main() -> None:
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup intent validation")

    registry = ActionRegistry()
    _setup_trading_env()

    read_only = [
        "show runtime health",
        "show healing actions",
        "show stuck workers",
        "validate runtime integrity",
        "summarize trading health",
        "what was i doing",
        "resume last task",
        "show operational suggestions",
        "show current state",
        "show runtime summary",
    ]
    for phrase in read_only:
        _run(registry, phrase)

    confirm = [
        ("recover overlay confirm", True),
        ("restart dashboard confirm", True),
    ]
    for phrase, confirmed in confirm:
        _run(registry, phrase, confirmed=confirmed)

    print("SMOKE PASS phase49_50")


if __name__ == "__main__":
    main()
