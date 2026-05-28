"""Tests for command router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from brain.router import CommandRouter
from core.session import SessionState
from core.types import ActionStatus, Intent


def test_route_open_cursor():
    router = CommandRouter()
    with patch("actions.apps.subprocess.Popen") as popen:
        popen.return_value = MagicMock()
        result = router.route("open cursor")
    assert result.intent == Intent.OPEN_CURSOR
    assert result.status in (ActionStatus.SUCCESS, ActionStatus.FAILED)


def test_unknown_command_blocked():
    router = CommandRouter()
    result = router.route("fly me to the moon xyz")
    assert result.status in (
        ActionStatus.BLOCKED,
        ActionStatus.CLARIFICATION_NEEDED,
    )


def test_low_confidence_clarifies():
    router = CommandRouter()
    result = router.route("maybe dashboard something vague")
    assert result.status in (
        ActionStatus.CLARIFICATION_NEEDED,
        ActionStatus.SUCCESS,
        ActionStatus.FAILED,
    )


def test_hebrew_last_errors_intent():
    router = CommandRouter()
    with patch.object(router.registry, "execute") as execute:
        execute.return_value = MagicMock(
            intent=Intent.SHOW_LAST_ERRORS,
            status=ActionStatus.SUCCESS,
            summary="ok",
            data={},
            error=None,
            requires_confirmation=False,
            confirmation_id=None,
            next_suggestions=[],
        )
        router.route("תראה שגיאות אחרונות")
    call_args = execute.call_args[0][0]
    assert call_args.intent == Intent.SHOW_LAST_ERRORS


def test_follow_up_uses_session(tmp_path: Path, monkeypatch):
    session_path = tmp_path / "session_state.json"
    monkeypatch.setattr("config.SESSION_STATE_PATH", session_path)

    log = tmp_path / "project" / "reports" / "a.log"
    log.parent.mkdir(parents=True)
    log.write_text("ERROR test failure\n", encoding="utf-8")

    session = SessionState.load()
    session.current_project_root = str(tmp_path / "project")
    session.last_opened_log = str(log)
    session.save()

    router = CommandRouter(session=SessionState.load())
    result = router.route("תסכם את זה")
    assert result.intent == Intent.SUMMARIZE_LATEST_LOG
    assert result.status == ActionStatus.SUCCESS


def test_remember_fact_structured_result(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("brain.memory.MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr("brain.memory.BACKUPS_DIR", tmp_path / "backups")
    from brain.memory import reset_memory_store

    reset_memory_store()
    router = CommandRouter()
    result = router.route("זכור שהפרויקט הראשי הוא C:\\FINAL_ALGO_TRADER")
    assert result.intent in (Intent.REMEMBER_FACT, Intent.REMEMBER_PREFERENCE)
    assert result.status == ActionStatus.SUCCESS
    assert result.summary
    assert hasattr(result, "data")
