"""pyttsx3 COM-thread playback tests (Phase 59.5)."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from voice.playback_metrics import format_playback_metrics, get_last_playback_metrics, reset_playback_metrics_for_tests
from voice.pyttsx3_completion import run_and_wait_nonblocking, run_direct_tts_isolated_test


def test_finished_utterance_callback_accepts_completed_kwarg() -> None:
    """SAPI finished-utterance passes completed=; callbacks must not swallow it."""
    reset_playback_metrics_for_tests()

    class _Engine:
        def __init__(self) -> None:
            self._connects: dict[str, list] = {}

        def connect(self, topic: str, cb) -> None:
            self._connects.setdefault(topic, []).append(cb)

        def emit(self, topic: str, **kwargs: object) -> None:
            for cb in self._connects.get(topic, []):
                cb(**kwargs)

    from voice.pyttsx3_completion import _WorkerState, _attach_utterance_callbacks

    state = _WorkerState()
    engine = _Engine()
    _attach_utterance_callbacks(engine, state)
    engine.emit("started-utterance")
    engine.emit("finished-utterance", completed=True)
    snap = state.snapshot()
    assert snap["utterance_started"] is True
    assert snap["utterance_finished"] is True


def test_create_engine_on_worker_uses_same_thread_for_say_and_run() -> None:
    reset_playback_metrics_for_tests()
    events: list[str] = []
    thread_ids: list[int] = []

    mock_engine = MagicMock()

    def _say(text: str) -> None:
        del text
        events.append("say")
        thread_ids.append(threading.get_ident())

    def _run_and_wait() -> None:
        events.append("runAndWait")
        thread_ids.append(threading.get_ident())

    mock_engine.say = MagicMock(side_effect=_say)
    mock_engine.runAndWait = MagicMock(side_effect=_run_and_wait)

    with patch("voice.pyttsx3_completion._create_worker_engine", return_value=mock_engine), patch(
        "voice.pyttsx3_completion._com_thread_enter",
        return_value="pythoncom",
    ), patch("voice.pyttsx3_completion._com_thread_exit"):
        result = run_and_wait_nonblocking(
            text="Hello COM thread.",
            rate_raw="185",
            create_engine_on_worker=True,
        )

    assert result.ok is True, result
    assert events == ["say", "runAndWait"]
    assert len(set(thread_ids)) == 1
    metrics = get_last_playback_metrics()
    assert metrics is not None
    assert metrics.playback_completed is True


def test_emergency_subprocess_fallback_on_hard_timeout() -> None:
    reset_playback_metrics_for_tests()
    mock_engine = MagicMock()
    mock_engine.runAndWait = MagicMock(side_effect=lambda: threading.Event().wait(3600))

    fallback = MagicMock(ok=True, exit_code=0, stderr="", timed_out=False)
    with patch("voice.pyttsx3_completion._create_worker_engine", return_value=mock_engine), patch(
        "voice.pyttsx3_completion._com_thread_enter",
        return_value=None,
    ), patch("voice.pyttsx3_completion._com_thread_exit"), patch(
        "voice.pyttsx3_completion.completion_grace_recovery_enabled",
        return_value=False,
    ), patch("voice.pyttsx3_completion.get_direct_completion_timeout_seconds", return_value=0.35), patch(
        "voice.tts_subprocess.speak_subprocess_pyttsx3",
        return_value=fallback,
    ):
        result = run_and_wait_nonblocking(
            text="Fallback phrase.",
            rate_raw="185",
            create_engine_on_worker=True,
        )

    assert result.ok is True, result
    assert result.fallback_path == "subprocess_pyttsx3"
    assert "forced recovery count: 1" in format_playback_metrics()


def test_direct_tts_isolated_test_invokes_worker_path() -> None:
    with patch(
        "voice.pyttsx3_completion.run_and_wait_nonblocking",
        return_value=MagicMock(
            ok=True,
            elapsed_ms=100.0,
            fallback_path="",
            error="",
            utterance_started=True,
            utterance_finished=True,
        ),
    ) as run_mock, patch("voice.pyttsx3_lifecycle.direct_speech_lock") as lock_ctx:
        lock_ctx.return_value.__enter__ = MagicMock(return_value=None)
        lock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = run_direct_tts_isolated_test("Short test.")
    assert result.ok is True
    run_mock.assert_called_once()
    assert run_mock.call_args.kwargs["create_engine_on_worker"] is True
