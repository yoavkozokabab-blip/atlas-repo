"""Direct smoke test for Phase 48.2 patch workflow classifier priority."""

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
from brain.intent_classifier import classify, classify_rules
from brain.patch_command_phrases import match_patch_workflow_commands, validate_patch_workflow_phrase_collisions
from core.intent_validation import validate_patch_workflow_phrase_collisions as startup_patch_validation
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


def test_classifier_priority() -> None:
    cases = {
        "show patch workflow status": Intent.SHOW_PATCH_WORKFLOW_STATUS,
        "run patch workflow confirm": Intent.RUN_PATCH_WORKFLOW,
        "run patch workflow": Intent.RUN_PATCH_WORKFLOW,
        "replay after patch": Intent.REPLAY_AFTER_PATCH,
        "replay validation": Intent.REPLAY_AFTER_PATCH,
        "replay patch validation": Intent.REPLAY_AFTER_PATCH,
        "validate patch safety": Intent.VALIDATE_PATCH_SAFETY,
        "validate patch safe": Intent.VALIDATE_PATCH_SAFETY,
        "apply approved patch confirm": Intent.APPLY_APPROVED_PATCH,
        "rollback last patch confirm": Intent.ROLLBACK_LAST_PATCH,
    }
    for phrase, expected in cases.items():
        matched = match_patch_workflow_commands(phrase)
        assert matched is not None, phrase
        assert matched.intent == expected, (phrase, matched.intent)
        assert matched.intent != Intent.RUN_WORKFLOW, phrase

        rules = classify_rules(phrase)
        assert rules.intent == expected, (phrase, rules.intent)
        assert rules.intent != Intent.RUN_WORKFLOW, phrase

        hybrid = classify(phrase)
        assert hybrid.intent == expected, (phrase, hybrid.intent)
        assert hybrid.intent != Intent.RUN_WORKFLOW, phrase
        print(f"OK classify priority {phrase!r} -> {expected.value}")


def test_startup_patch_collision_validation() -> None:
    assert validate_patch_workflow_phrase_collisions() == []
    assert startup_patch_validation() == []
    print("OK startup patch workflow collision validation")


def test_console_queue_seven_commands() -> None:
    from ui.operator_console import OperatorConsole

    class FakeRuntime:
        running = True

    class FakeApp:
        _running = True
        runtime = FakeRuntime()

    console = OperatorConsole(FakeApp())
    handled: list[str] = []
    lock = threading.Lock()

    def capture(raw: str, *, done_event: threading.Event | None = None) -> None:
        with lock:
            handled.append(raw)
        time.sleep(0.03)
        if done_event is not None:
            done_event.set()

    console._handle_line = capture  # type: ignore[method-assign]

    burst = [
        "validate patch safety",
        "show approved patch",
        "apply approved patch confirm",
        "validate applied patch",
        "compare pre post patch",
        "replay after patch",
        "show patch workflow status",
    ]
    for cmd in burst:
        console._enqueue_command(cmd)

    deadline = time.time() + 8.0
    while time.time() < deadline:
        with lock:
            if handled == burst and console.queue_length() == 0:
                break
        time.sleep(0.05)

    assert handled == burst, (handled, burst)
    assert console.queue_length() == 0
    print("OK console FIFO queue 7 commands sequential")


def test_workflow_commands() -> None:
    _setup_patch_env()
    registry = ActionRegistry()

    workflow = registry._actions[Intent.RUN_PATCH_WORKFLOW.value]
    confirmed = workflow.execute(
        CommandRequest(
            raw_text="run patch workflow confirm",
            intent=Intent.RUN_PATCH_WORKFLOW,
            confirmed=True,
        )
    )
    assert confirmed.status == ActionStatus.SUCCESS, (confirmed.status, confirmed.summary)
    assert confirmed.intent == Intent.RUN_PATCH_WORKFLOW
    assert "Workflow complete" in confirmed.summary
    print("OK run patch workflow confirm uses patch workflow engine")

    status = registry._actions[Intent.SHOW_PATCH_WORKFLOW_STATUS.value].execute(
        CommandRequest(raw_text="show patch workflow status", intent=Intent.SHOW_PATCH_WORKFLOW_STATUS)
    )
    assert status.status == ActionStatus.SUCCESS
    assert "safety validated" in status.summary.lower()
    assert "backup id" in status.summary.lower()
    assert "latest audit report" in status.summary.lower()
    print("OK show patch workflow status output")

    replay = registry._actions[Intent.REPLAY_AFTER_PATCH.value].execute(
        CommandRequest(raw_text="replay after patch", intent=Intent.REPLAY_AFTER_PATCH)
    )
    assert replay.status == ActionStatus.SUCCESS
    print("OK replay after patch")


def main() -> None:
    test_classifier_priority()
    test_startup_patch_collision_validation()
    test_console_queue_seven_commands()
    test_workflow_commands()
    print("SMOKE PASS phase48.2")


if __name__ == "__main__":
    main()
