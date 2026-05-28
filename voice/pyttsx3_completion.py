"""Non-blocking pyttsx3 COM completion recovery (direct SAPI speech)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import os

from core.logger import setup_logger
from voice.tts_config import resolve_pyttsx_rate

logger = setup_logger("jarvis.voice.pyttsx3_completion")

COMPLETION_PIPELINE_VERSION = "v2"
COMPLETION_HANDLER = "voice.pyttsx3_completion:run_and_wait_nonblocking"
GRACE_RECOVERY_ENABLED_DEFAULT = True
HEURISTIC_RECOVERY_ENABLED = True

MIN_PLAYBACK_SUCCESS_MS = 300.0
MAX_ESTIMATED_SECONDS = 15.0
MIN_ESTIMATED_SECONDS = 0.45
_CHARS_PER_SECOND_AT_185 = 14.0
# SAPI message pump + device start often exceeds raw text estimate by a few hundred ms.
COMPLETION_PRIMARY_SLACK_S = 0.85
POST_UTTERANCE_RUNANDWAIT_S = 0.75
GRACE_WINDOW_S = 10.0
POST_GRACE_RUNANDWAIT_S = 5.0
POLL_INTERVAL_S = 0.05

_last_completion_hang_success_mono: float = 0.0
_hang_success_lock = threading.Lock()


@dataclass(frozen=True)
class DirectPlaybackResult:
    ok: bool
    completion_hang: bool = False
    delayed_completion_recovered: bool = False
    playback_started: bool = False
    elapsed_ms: float = 0.0
    estimated_ms: float = 0.0
    error: str = ""
    fallback_path: str = ""
    utterance_started: bool = False
    utterance_finished: bool = False


def completion_grace_recovery_enabled() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "COMPLETION_GRACE_RECOVERY_ENABLED", GRACE_RECOVERY_ENABLED_DEFAULT))
    except Exception:
        return GRACE_RECOVERY_ENABLED_DEFAULT


def get_direct_completion_timeout_seconds(text: str, rate_raw: str = "") -> float:
    """Outer watchdog/operation timeout budget for direct pyttsx3 completion."""
    estimated = estimate_speech_duration_seconds(text, rate_raw)
    wait_s = max(MIN_PLAYBACK_SUCCESS_MS / 1000.0, estimated)
    if not completion_grace_recovery_enabled():
        return max(wait_s + 3.0, 8.0)
    return wait_s + GRACE_WINDOW_S + POST_GRACE_RUNANDWAIT_S + 2.0


def get_completion_pipeline_info() -> dict[str, object]:
    from pathlib import Path

    source_file = str(Path(__file__).resolve())
    legacy_detected = False
    try:
        source_text = Path(source_file).read_text(encoding="utf-8")
        legacy_detected = (
            COMPLETION_PIPELINE_VERSION != "v2"
            or "completion_grace_start" not in source_text
            or "GRACE_WINDOW_S" not in source_text
        )
    except Exception:
        legacy_detected = True
    return {
        "version": COMPLETION_PIPELINE_VERSION,
        "handler": COMPLETION_HANDLER,
        "source_file": source_file,
        "grace_recovery_enabled": completion_grace_recovery_enabled(),
        "heuristic_enabled": HEURISTIC_RECOVERY_ENABLED,
        "legacy_detected": legacy_detected,
        "grace_window_s": GRACE_WINDOW_S,
        "post_grace_s": POST_GRACE_RUNANDWAIT_S,
    }


def _emit_pipeline_trace(info: dict[str, object]) -> None:
    print(
        f"[TTS_DIRECT] using_completion_pipeline={info.get('version')}",
        flush=True,
    )
    print(
        f"[TTS_DIRECT] grace_recovery_enabled={info.get('grace_recovery_enabled')}",
        flush=True,
    )
    print(
        f"[TTS_DIRECT] heuristic_enabled={info.get('heuristic_enabled')}",
        flush=True,
    )
    print(
        f"[TTS_DIRECT] completion_pipeline_source={info.get('handler')}",
        flush=True,
    )
    print(
        f"[TTS_DIRECT] completion_module_path={info.get('source_file')}",
        flush=True,
    )


def log_completion_pipeline_startup() -> None:
    info = get_completion_pipeline_info()
    _emit_pipeline_trace(info)
    try:
        from voice.audio_status import register_completion_pipeline_at_startup

        register_completion_pipeline_at_startup(
            version=str(info["version"]),
            handler=str(info["handler"]),
            grace_recovery_enabled=bool(info["grace_recovery_enabled"]),
            heuristic_enabled=bool(info["heuristic_enabled"]),
            legacy_detected=bool(info["legacy_detected"]),
            source_file=str(info["source_file"]),
        )
    except Exception as exc:
        logger.debug("completion pipeline startup registration skipped: %s", exc)
    if info.get("legacy_detected"):
        print(
            "[WARNING] legacy completion path active — grace recovery module missing or stale; "
            "restart JARVIS after updating voice/pyttsx3_completion.py",
            flush=True,
        )


def verify_completion_pipeline_at_startup() -> bool:
    info = get_completion_pipeline_info()
    log_completion_pipeline_startup()
    return not bool(info.get("legacy_detected"))


def assert_completion_pipeline_v2_at_startup() -> None:
    """Hard startup gate — refuse to run with legacy/stale completion module."""
    from core.startup import StartupError

    info = get_completion_pipeline_info()
    log_completion_pipeline_startup()
    version = str(info.get("version") or "")
    legacy = bool(info.get("legacy_detected"))
    if version != "v2" or legacy:
        raise StartupError(
            "Completion pipeline v2 required at startup; "
            f"version={version!r} legacy_detected={legacy} "
            f"source={info.get('source_file')!r}. "
            "Restart JARVIS from local_jarvis/ after updating voice/pyttsx3_completion.py."
        )
    if not bool(info.get("grace_recovery_enabled")):
        raise StartupError(
            "Completion grace recovery is disabled (COMPLETION_GRACE_RECOVERY_ENABLED=false)."
        )


def estimate_speech_duration_seconds(text: str, rate_raw: str = "") -> float:
    """Estimate audible playback duration from text length and pyttsx3 rate."""
    rate = resolve_pyttsx_rate(rate_raw)
    chars = max(1, len(text or ""))
    chars_per_second = max(6.0, rate / _CHARS_PER_SECOND_AT_185)
    seconds = (chars / chars_per_second) + 0.25
    return max(MIN_ESTIMATED_SECONDS, min(MAX_ESTIMATED_SECONDS, seconds))


def recent_completion_hang_success(*, within_seconds: float = 8.0) -> bool:
    with _hang_success_lock:
        if _last_completion_hang_success_mono <= 0:
            return False
        return (time.monotonic() - _last_completion_hang_success_mono) <= within_seconds


def mark_completion_hang_success() -> None:
    global _last_completion_hang_success_mono
    with _hang_success_lock:
        _last_completion_hang_success_mono = time.monotonic()


def reset_completion_hang_tracking() -> None:
    global _last_completion_hang_success_mono
    with _hang_success_lock:
        _last_completion_hang_success_mono = 0.0


def _trace(label: str, **fields: object) -> None:
    parts = " ".join(f"{key}={value}" for key, value in fields.items())
    print(f"[TTS_DIRECT] {label} {parts}".strip(), flush=True)
    logger.debug("%s %s", label, parts)


def _com_thread_enter() -> str | None:
    if os.name != "nt":
        return None
    try:
        import pythoncom

        pythoncom.CoInitialize()
        return "pythoncom"
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.ole32.CoInitializeEx(None, 2)
        return "ctypes"
    except Exception:
        return None


def _com_thread_exit(token: str | None) -> None:
    if not token:
        return
    if token == "pythoncom":
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except Exception:
            pass
    elif token == "ctypes":
        try:
            import ctypes

            ctypes.windll.ole32.CoUninitialize()
        except Exception:
            pass


def _attach_utterance_callbacks(engine: object, state: "_WorkerState") -> None:
    def _started(*args: object, **kwargs: object) -> None:
        del args, kwargs
        with state.lock:
            state.utterance_started = True
        _trace("utterance_started", thread_id=threading.get_ident())

    def _finished(*args: object, **kwargs: object) -> None:
        del args
        with state.lock:
            state.utterance_finished = True
        trace_fields = {"thread_id": threading.get_ident()}
        if "completed" in kwargs:
            trace_fields["completed"] = kwargs["completed"]
        _trace("utterance_finished", **trace_fields)

    try:
        engine.connect("started-utterance", _started)
        engine.connect("finished-utterance", _finished)
    except Exception as exc:
        _trace("utterance_callbacks_unavailable", err=str(exc)[:120])


def _create_worker_engine(rate_raw: str) -> object:
    import pyttsx3

    from voice.tts_pyttsx3 import _configure_engine

    engine = pyttsx3.init()
    _configure_engine(engine, rate_raw)
    return engine


def _try_emergency_playback_fallback(text: str) -> DirectPlaybackResult | None:
    safe = (text or "").strip()
    if not safe:
        return None
    _trace("emergency_fallback_start", path="subprocess_pyttsx3")
    try:
        from voice.playback_metrics import record_forced_recovery
        from voice.tts_subprocess import speak_subprocess_pyttsx3

        sub = speak_subprocess_pyttsx3(safe)
        if sub.ok:
            record_forced_recovery(path="subprocess_pyttsx3")
            _trace("emergency_fallback_success", path="subprocess_pyttsx3")
            return DirectPlaybackResult(
                ok=True,
                playback_started=True,
                fallback_path="subprocess_pyttsx3",
                error="",
            )
        _trace("emergency_fallback_failed", exit_code=sub.exit_code, stderr=(sub.stderr or "")[:120])
    except Exception as exc:
        _trace("emergency_fallback_failed", err=str(exc)[:160])
    return None


def _dispose_engine_async(engine: object) -> None:
    def _cleanup() -> None:
        try:
            from voice.pyttsx3_lifecycle import abandon_active_engine

            abandon_active_engine(engine)
        except Exception as exc:
            logger.debug("pyttsx3 dispose skipped: %s", exc)
        try:
            from voice.tts_pyttsx3 import reset_pyttsx3_engine

            reset_pyttsx3_engine()
        except Exception as exc:
            logger.debug("pyttsx3 reset skipped: %s", exc)

    threading.Thread(
        target=_cleanup,
        name="jarvis-pyttsx3-dispose",
        daemon=True,
    ).start()


@dataclass
class _WorkerState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    playback_started: bool = False
    run_and_wait_started: bool = False
    run_and_wait_returned: bool = False
    completion_event_set: bool = False
    utterance_started: bool = False
    utterance_finished: bool = False
    worker_thread_id: int = 0
    error: Exception | None = None

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "playback_started": self.playback_started,
                "run_and_wait_started": self.run_and_wait_started,
                "run_and_wait_returned": self.run_and_wait_returned,
                "completion_event_set": self.completion_event_set,
                "utterance_started": self.utterance_started,
                "utterance_finished": self.utterance_finished,
                "worker_thread_id": self.worker_thread_id,
                "error": str(self.error) if self.error is not None else "",
            }


def run_and_wait_nonblocking(
    engine: object | None = None,
    *,
    text: str,
    rate_raw: str,
    on_playback_start: Callable[[], None] | None = None,
    create_engine_on_worker: bool = False,
) -> DirectPlaybackResult:
    """
    Run pyttsx3 runAndWait in an isolated worker.

    Estimated timeout means "still running", not failure.
    Hard failure only after grace window or on worker exception.
    """
    from voice.audio_status import (
        clear_completion_grace,
        mark_speech_success_heuristic_active,
        playback_audible_confirmed,
        record_completion_hang,
        record_delayed_completion_recovered,
        set_completion_grace_active,
    )
    from voice.tts_watchdog import begin_speak_session, end_speak_session, set_pending_speak_timeout

    pipeline = get_completion_pipeline_info()
    _emit_pipeline_trace(pipeline)
    try:
        from voice.audio_status import register_completion_pipeline_invocation

        register_completion_pipeline_invocation(
            version=str(pipeline["version"]),
            handler=str(pipeline["handler"]),
            grace_recovery_enabled=bool(pipeline["grace_recovery_enabled"]),
            heuristic_enabled=bool(pipeline["heuristic_enabled"]),
            legacy_detected=bool(pipeline["legacy_detected"]),
        )
    except Exception:
        pass

    try:
        from voice.pyttsx3_lifecycle import mark_runloop_started

        mark_runloop_started()
    except Exception:
        pass

    estimated_s = estimate_speech_duration_seconds(text, rate_raw)
    estimated_ms = estimated_s * 1000.0
    wait_s = max(MIN_PLAYBACK_SUCCESS_MS / 1000.0, estimated_s + COMPLETION_PRIMARY_SLACK_S)
    outer_timeout_s = get_direct_completion_timeout_seconds(text, rate_raw)
    try:
        set_pending_speak_timeout(outer_timeout_s)
        begin_speak_session()
    except Exception as exc:
        logger.debug("completion speak session setup skipped: %s", exc)

    state = _WorkerState()
    done = threading.Event()
    t0 = time.perf_counter()
    primary_timeout_warning = False
    grace_started = False

    def _elapsed_ms() -> float:
        return (time.perf_counter() - t0) * 1000.0

    def _fail(error: str, *, reason: str, worker: threading.Thread) -> DirectPlaybackResult:
        snap = state.snapshot()
        clear_completion_grace()
        _trace(
            "hard_failure",
            reason=reason,
            err=error,
            elapsed_ms_exact=round(_elapsed_ms(), 2),
            worker_thread_alive=worker.is_alive(),
            **snap,
        )
        _trace(
            "final_success_decision",
            completion_success=False,
            reason=reason,
            err=error,
            elapsed_ms_exact=round(_elapsed_ms(), 2),
            worker_thread_alive=worker.is_alive(),
            **snap,
        )
        try:
            from voice.pyttsx3_lifecycle import mark_runloop_finished

            mark_runloop_finished(abandon=False)
        except Exception:
            pass
        end_speak_session()
        try:
            from voice.playback_metrics import record_playback_metrics

            snap = state.snapshot()
            record_playback_metrics(
                audio_started=bool(snap.get("playback_started")),
                playback_completed=False,
                playback_duration_ms=_elapsed_ms(),
                playback_timeout="timeout" in reason,
                worker_thread_id=int(snap.get("worker_thread_id") or 0),
                utterance_started=bool(snap.get("utterance_started")),
                utterance_finished=bool(snap.get("utterance_finished")),
            )
        except Exception:
            pass
        return DirectPlaybackResult(
            ok=False,
            playback_started=bool(snap.get("playback_started")),
            elapsed_ms=_elapsed_ms(),
            estimated_ms=estimated_ms,
            error=error,
            utterance_started=bool(snap.get("utterance_started")),
            utterance_finished=bool(snap.get("utterance_finished")),
        )

    def _success(
        *,
        completion_hang: bool = False,
        delayed_recovery: bool = False,
        reason: str,
    ) -> DirectPlaybackResult:
        snap = state.snapshot()
        clear_completion_grace()
        if delayed_recovery or completion_hang:
            record_delayed_completion_recovered()
            record_completion_hang()
            mark_completion_hang_success()
            mark_speech_success_heuristic_active()
        _trace(
            "final_success_decision",
            completion_success=True,
            reason=reason,
            completion_hang=completion_hang,
            delayed_completion_recovered=delayed_recovery or completion_hang,
            elapsed_ms_exact=round(_elapsed_ms(), 2),
            **snap,
        )
        if completion_hang and not delayed_recovery:
            try:
                from voice.pyttsx3_lifecycle import mark_runloop_finished

                mark_runloop_finished(abandon=True)
            except Exception:
                pass
        else:
            try:
                from voice.pyttsx3_lifecycle import mark_runloop_finished

                mark_runloop_finished(abandon=False)
            except Exception:
                pass
        end_speak_session()
        snap = state.snapshot()
        try:
            from voice.playback_metrics import record_playback_metrics

            record_playback_metrics(
                audio_started=bool(snap.get("playback_started")),
                playback_completed=True,
                playback_duration_ms=_elapsed_ms(),
                playback_timeout=completion_hang or primary_timeout_warning,
                worker_thread_id=int(snap.get("worker_thread_id") or 0),
                utterance_started=bool(snap.get("utterance_started")),
                utterance_finished=bool(snap.get("utterance_finished")),
            )
        except Exception:
            pass
        return DirectPlaybackResult(
            ok=True,
            completion_hang=completion_hang,
            delayed_completion_recovered=delayed_recovery or completion_hang,
            playback_started=bool(snap.get("playback_started")),
            elapsed_ms=_elapsed_ms(),
            estimated_ms=estimated_ms,
            utterance_started=bool(snap.get("utterance_started")),
            utterance_finished=bool(snap.get("utterance_finished")),
        )

    def _normal_completion_success(
        *,
        reason: str,
        delayed_recovery: bool = False,
        completion_hang: bool = False,
    ) -> DirectPlaybackResult | None:
        snap = state.snapshot()
        err = snap.get("error") or ""
        if err:
            return None
        if not snap.get("run_and_wait_started"):
            return None
        if not snap.get("playback_started"):
            return None
        if _elapsed_ms() < MIN_PLAYBACK_SUCCESS_MS:
            return None
        finished = bool(snap.get("utterance_finished"))
        returned = bool(snap.get("run_and_wait_returned"))
        if not returned and not finished:
            return None
        if finished and not returned and _elapsed_ms() < wait_s * 1000.0 + POST_UTTERANCE_RUNANDWAIT_S * 1000.0:
            return None
        hang = bool(
            completion_hang
            or delayed_recovery
            or (primary_timeout_warning and not finished)
        )
        return _success(
            completion_hang=hang,
            delayed_recovery=delayed_recovery or (primary_timeout_warning and not finished),
            reason=reason,
        )

    def _evaluate(
        worker: threading.Thread,
        *,
        allow_heuristic: bool,
        reason: str,
        delayed_recovery: bool = False,
    ) -> DirectPlaybackResult | None:
        snap = state.snapshot()
        if snap.get("error"):
            return _fail(str(snap["error"]), reason=f"{reason}:worker_error", worker=worker)

        normal = _normal_completion_success(
            reason=f"{reason}:runAndWait_returned",
            delayed_recovery=delayed_recovery,
            completion_hang=delayed_recovery,
        )
        if normal is not None:
            return normal

        if allow_heuristic and not snap.get("run_and_wait_returned"):
            elapsed = _elapsed_ms()
            heuristic_ok = (
                bool(snap.get("playback_started"))
                and elapsed >= MIN_PLAYBACK_SUCCESS_MS
                and playback_audible_confirmed()
                and worker.is_alive()
            )
            if heuristic_ok:
                _trace(
                    "heuristic_success_triggered",
                    elapsed_ms_exact=round(elapsed, 2),
                    worker_alive=worker.is_alive(),
                )
                mark_speech_success_heuristic_active()
                record_completion_hang()
                mark_completion_hang_success()
                _dispose_engine_async(engine)
                return _success(
                    completion_hang=True,
                    delayed_recovery=True,
                    reason=f"{reason}:heuristic",
                )
        return None

    def _poll_until(
        worker: threading.Thread,
        deadline: float,
        *,
        allow_heuristic: bool,
        reason: str,
        delayed_recovery: bool = False,
        on_tick: Callable[[], None] | None = None,
    ) -> DirectPlaybackResult | None:
        while time.perf_counter() < deadline:
            if on_tick is not None:
                on_tick()
            result = _evaluate(
                worker,
                allow_heuristic=allow_heuristic,
                reason=reason,
                delayed_recovery=delayed_recovery,
            )
            if result is not None:
                return result
            if done.is_set():
                result = _evaluate(
                    worker,
                    allow_heuristic=allow_heuristic,
                    reason=f"{reason}_done",
                    delayed_recovery=delayed_recovery,
                )
                if result is not None:
                    return result
            time.sleep(POLL_INTERVAL_S)
        return None

    def _worker() -> None:
        worker_engine = engine
        com_token: str | None = None
        owned_engine = False
        try:
            with state.lock:
                state.worker_thread_id = threading.get_ident()
            com_token = _com_thread_enter()
            _trace("worker_thread_start", thread_id=threading.get_ident(), com=com_token or "none")
            if create_engine_on_worker or worker_engine is None:
                worker_engine = _create_worker_engine(rate_raw)
                owned_engine = True
                _trace("worker_engine_created", thread_id=threading.get_ident())
            _attach_utterance_callbacks(worker_engine, state)
            if text.strip():
                _trace("utterance_say_start", thread_id=threading.get_ident(), chars=len(text))
                worker_engine.say(text)
            if on_playback_start is not None:
                on_playback_start()
            with state.lock:
                state.playback_started = True
            _trace("runAndWait_enter", thread_id=threading.get_ident())
            with state.lock:
                state.run_and_wait_started = True
            worker_engine.runAndWait()
            _trace("runAndWait_exit", thread_id=threading.get_ident())
            with state.lock:
                state.run_and_wait_returned = True
        except Exception as exc:
            with state.lock:
                state.error = exc
            _trace("worker_exception", err=str(exc)[:160], thread_id=threading.get_ident())
        finally:
            if owned_engine and worker_engine is not None:
                snap = state.snapshot()
                if not snap.get("run_and_wait_returned"):
                    try:
                        _trace("engine_stop_invoked", thread_id=threading.get_ident())
                        worker_engine.stop()
                    except Exception as exc:
                        _trace("engine_stop_failed", err=str(exc)[:120])
            with state.lock:
                state.completion_event_set = True
            done.set()
            _trace(
                "completion_event_set",
                done=True,
                thread_id=threading.get_ident(),
                worker_alive=threading.current_thread().is_alive(),
            )
            _com_thread_exit(com_token)

    worker = threading.Thread(
        target=_worker,
        name="jarvis-pyttsx3-runAndWait",
        daemon=True,
    )
    worker.start()

    _trace("completion_event_wait_start", wait_s=round(wait_s, 3))

    primary_deadline = t0 + wait_s
    result = _poll_until(
        worker,
        primary_deadline,
        allow_heuristic=False,
        reason="primary_wait",
    )
    if result is not None:
        _trace("completion_event_wait_end", phase="primary", ok=result.ok)
        return result

    snap = state.snapshot()
    if not snap.get("run_and_wait_returned"):
        primary_timeout_warning = True
        _trace(
            "timeout_warning",
            message="speech_still_running",
            worker_alive=worker.is_alive(),
            elapsed_ms_exact=round(_elapsed_ms(), 2),
        )
        if not completion_grace_recovery_enabled():
            _trace("entering_grace_recovery", enabled=False, reason="grace_recovery_disabled")
        elif worker.is_alive():
            _trace("entering_grace_recovery", enabled=True)
            grace_started = True
            set_completion_grace_active(active=True, elapsed_ms=0.0)
            grace_t0 = time.perf_counter()
            grace_deadline = grace_t0 + GRACE_WINDOW_S
            _trace("completion_grace_start", grace_s=GRACE_WINDOW_S)
        else:
            _trace(
                "completion_grace_skipped",
                reason="worker_not_alive",
                worker_alive=False,
            )

        if grace_started:
            def _grace_tick() -> None:
                set_completion_grace_active(
                    active=True,
                    elapsed_ms=(time.perf_counter() - grace_t0) * 1000.0,
                )

            result = _poll_until(
                worker,
                grace_deadline,
                allow_heuristic=False,
                reason="grace_wait",
                delayed_recovery=True,
                on_tick=_grace_tick,
            )
            if result is not None:
                _trace("completion_event_wait_end", phase="grace", ok=result.ok)
                return result

            set_completion_grace_active(active=False, elapsed_ms=GRACE_WINDOW_S * 1000.0)
            _trace(
                "completion_grace_end",
                worker_alive=worker.is_alive(),
                elapsed_ms_exact=round(_elapsed_ms(), 2),
            )

    worker.join(timeout=POLL_INTERVAL_S)
    _trace(
        "worker_thread_alive_after_join",
        alive=worker.is_alive(),
        elapsed_ms_exact=round(_elapsed_ms(), 2),
    )

    if worker.is_alive() and not state.snapshot().get("run_and_wait_returned"):
        post_grace_deadline = time.perf_counter() + POST_GRACE_RUNANDWAIT_S
        _trace("post_grace_runandwait_wait_start", wait_s=POST_GRACE_RUNANDWAIT_S)
        result = _poll_until(
            worker,
            post_grace_deadline,
            allow_heuristic=False,
            reason="post_grace_wait",
            delayed_recovery=True,
        )
        if result is not None:
            _trace("completion_event_wait_end", phase="post_grace", ok=result.ok)
            return result
        worker.join(timeout=POLL_INTERVAL_S)
        _trace(
            "post_grace_runandwait_wait_end",
            alive=worker.is_alive(),
            elapsed_ms_exact=round(_elapsed_ms(), 2),
        )

    snap = state.snapshot()
    if snap.get("error"):
        return _fail(str(snap["error"]), reason="post_grace:worker_error", worker=worker)

    if snap.get("run_and_wait_returned"):
        return _success(
            completion_hang=primary_timeout_warning,
            delayed_recovery=primary_timeout_warning,
            reason="post_grace:runAndWait_returned",
        )

    if worker.is_alive():
        result = _evaluate(
            worker,
            allow_heuristic=HEURISTIC_RECOVERY_ENABLED,
            reason="grace_expired",
            delayed_recovery=True,
        )
        if result is not None:
            _trace("completion_event_wait_end", phase="grace_heuristic", ok=result.ok)
            return result
        _trace("watchdog_timeout_triggered", worker_alive=True, hard_failure_pending=True)
        if engine is not None and not create_engine_on_worker:
            _dispose_engine_async(engine)
        fallback = _try_emergency_playback_fallback(text)
        if fallback is not None and fallback.ok:
            clear_completion_grace()
            end_speak_session()
            try:
                from voice.playback_metrics import record_playback_metrics

                record_playback_metrics(
                    audio_started=True,
                    playback_completed=True,
                    playback_duration_ms=_elapsed_ms(),
                    playback_timeout=True,
                    fallback_path=fallback.fallback_path,
                    worker_thread_id=int(state.snapshot().get("worker_thread_id") or 0),
                )
            except Exception:
                pass
            return DirectPlaybackResult(
                ok=True,
                playback_started=True,
                elapsed_ms=_elapsed_ms(),
                estimated_ms=estimated_ms,
                completion_hang=True,
                delayed_completion_recovered=True,
                fallback_path=fallback.fallback_path,
                error="",
            )
        return _fail(
            "runAndWait did not complete",
            reason="hard_grace_timeout",
            worker=worker,
        )

    clear_completion_grace()
    return _fail(
        "runAndWait worker exited without completion",
        reason="worker_exited_incomplete",
        worker=worker,
    )


log_completion_pipeline_startup()


def run_direct_tts_isolated_test(
    text: str = "Direct TTS test. One short audible sentence.",
    *,
    rate_raw: str = "",
    on_playback_start: Callable[[], None] | None = None,
) -> DirectPlaybackResult:
    """Minimal direct playback path — COM thread owns init/say/runAndWait."""
    from voice.pyttsx3_lifecycle import direct_speech_lock

    with direct_speech_lock():
        return run_and_wait_nonblocking(
            text=text,
            rate_raw=rate_raw,
            on_playback_start=on_playback_start,
            create_engine_on_worker=True,
        )
