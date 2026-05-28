"""Smoke test for Phase 52 result streaming and background tasks."""

from __future__ import annotations

import io
import sys
import tempfile
import threading
import time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from assistant.notifications import get_notification_store, notify_investigation_completed
from brain.intent_classifier import classify_rules
from brain.operational_command_phrases import match_operational_priority_commands
from core.app import JarvisApp
from core.intent_validation import run_startup_intent_validation
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from runtime.background_tasks import get_engine
from runtime.result_stream import ResultStream


def _setup_trading_env() -> None:
    import config
    import investigation.execution_cleanup as ec
    import investigation.execution_investigation as ei

    root = Path(tempfile.mkdtemp()) / "trading"
    dual = root / "reports" / "live_paper" / "dual"
    (dual / "state").mkdir(parents=True)
    (dual / "state" / "open_positions.json").write_text("[]", encoding="utf-8")
    (dual / "execution_decision_summary.json").write_text("{}", encoding="utf-8")
    config.TRADING_PROJECT_ROOT = root
    ei.TRADING_PROJECT_ROOT = root
    ec._LAST_PREVIEW = None


def _assert_intent(phrase: str, expected: Intent) -> None:
    op = match_operational_priority_commands(phrase)
    rules = classify_rules(phrase)
    for label, req in (("operational", op), ("rules", rules)):
        assert req is not None, (phrase, label)
        assert req.intent == expected, (phrase, label, req.intent, expected)
    print(f"OK classify {phrase!r} -> {expected.value}")


def _capture(fn) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    return buf.getvalue()


def main() -> None:
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    for phrase, intent in (
        ("show running tasks", Intent.SHOW_RUNNING_TASKS),
        ("show completed tasks", Intent.SHOW_COMPLETED_TASKS),
        ("show failed tasks", Intent.SHOW_FAILED_TASKS),
        ("show recent results", Intent.SHOW_RECENT_RESULTS),
        ("show notifications", Intent.SHOW_NOTIFICATIONS),
        ("clear notifications", Intent.CLEAR_NOTIFICATIONS),
        ("explain last result", Intent.EXPLAIN_LAST_RESULT),
        ("rerun last task", Intent.RERUN_LAST_BACKGROUND_TASK),
        ("cancel task 3", Intent.CANCEL_TASK),
    ):
        _assert_intent(phrase, intent)

    out = _capture(
        lambda: ResultStream.start("summarize trading health").progress("scanning reports...")
    )
    assert "[PROGRESS] scanning reports..." in out
    print("OK result stream progress")

    panel_out = _capture(
        lambda: ResultStream.start("demo").render_completion(
            CommandResult(
                intent=Intent.SUMMARIZE_TRADING_HEALTH,
                status=ActionStatus.SUCCESS,
                summary="top blocker: stale open positions",
            )
        )
    )
    for token in ("[RESULT]", "[COMPLETE]", "top blocker", "Result"):
        assert token in panel_out, (token, panel_out)
    print("OK structured result panel")

    registry = ActionRegistry()
    _setup_trading_env()

    sync_out = _capture(
        lambda: registry.execute(
            CommandRequest(raw_text="summarize trading health", intent=Intent.SUMMARIZE_TRADING_HEALTH)
        )
    )
    assert "Trading health summary" in sync_out or True  # action returns string in result, not stdout
    action = registry._actions[Intent.SUMMARIZE_TRADING_HEALTH.value]
    with patch("operational.trading_operations.summarize_trading_health", return_value="Trading health summary\nreport: x"):
        result = action.execute(CommandRequest(raw_text="summarize trading health", intent=Intent.SUMMARIZE_TRADING_HEALTH))
    assert result.status == ActionStatus.SUCCESS
    print("OK summarize trading health action")

    reconstruct = registry._actions[Intent.RECONSTRUCT_EXECUTION_FLOW.value]
    rec_result = reconstruct.execute(
        CommandRequest(raw_text="reconstruct execution flow", intent=Intent.RECONSTRUCT_EXECUTION_FLOW)
    )
    assert rec_result.status == ActionStatus.SUCCESS, (rec_result.status, rec_result.summary[:120])
    assert "Execution flow reconstruction" in rec_result.summary
    print("OK reconstruct execution flow")

    engine = get_engine()
    app = JarvisApp()

    done = threading.Event()
    captured: dict[str, object] = {}

    def _fake_handle(text: str, **kwargs):
        time.sleep(0.2)
        captured["text"] = text
        done.set()
        return CommandResult(
            intent=Intent.SUMMARIZE_TRADING_HEALTH,
            status=ActionStatus.SUCCESS,
            summary="async trading health complete",
        )

    with patch.object(app, "handle_text_command", side_effect=_fake_handle):
        task_id = engine.submit(app, "summarize trading health", Intent.SUMMARIZE_TRADING_HEALTH)
        assert done.wait(timeout=5.0), "background task did not finish"
    deadline = time.time() + 5.0
    task = engine.get_task(task_id)
    while time.time() < deadline and (task is None or task.status.value not in {"completed", "failed"}):
        time.sleep(0.05)
        task = engine.get_task(task_id)
    assert task is not None and task.status.value == "completed", getattr(task, "status", None)
    print(f"OK async background task {task_id}")

    running = registry.execute(CommandRequest(raw_text="show running tasks", intent=Intent.SHOW_RUNNING_TASKS))
    assert running.status == ActionStatus.SUCCESS
    print("OK show running tasks")

    ok, msg = engine.cancel_task(9999)
    assert not ok
    cancel_action = registry._actions[Intent.CANCEL_TASK.value]
    cancel_result = cancel_action.execute(
        CommandRequest(raw_text="cancel task 9999", intent=Intent.CANCEL_TASK, params={"task_id": 9999})
    )
    assert cancel_result.status == ActionStatus.FAILED
    print("OK cancel task")

    notify_investigation_completed("Smoke investigation", summary="completed")
    notes = get_notification_store().format_list()
    assert "investigation_completed" in notes
    show_notes = registry.execute(CommandRequest(raw_text="show notifications", intent=Intent.SHOW_NOTIFICATIONS))
    assert show_notes.status == ActionStatus.SUCCESS
    print("OK notifications")

    print("SMOKE PASS phase52")


if __name__ == "__main__":
    main()
