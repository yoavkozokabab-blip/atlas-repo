"""Phase 43 — foundation hardening tests."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from brain.command_grammar import score_command_grammar
from brain.intent_classifier import classify_rules
from brain.voice_grammar import match_voice_grammar
from core.types import Intent


@pytest.mark.parametrize(
    "phrase,intent",
    [
        ("open the dashboard", Intent.OPEN_TRADING_DASHBOARD),
        ("bring up the dashboard", Intent.OPEN_TRADING_DASHBOARD),
        ("show me the dashboard", Intent.OPEN_TRADING_DASHBOARD),
        ("open discord", Intent.OPEN_APP),
        ("open chrome", Intent.OPEN_CHROME),
        ("what am i doing", Intent.WHAT_AM_I_DOING),
        ("describe the screen", Intent.DESCRIBE_SCREEN),
        ("what is on my screen", Intent.DESCRIBE_SCREEN),
        ("analyze this window", Intent.ANALYZE_ACTIVE_WINDOW),
        ("foundation health check", Intent.FOUNDATION_HEALTH_CHECK),
        ("show launcher status", Intent.SHOW_LAUNCHER_STATUS),
    ],
)
def test_natural_phrases_classify(phrase, intent):
    req = classify_rules(phrase)
    assert req.intent == intent
    assert req.confidence >= 0.85


@pytest.mark.parametrize(
    "phrase,intent,website",
    [
        ("open youtube", Intent.OPEN_WEBSITE, "youtube"),
        ("open chatgpt", Intent.OPEN_WEBSITE, "chatgpt"),
        ("show runtime status", Intent.SHOW_RUNTIME_STATUS, None),
        ("what can you do", Intent.SHOW_CAPABILITIES, None),
        ("list workflows", Intent.LIST_WORKFLOWS, None),
        ("check trading", Intent.RUN_WORKFLOW, None),
        ("show last errors", Intent.SHOW_LAST_ERRORS, None),
    ],
)
def test_legacy_fuzzy_phrases_still_match(phrase, intent, website):
    req = match_voice_grammar(phrase)
    assert req is not None
    assert req.intent == intent
    if website:
        assert req.params.get("website") == website


def test_trailing_period_stripped_before_classify():
    req = classify_rules("test direct speech.")
    assert req.intent == Intent.TEST_DIRECT_SPEECH


def test_grammar_does_not_execute():
    with patch("actions.registry.ActionRegistry.execute") as execute:
        match_voice_grammar("open dashboard")
    execute.assert_not_called()


def test_ambiguous_low_confidence_clarifies():
    req = classify_rules("maybe do something with charts")
    assert req.intent in (Intent.UNKNOWN, Intent.CLARIFY)


def test_foundation_health_action():
    from actions.foundation_actions import FoundationHealthCheckAction
    from core.types import CommandRequest

    result = FoundationHealthCheckAction().execute(
        CommandRequest(
            raw_text="foundation health check",
            intent=Intent.FOUNDATION_HEALTH_CHECK,
            confidence=1.0,
        )
    )
    assert "Foundation health" in result.summary


def test_show_launcher_status_reports_paths():
    from actions.foundation_actions import ShowLauncherStatusAction
    from core.types import CommandRequest

    result = ShowLauncherStatusAction().execute(
        CommandRequest(
            raw_text="show launcher status",
            intent=Intent.SHOW_LAUNCHER_STATUS,
            confidence=1.0,
        )
    )
    assert "chrome:" in result.summary.lower() or "Chrome" in result.summary


def test_longest_grammar_match_wins():
    a = score_command_grammar("show dashboard health")
    assert a is not None
    assert a.intent == Intent.SHOW_DASHBOARD_HEALTH


def test_router_registry_unchanged():
    from actions.registry import ActionRegistry
    from brain.router import CommandRouter

    reg = ActionRegistry()
    router = CommandRouter(registry=reg)
    assert router.registry is reg


def test_show_runtime_threads_classify():
    req = classify_rules("show runtime threads")
    assert req.intent == Intent.SHOW_RUNTIME_THREADS


def test_operator_console_thread_starts(monkeypatch, capsys):
    from ui.operator_console import OperatorConsole

    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True

    console = OperatorConsole(app)
    monkeypatch.setattr("ui.operator_console.should_start_operator_console", lambda **_: True)
    monkeypatch.setattr("ui.operator_console.OperatorConsole._read_loop", lambda self: None)
    assert console.start() is True
    assert console._thread is not None
    assert console._started is True
    out = capsys.readouterr().out
    assert "[INFO] Interactive console enabled. Type commands and press Enter." in out


def test_operator_console_unavailable_warns(monkeypatch, capsys):
    from ui.operator_console import OperatorConsole

    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True

    console = OperatorConsole(app)
    monkeypatch.setattr("ui.operator_console.should_start_operator_console", lambda **_: False)
    assert console.start() is False
    out = capsys.readouterr().out
    assert "Interactive console unavailable in background/tray mode." in out


def test_console_command_helper_routes_via_app_handler():
    from core.runtime_state import RuntimeState
    from core.types import ActionStatus, CommandResult, Intent
    from voice.voice_loop import process_console_command

    app = MagicMock()
    app._running = True
    app.runtime = RuntimeState()
    app.runtime.running = True
    app.handle_text_command.return_value = CommandResult(
        intent=Intent.OPEN_TRADING_DASHBOARD,
        status=ActionStatus.SUCCESS,
        summary="Dashboard opened.",
        requires_confirmation=False,
    )

    result = process_console_command(app, "open dashboard")
    assert result is app.handle_text_command.return_value
    app.handle_text_command.assert_called_once_with(
        "open dashboard",
        input_mode="console",
        transcribed_text="open dashboard",
        print_result=False,
    )


@pytest.mark.parametrize(
    "command",
    [
        "force shell tts test",
        "test normal speech path",
        "show audio status",
        "foundation health check",
        "open dashboard",
    ],
)
def test_operator_console_required_commands_route(monkeypatch, command, capsys):
    from ui.operator_console import OperatorConsole

    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True
    calls: list[str] = []

    def _process(_app, phrase, **kwargs):
        calls.append(phrase)

    monkeypatch.setattr("voice.voice_loop.process_console_command", _process)
    console = OperatorConsole(app)
    console._handle_line(command)
    assert calls == [command]
    out = capsys.readouterr().out
    assert "[CONSOLE] command received" in out


def test_wake_listener_remains_active_with_console(monkeypatch):
    from ui.operator_console import OperatorConsole

    hold = threading.Event()

    def _wake_target() -> None:
        hold.wait(timeout=3.0)

    wake = threading.Thread(target=_wake_target, name="jarvis-wake-test", daemon=True)
    wake.start()
    tray = MagicMock()
    tray._wakeword_detector = MagicMock()
    tray._wakeword_detector._thread = wake

    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True

    console = OperatorConsole(app, tray_app=tray)
    monkeypatch.setattr("ui.operator_console.should_start_operator_console", lambda **_: True)
    monkeypatch.setattr("ui.operator_console.OperatorConsole._read_loop", lambda self: None)
    console.start()
    assert wake.is_alive()
    hold.set()


def test_exit_shuts_down_cleanly():
    from ui.operator_console import OperatorConsole

    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True
    tray = MagicMock()

    console = OperatorConsole(app, tray_app=tray)
    console._handle_line("quit")
    assert app._running is False
    app.runtime.stop.assert_called_once()
    tray.stop.assert_called_once()


def test_modal_yes_completes_verification(monkeypatch):
    from ui.console_modal import reset_modal_for_tests, run_modal_yes_no_prompt, submit_modal_line

    reset_modal_for_tests()
    monkeypatch.setattr("ui.console_modal._operator_console_stdin_shared", lambda: True)

    results: list[bool | None] = []

    def _run() -> None:
        results.append(
            run_modal_yes_no_prompt(
                "Did you hear the shell TTS test? say yes or no",
                timeout_seconds=5.0,
            )
        )

    worker = threading.Thread(target=_run)
    worker.start()
    assert worker.is_alive()
    threading.Event().wait(0.15)
    assert submit_modal_line("yes") is True
    worker.join(timeout=3.0)
    assert results == [True]


def test_operator_console_paused_during_modal(monkeypatch):
    from ui.console_modal import is_modal_active, reset_modal_for_tests, run_modal_yes_no_prompt
    from ui.operator_console import OperatorConsole

    reset_modal_for_tests()
    monkeypatch.setattr("ui.console_modal._operator_console_stdin_shared", lambda: True)
    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True
    console = OperatorConsole(app)

    def _run() -> None:
        run_modal_yes_no_prompt("heard?", timeout_seconds=5.0)

    worker = threading.Thread(target=_run)
    worker.start()
    threading.Event().wait(0.1)
    assert is_modal_active() is True
    with patch("voice.voice_loop.process_console_command") as route:
        console._dispatch_line("open dashboard")
        route.assert_not_called()
    from ui.console_modal import submit_modal_line

    submit_modal_line("no")
    worker.join(timeout=3.0)
    assert is_modal_active() is False


def test_no_busy_warning_during_modal(monkeypatch, capsys):
    from ui.console_modal import reset_modal_for_tests, run_modal_yes_no_prompt, submit_modal_line
    from ui.operator_console import OperatorConsole

    reset_modal_for_tests()
    monkeypatch.setattr("ui.console_modal._operator_console_stdin_shared", lambda: True)
    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True
    console = OperatorConsole(app)
    console._busy = True

    def _run() -> None:
        run_modal_yes_no_prompt("heard?", timeout_seconds=5.0)

    worker = threading.Thread(target=_run)
    worker.start()
    threading.Event().wait(0.1)
    console._dispatch_line("yes")
    submit_modal_line("yes")
    worker.join(timeout=3.0)
    out = capsys.readouterr().out
    assert "busy" not in out.lower()


def test_ask_user_audible_confirmation_via_modal_yes(monkeypatch):
    from voice.audio_verified import ask_user_audible_confirmation
    from ui.console_modal import reset_modal_for_tests, submit_modal_line

    reset_modal_for_tests()
    monkeypatch.setattr("ui.console_modal._operator_console_stdin_shared", lambda: True)

    results: list[bool | None] = []

    def _run() -> None:
        results.append(
            ask_user_audible_confirmation("Did you hear the shell TTS test? say yes or no")
        )

    worker = threading.Thread(target=_run)
    worker.start()
    threading.Event().wait(0.15)
    assert submit_modal_line("yes") is True
    worker.join(timeout=3.0)
    assert results == [True]


def test_verified_backend_saved_after_modal_yes(monkeypatch):
    from actions.voice_audio_actions import ForceShellTtsTestAction
    from core.types import ActionStatus, CommandRequest, Intent
    from voice.audio_status import get_selected_verified_audio_backend, reset_audio_status
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND, SubprocessTtsResult
    from ui.console_modal import reset_modal_for_tests, submit_modal_line

    reset_audio_status()
    reset_modal_for_tests()
    monkeypatch.setattr("ui.console_modal._operator_console_stdin_shared", lambda: True)
    monkeypatch.setattr(
        "voice.tts_subprocess.run_shell_exact_pyttsx3",
        lambda: SubprocessTtsResult(exit_code=0, stdout="", stderr=""),
    )

    results: list = []

    def _run_action() -> None:
        results.append(
            ForceShellTtsTestAction().execute(
                CommandRequest(
                    raw_text="force shell tts test",
                    intent=Intent.FORCE_SHELL_TTS_TEST,
                )
            )
        )

    worker = threading.Thread(target=_run_action)
    worker.start()
    threading.Event().wait(0.15)
    assert submit_modal_line("yes") is True
    worker.join(timeout=5.0)
    assert len(results) == 1
    assert results[0].status == ActionStatus.SUCCESS
    assert get_selected_verified_audio_backend() == SHELL_SUBPROCESS_BACKEND


def test_normal_commands_resume_after_modal(monkeypatch):
    from ui.console_modal import reset_modal_for_tests, run_modal_yes_no_prompt, submit_modal_line
    from ui.operator_console import OperatorConsole

    reset_modal_for_tests()
    monkeypatch.setattr("ui.console_modal._operator_console_stdin_shared", lambda: True)
    app = MagicMock()
    app._running = True
    app.runtime = MagicMock()
    app.runtime.running = True
    calls: list[str] = []

    def _process(_app, phrase, **kwargs):
        calls.append(phrase)

    monkeypatch.setattr("voice.voice_loop.process_console_command", _process)
    console = OperatorConsole(app)

    def _modal() -> None:
        run_modal_yes_no_prompt("heard?", timeout_seconds=5.0)

    worker = threading.Thread(target=_modal)
    worker.start()
    threading.Event().wait(0.1)
    submit_modal_line("yes")
    worker.join(timeout=3.0)
    console._handle_line("open dashboard")
    assert calls == ["open dashboard"]


def test_no_duplicate_execution(monkeypatch):
    from core.runtime_state import RuntimeState
    from ui.operator_console import OperatorConsole

    app = MagicMock()
    app._running = True
    app.runtime = RuntimeState()
    app.runtime.running = True
    started = threading.Event()
    release = threading.Event()
    count = {"n": 0}

    def _slow_process(_app, phrase, **kwargs):
        count["n"] += 1
        started.set()
        release.wait(timeout=2.0)

    monkeypatch.setattr("voice.voice_loop.process_console_command", _slow_process)
    console = OperatorConsole(app)
    t1 = threading.Thread(target=console._dispatch_line, args=("open dashboard",))
    t2 = threading.Thread(target=console._dispatch_line, args=("open dashboard",))
    t1.start()
    assert started.wait(timeout=1.0)
    t2.start()
    t1.join(timeout=2.0)
    release.set()
    t2.join(timeout=2.0)
    assert count["n"] == 1
