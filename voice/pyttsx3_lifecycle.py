"""pyttsx3 engine lifecycle — fresh engine per speech, global execution lock."""

from __future__ import annotations

import gc
import threading
from contextlib import contextmanager
from typing import Iterator

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.pyttsx3_lifecycle")

_EXECUTION_LOCK = threading.Lock()
_runloop_active = False
_engine_active = False
_speech_lock_held = False
_active_engine: object | None = None
_abandoned_engines: list[object] = []


class Pyttsx3LifecycleError(RuntimeError):
    """pyttsx3 lifecycle / run-loop conflict."""


def get_lifecycle_snapshot() -> dict[str, bool]:
    with _EXECUTION_LOCK:
        return {
            "runloop_active": _runloop_active,
            "engine_active": _engine_active,
            "speech_lock_held": _speech_lock_held,
        }


def runloop_active() -> bool:
    return get_lifecycle_snapshot()["runloop_active"]


def engine_active() -> bool:
    return get_lifecycle_snapshot()["engine_active"]


def speech_lock_held() -> bool:
    return get_lifecycle_snapshot()["speech_lock_held"]


def _dispose_engine_object(engine: object | None, *, abandon: bool = False) -> None:
    global _active_engine, _engine_active, _runloop_active
    if engine is None:
        return
    try:
        engine.stop()
    except Exception as exc:
        logger.debug("engine.stop skipped: %s", exc)
    try:
        end_loop = getattr(engine, "endLoop", None)
        if callable(end_loop):
            end_loop()
    except Exception:
        pass
    if abandon:
        _abandoned_engines.append(engine)
        _runloop_active = True
    else:
        _runloop_active = bool(_abandoned_engines)
    if _active_engine is engine:
        _active_engine = None
    _engine_active = _active_engine is not None


def _cleanup_abandoned_engines() -> None:
    global _abandoned_engines, _runloop_active
    if not _abandoned_engines:
        _runloop_active = False
        return
    stale = _abandoned_engines
    _abandoned_engines = []
    for engine in stale:
        try:
            engine.stop()
        except Exception:
            pass
    gc.collect()
    _runloop_active = False


def create_fresh_engine(rate_raw: str):
    """Create a new pyttsx3 engine; never reuse a cached instance."""
    global _active_engine, _engine_active
    try:
        import pyttsx3
    except ImportError as exc:
        raise Pyttsx3LifecycleError(
            "pyttsx3 is not installed. Run: pip install pyttsx3"
        ) from exc
    from voice.tts_pyttsx3 import Pyttsx3TTSError, _configure_engine

    try:
        engine = pyttsx3.init()
    except Exception as exc:
        raise Pyttsx3TTSError(f"Could not initialize pyttsx3: {exc}") from exc
    _configure_engine(engine, rate_raw)
    _active_engine = engine
    _engine_active = True
    return engine


def mark_runloop_started() -> None:
    global _runloop_active
    _runloop_active = True


def mark_runloop_finished(*, abandon: bool = False) -> None:
    global _runloop_active
    if abandon:
        _runloop_active = True
    else:
        _runloop_active = bool(_abandoned_engines)


def abandon_active_engine(engine: object | None) -> None:
    """Stop and orphan a hung engine; next speech starts fresh after lock release."""
    _dispose_engine_object(engine, abandon=True)
    gc.collect()


@contextmanager
def direct_speech_lock() -> Iterator[None]:
    """Global pyttsx3 speech lock without creating an engine on the caller thread."""
    global _speech_lock_held

    acquired = _EXECUTION_LOCK.acquire(timeout=120.0)
    if not acquired:
        raise Pyttsx3LifecycleError("Timed out waiting for pyttsx3 speech lock")
    _speech_lock_held = True
    try:
        _cleanup_abandoned_engines()
        yield None
    finally:
        _speech_lock_held = False
        _EXECUTION_LOCK.release()
        gc.collect()


@contextmanager
def direct_speech_execution(rate_raw: str) -> Iterator[object]:
    """
    Global TTS lock — only one pyttsx3 runAndWait sequence at a time.
    Always yields a fresh engine; disposes it on exit.
    """
    global _speech_lock_held

    acquired = _EXECUTION_LOCK.acquire(timeout=120.0)
    if not acquired:
        raise Pyttsx3LifecycleError("Timed out waiting for pyttsx3 speech lock")
    _speech_lock_held = True
    engine = None
    hung = False
    try:
        _cleanup_abandoned_engines()
        engine = create_fresh_engine(rate_raw)
        yield engine
    finally:
        hung = _runloop_active
        if engine is not None:
            _dispose_engine_object(engine, abandon=hung)
        else:
            global _active_engine, _engine_active
            _active_engine = None
            _engine_active = False
        _speech_lock_held = False
        _EXECUTION_LOCK.release()
        gc.collect()


def reset_pyttsx3_lifecycle_for_tests() -> None:
    global _runloop_active, _engine_active, _speech_lock_held, _active_engine, _abandoned_engines
    with _EXECUTION_LOCK:
        for engine in list(_abandoned_engines):
            try:
                engine.stop()
            except Exception:
                pass
        _abandoned_engines = []
        if _active_engine is not None:
            try:
                _active_engine.stop()
            except Exception:
                pass
        _active_engine = None
        _runloop_active = False
        _engine_active = False
        _speech_lock_held = False
    gc.collect()
