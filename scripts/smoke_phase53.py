"""Smoke test for Phase 53 persistent assistant state."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from assistant.notifications import get_notification_store, reset_notification_store_for_tests
from brain.intent_classifier import classify_rules
from brain.operational_command_phrases import match_operational_priority_commands
from core.app import JarvisApp
from core.intent_validation import run_startup_intent_validation
from core.persistent_json import atomic_write_json
from core.session import SessionState
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from runtime.background_tasks import get_engine, reset_background_engine_for_tests
from runtime.task_lifecycle import get_task_lifecycle, reset_task_lifecycle_for_tests


def _setup_isolated_data(tmp: Path) -> None:
    import config

    config.DATA_DIR = tmp / "data"
    config.SESSION_STATE_PATH = config.DATA_DIR / "session_state.json"
    import runtime.task_lifecycle as tl

    tl.TASK_RESULTS_DIR = config.DATA_DIR / "task_results"
    tl.TASK_LIFECYCLE_DIR = config.DATA_DIR / "task_lifecycle"
    tl.TASK_STATE_PATH = tl.TASK_LIFECYCLE_DIR / "state.json"
    import assistant.notifications as nt

    nt.NOTIFICATIONS_PATH = config.DATA_DIR / "notifications.json"
    import assistant.continuity_engine as ce

    ce.CONTINUITY_PATH = config.DATA_DIR / "assistant_continuity.json"
    import memory.task_memory as tm

    tm.TASK_MEMORY_PATH = config.DATA_DIR / "task_memory.json"
    tm.DATA_DIR = config.DATA_DIR


def _assert_intent(phrase: str, expected: Intent) -> None:
    op = match_operational_priority_commands(phrase)
    rules = classify_rules(phrase)
    for label, req in (("operational", op), ("rules", rules)):
        assert req is not None, (phrase, label)
        assert req.intent == expected, (phrase, label, req.intent, expected)
    print(f"OK classify {phrase!r} -> {expected.value}")


def _wait_task(task_id: int, *, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    lifecycle = get_task_lifecycle()
    while time.time() < deadline:
        task = lifecycle.get(task_id)
        if task and task.phase.is_terminal:
            return
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not finish")


def main() -> None:
    os.environ["JARVIS_SKIP_INVESTIGATION_SCHEDULER"] = "1"
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    for phrase, intent in (
        ("show completed tasks", Intent.SHOW_COMPLETED_TASKS),
        ("explain last result", Intent.EXPLAIN_LAST_RESULT),
        ("continue previous session", Intent.CONTINUE_PREVIOUS_SESSION),
        ("summarize unresolved issues", Intent.SUMMARIZE_UNRESOLVED_ISSUES),
        ("recommend next action", Intent.RECOMMEND_NEXT_ACTION),
        ("reopen task result 7", Intent.REOPEN_TASK_RESULT),
        ("archive notification 4", Intent.ARCHIVE_NOTIFICATION),
    ):
        _assert_intent(phrase, intent)

    tmp = Path(tempfile.mkdtemp()) / "phase53"
    _setup_isolated_data(tmp)
    reset_task_lifecycle_for_tests()
    reset_background_engine_for_tests()
    reset_notification_store_for_tests()

    app = JarvisApp()
    engine = get_engine()
    lifecycle = get_task_lifecycle()
    registry = ActionRegistry()

    elapsed_seen = {"ok": False}

    def _slow_handle(text: str, **kwargs):
        time.sleep(0.35)
        return CommandResult(
            intent=Intent.SUMMARIZE_TRADING_HEALTH,
            status=ActionStatus.SUCCESS,
            summary="trading health async complete — top blocker: stale open positions",
        )

    with patch.object(app, "handle_text_command", side_effect=_slow_handle):
        task_id = engine.submit(app, "summarize trading health", Intent.SUMMARIZE_TRADING_HEALTH)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            running = engine.list_running()
            if running and running[0].duration_seconds >= 0.1:
                elapsed_seen["ok"] = True
                break
            time.sleep(0.05)
        _wait_task(task_id)

    assert elapsed_seen["ok"], "running task elapsed stayed at 0.0s"
    print("OK live elapsed tracking")

    completed = engine.list_completed()
    assert completed, "completed tasks empty after finish"
    print(f"OK completed tasks ({len(completed)})")

    explain = registry._actions[Intent.EXPLAIN_LAST_RESULT.value].execute(
        CommandRequest(raw_text="explain last result", intent=Intent.EXPLAIN_LAST_RESULT)
    )
    assert explain.status == ActionStatus.SUCCESS
    assert "trading health" in explain.summary.lower()
    print("OK explain last result")

    cont = registry._actions[Intent.CONTINUE_PREVIOUS_SESSION.value].execute(
        CommandRequest(raw_text="continue previous session", intent=Intent.CONTINUE_PREVIOUS_SESSION)
    )
    assert cont.status == ActionStatus.SUCCESS
    print("OK continue previous session")

    rec = registry._actions[Intent.RECOMMEND_NEXT_ACTION.value].execute(
        CommandRequest(raw_text="recommend next action", intent=Intent.RECOMMEND_NEXT_ACTION)
    )
    assert rec.status == ActionStatus.SUCCESS
    print("OK recommend next action")

    result_path = lifecycle._result_index.get(task_id)
    assert result_path and result_path.is_file(), "task result not persisted"
    print("OK task result file persisted")

    # Simulate restart — reload managers from disk
    reset_task_lifecycle_for_tests()
    reset_background_engine_for_tests()
    reset_notification_store_for_tests()
    engine2 = get_engine()
    completed2 = engine2.list_completed()
    assert completed2, "completed tasks lost after restart"
    explain2 = engine2.explain_last_result()
    assert "trading health" in explain2.lower()
    print("OK persistence survives restart")

    # Session corruption recovery
    corrupt_path = tmp / "data" / "session_state.json"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("", encoding="utf-8")
    backup_dir = corrupt_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        backup_dir / "session_state_recovery.json",
        {
            "last_intent": "test",
            "current_project_root": str(tmp),
            "created_at": "2020-01-01T00:00:00+00:00",
            "updated_at": "2020-01-01T00:00:00+00:00",
        },
    )
    # load_json recovery looks for session_state_*.json backups
    atomic_write_json(
        backup_dir / "session_state_20200101.json",
        {
            "last_intent": "test",
            "current_project_root": str(tmp),
            "created_at": "2020-01-01T00:00:00+00:00",
            "updated_at": "2020-01-01T00:00:00+00:00",
        },
    )
    state = SessionState.load()
    assert state.last_intent == "test"
    print("OK session corruption recovery")

    notes = get_notification_store().list_notifications(limit=5)
    assert notes, "notifications not persisted"
    print(f"OK notifications persisted ({len(notes)})")

    print("SMOKE PASS phase53")


if __name__ == "__main__":
    main()
