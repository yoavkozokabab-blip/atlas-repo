"""Pytest path setup and overlay/Qt test isolation."""

from __future__ import annotations

import os
import sys
import getpass
import importlib
import subprocess
from pathlib import Path

# Phase 41.5 — deterministic test runtime (no real audio unless opted in).
os.environ.setdefault("JARVIS_TEST_MODE", "1")
# Tests default to non-stable voice unless a case sets VOICE_RUNTIME_MODE (see .env stable preset).
os.environ["VOICE_RUNTIME_MODE"] = ""
os.environ["VOICE_LATENCY_MODE"] = ""
# Avoid loading real Whisper models in most tests (Phase 42 v2 tests opt in).
os.environ.setdefault("STT_MULTIPASS_ENABLED", "0")
os.environ.setdefault("STT_STACK_ENABLED", "0")
os.environ.setdefault("SEMANTIC_LLM_ENABLED", "0")
os.environ.setdefault("STT_STREAMING_BUFFER_ENABLED", "0")
os.environ.setdefault("CONVERSATION_SEMANTIC_STREAM_ENABLED", "0")
# Headless overlay by default — no real QApplication during pytest (avoids Windows AV on exit).
os.environ.setdefault("JARVIS_OVERLAY_QT", "0")


def _configure_pytest_temproot_on_windows() -> None:
    """Keep pytest temp roots usable in this Windows sandbox."""
    if os.name != "nt" or os.environ.get("PYTEST_DEBUG_TEMPROOT"):
        return
    root = Path(__file__).resolve().parent.parent / "tests_tmp" / "pytest_temp"
    user_root = root / f"pytest-of-{getpass.getuser() or 'unknown'}"
    try:
        user_root.mkdir(parents=True, exist_ok=True)
        os.environ["PYTEST_DEBUG_TEMPROOT"] = str(root)
    except OSError:
        pass


def _patch_pytest_tmpdir_mode_on_windows() -> None:
    """Avoid unreadable pytest temp dirs on constrained Windows sandboxes."""
    if os.name != "nt":
        return
    try:
        import _pytest.pathlib as pytest_pathlib
        import _pytest.tmpdir as pytest_tmpdir
    except Exception:
        return

    original = pytest_pathlib.make_numbered_dir
    if getattr(original, "_jarvis_windows_mode_patch", False):
        return

    def make_numbered_dir_usable(root, prefix, mode=0o700):
        return original(root, prefix, 0o777)

    make_numbered_dir_usable._jarvis_windows_mode_patch = True
    pytest_pathlib.make_numbered_dir = make_numbered_dir_usable
    pytest_tmpdir.make_numbered_dir = make_numbered_dir_usable


_configure_pytest_temproot_on_windows()
_patch_pytest_tmpdir_mode_on_windows()

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.test_runtime import shutdown_jarvis_test_runtime
from ui.overlay_app import reset_overlay_controller


def _cleanup_pytest_child_processes() -> None:
    """Reap Python children spawned by audio/STT subprocess tests."""
    try:
        import psutil

        parent = psutil.Process(os.getpid())
        children = parent.children(recursive=True)
    except Exception:
        return
    for child in children:
        try:
            name = (child.name() or "").lower()
        except Exception:
            continue
        if name not in {"py.exe", "python.exe", "pythonw.exe"}:
            continue
        try:
            child.kill()
        except Exception:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3,
                    check=False,
                )
            except Exception:
                pass


@pytest.fixture(autouse=True)
def _jarvis_test_runtime_cleanup(monkeypatch):
    """
    Reset runtime/overlay/voice workers between tests.
    Disables fast-ack TTS speak (can block after long runs).
    """
    try:
        import config

        importlib.reload(config)
    except Exception:
        pass
    shutdown_jarvis_test_runtime()
    try:
        from voice.tts_watchdog import end_speak_session

        end_speak_session()
    except Exception:
        pass
    try:
        from core.runtime_state import get_runtime_state, reset_runtime_state

        reset_runtime_state()
        get_runtime_state().set_overlay(False)
    except Exception:
        pass

    import conversation.latency_hints as _latency_hints

    _orig_fast_ack = _latency_hints.deliver_fast_ack

    def _fast_ack_without_tts(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["speak"] = False
        return _orig_fast_ack(*args, **kwargs)

    monkeypatch.setattr(_latency_hints, "deliver_fast_ack", _fast_ack_without_tts)
    yield
    try:
        from voice.tts_watchdog import end_speak_session

        end_speak_session()
    except Exception:
        pass
    shutdown_jarvis_test_runtime()
    _cleanup_pytest_child_processes()
    reset_overlay_controller()
    try:
        from core.runtime_state import reset_runtime_state

        reset_runtime_state()
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _jarvis_session_shutdown():
    yield
    shutdown_jarvis_test_runtime(join_timeout=2.0)
    _cleanup_pytest_child_processes()


@pytest.fixture
def allow_audio_playback(monkeypatch):
    """Opt-in fixture for tests that must exercise real playback."""
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    yield
    monkeypatch.delenv("JARVIS_ALLOW_AUDIO_PLAYBACK", raising=False)


@pytest.fixture
def safe_qt_app(monkeypatch):
    """Opt-in: allow a single shared QApplication for tests that need real Qt."""
    monkeypatch.setenv("JARVIS_OVERLAY_QT", "1")
    monkeypatch.setattr("config.OVERLAY_QT_ENABLED", True)
    monkeypatch.setattr("ui.overlay_app.OVERLAY_QT_ENABLED", True)
    yield
    reset_overlay_controller()
    shutdown_jarvis_test_runtime()
