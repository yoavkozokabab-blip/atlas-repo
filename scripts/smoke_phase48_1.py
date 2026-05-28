"""Direct smoke test for Phase 48.1 console queue + patch command fixes."""

from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from brain.patch_command_phrases import match_patch_command, normalize_patch_command
from core.types import ActionStatus, CommandRequest, Intent
import investigation.execution_cleanup as ec
import investigation.execution_investigation as ei
import investigation.patch_apply as pa


def _fixture(root: Path) -> None:
    state = root / "reports" / "live_paper" / "dual" / "state"
    dual = state.parent
    state.mkdir(parents=True)
    (state / "open_positions.json").write_text(
        '[{"symbol":"AAPL","stop_loss_hit":true},{"symbol":"MSFT","stop_loss_hit":true}]',
        encoding="utf-8",
    )
    (dual / "execution_decision_summary.json").write_text(
        '{"execution_mode":"paper","open_risk_fraction_daily":0.1125,"reason_if_no_attempt":"not_relevant_to_last_bar"}',
        encoding="utf-8",
    )
    (dual / "live_summary_latest.json").write_text(
        '{"execution_adapter":"ExecutionDisabledAdapter","execution_mode":"paper","dry_run":true}',
        encoding="utf-8",
    )
    services = root / "services"
    services.mkdir(parents=True)
    (services / "live_paper_engine.py").write_text("# paper engine\n", encoding="utf-8")
    (services / "live_dual_paper_cycle.py").write_text("# dual cycle\n", encoding="utf-8")


def _setup_patch_env() -> None:
    import config

    root = Path(tempfile.mkdtemp()) / "trading"
    _fixture(root)
    backup_root = Path(tempfile.mkdtemp()) / "backups"
    report_dir = Path(tempfile.mkdtemp()) / "patch_apply"
    config.TRADING_PROJECT_ROOT = root
    ei.TRADING_PROJECT_ROOT = root
    pa.BACKUP_ROOT = backup_root
    pa.APPLY_REPORT_DIR = report_dir
    pa.STATE_PATH = Path(tempfile.mkdtemp()) / "patch_apply_state.json"
    pa.HISTORY_PATH = report_dir / "history.jsonl"
    ec._LAST_PREVIEW = None


def test_classifier_aliases() -> None:
    cases = {
        "validate patch safe": Intent.VALIDATE_PATCH_SAFETY,
        "validate patch safety": Intent.VALIDATE_PATCH_SAFETY,
        "replay after patch": Intent.REPLAY_AFTER_PATCH,
        "replay validation": Intent.REPLAY_AFTER_PATCH,
        "compare pre post patch": Intent.COMPARE_PRE_POST_PATCH,
        "show approved patch": Intent.SHOW_APPROVED_PATCH,
        "apply approved patch confirm": Intent.APPLY_APPROVED_PATCH,
        "rollback last patch confirm": Intent.ROLLBACK_LAST_PATCH,
        "run patch workflow": Intent.RUN_PATCH_WORKFLOW,
        "show patch workflow status": Intent.SHOW_PATCH_WORKFLOW_STATUS,
    }
    for phrase, expected in cases.items():
        matched = match_patch_command(phrase)
        assert matched is not None, phrase
        assert matched.intent == expected, (phrase, matched.intent)
        rules = classify_rules(phrase)
        assert rules.intent == expected, (phrase, rules.intent, rules.confidence)
        print(f"OK classify {phrase!r} -> {expected.value}")


def test_console_queue_fifo() -> None:
    from ui.operator_console import OperatorConsole

    class FakeRuntime:
        running = True

    class FakeApp:
        _running = True
        runtime = FakeRuntime()

    console = OperatorConsole(FakeApp())
    handled: list[str] = []
    lock = threading.Lock()

    def capture(raw: str) -> None:
        with lock:
            handled.append(raw)
        time.sleep(0.05)

    console._handle_line = capture  # type: ignore[method-assign]

    burst = [
        "validate patch safety",
        "show approved patch",
        "apply approved patch confirm",
    ]
    for cmd in burst:
        console._enqueue_command(cmd)

    deadline = time.time() + 5.0
    while time.time() < deadline:
        with lock:
            if handled == burst and console.queue_length() == 0:
                break
        time.sleep(0.05)

    assert handled == burst, (handled, burst)
    assert console.queue_length() == 0
    print("OK console FIFO queue sequential execution")


def test_patch_workflow_and_rollback() -> None:
    _setup_patch_env()
    registry = ActionRegistry()

    workflow_action = registry._actions[Intent.RUN_PATCH_WORKFLOW.value]
    unconfirmed = workflow_action.execute(
        CommandRequest(raw_text="run patch workflow", intent=Intent.RUN_PATCH_WORKFLOW)
    )
    assert unconfirmed.status == ActionStatus.CONFIRMATION_REQUIRED, unconfirmed.status
    assert "confirmation required" in unconfirmed.summary.lower() or "Apply NOT executed" in unconfirmed.summary
    print("OK run patch workflow stops before apply without confirm")

    confirmed = workflow_action.execute(
        CommandRequest(
            raw_text="run patch workflow confirm",
            intent=Intent.RUN_PATCH_WORKFLOW,
            confirmed=True,
        )
    )
    assert confirmed.status == ActionStatus.SUCCESS, (confirmed.status, confirmed.summary)
    assert "Workflow complete" in confirmed.summary
    print("OK run patch workflow confirm completes")

    status_action = registry._actions[Intent.SHOW_PATCH_WORKFLOW_STATUS.value]
    status = status_action.execute(CommandRequest(raw_text="", intent=Intent.SHOW_PATCH_WORKFLOW_STATUS))
    assert status.status == ActionStatus.SUCCESS
    assert "safety validation" in status.summary.lower()
    assert "rollback available" in status.summary.lower()
    print("OK show patch workflow status")

    replay_action = registry._actions[Intent.REPLAY_AFTER_PATCH.value]
    replay = replay_action.execute(CommandRequest(raw_text="replay after patch", intent=Intent.REPLAY_AFTER_PATCH))
    assert replay.status == ActionStatus.SUCCESS
    assert "replay after patch" in replay.summary.lower()
    print("OK replay after patch")

    rollback_action = registry._actions[Intent.ROLLBACK_LAST_PATCH.value]
    rollback = rollback_action.execute(
        CommandRequest(
            raw_text="rollback last patch confirm",
            intent=Intent.ROLLBACK_LAST_PATCH,
            confirmed=True,
        )
    )
    assert rollback.status == ActionStatus.SUCCESS, (rollback.status, rollback.summary)
    print("OK rollback last patch confirm")


def main() -> None:
    test_classifier_aliases()
    test_console_queue_fifo()
    test_patch_workflow_and_rollback()
    print("SMOKE PASS phase48.1")


if __name__ == "__main__":
    main()
