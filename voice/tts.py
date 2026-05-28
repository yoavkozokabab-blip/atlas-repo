"""Optional text-to-speech output (summary only, non-critical)."""

from __future__ import annotations

import re
import threading
import time

import config as cfg
from core.logger import setup_logger
from voice.tts_config import normalize_tts_engine
from voice.tts_status import record_tts_async_failure, record_tts_run

logger = setup_logger("jarvis.voice.tts")


def _warn_tts_console(message: str) -> None:
    print(f"[WARNING] TTS: {message}", flush=True)


class TTSError(Exception):
    """Raised when TTS engine fails; callers should warn, not abort commands."""


_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(api[_-]?key|token|password|secret|bearer)\s*[=:]\s*\S+", re.I),
    re.compile(r"(OPENAI|TELEGRAM|AWS|AZURE)[_A-Z]*\s*[=:]\s*\S+", re.I),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
]
_ENV_LINE = re.compile(r"^[A-Z][A-Z0-9_]{2,}=[^\s]+$", re.MULTILINE)


def resolve_tts_enabled(cli_flag: bool | None = None) -> bool:
    """CLI --speak / --no-speak overrides .env TTS_ENABLED."""
    if cli_flag is True:
        return True
    if cli_flag is False:
        return False
    return cfg.TTS_ENABLED


def sanitize_for_speech(text: str) -> str:
    """Prepare summary text for TTS: strip markup, redact secrets, truncate."""
    if not text or not str(text).strip():
        return ""

    out = str(text)
    out = re.sub(r"\[/?[^\]]+\]", "", out)
    out = out.replace("**", "").replace("__", "")

    for pat in _SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)

    lines = []
    for line in out.splitlines():
        stripped = line.strip()
        if _ENV_LINE.match(stripped):
            continue
        if re.search(r"(password|secret|token|apikey)\s*=", stripped, re.I):
            continue
        lines.append(line)
    out = "\n".join(lines).strip()

    if len(out) > cfg.TTS_MAX_CHARS:
        out = out[: cfg.TTS_MAX_CHARS - 3].rstrip() + "..."
    return out


def first_sentence_for_speech(text: str, *, max_chars: int = 160) -> str:
    """First sentence or line for fast TTS (Phase 37e); full summary stays in UI."""
    safe = sanitize_for_speech(text)
    if not safe:
        return ""
    for sep in (". ", ".\n", "\n", "? ", "! "):
        if sep in safe:
            part = safe.split(sep, 1)[0].strip() + sep.strip()
            if part:
                return part[:max_chars]
    return safe[:max_chars]


class TTSService:
    """Speaks command summaries via edge-tts (premium) with pyttsx3 fallback."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = cfg.TTS_ENABLED if enabled is None else enabled
        self._speak_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._last_timeout_monotonic = 0.0

    def speak(self, text: str) -> bool:
        """
        Speak sanitized text. Returns True if spoken, False if disabled/empty.
        Raises TTSError on total failure (both engines).
        """
        if not self.enabled:
            return False

        safe = sanitize_for_speech(text)
        if not safe:
            return False
        try:
            from voice.tts_output_policy import evaluate_tts_output, log_tts_output_decision, notify_overlay_tts_blocked

            decision = evaluate_tts_output(speak_enabled=self.enabled, voice_path="tts.speak")
            log_tts_output_decision(decision)
            if not decision.allowed:
                logger.info("TTS deferred: %s", decision.reason)
                notify_overlay_tts_blocked(decision)
                return False
        except Exception:
            try:
                from voice.tool_first_mode import can_attempt_tts, is_tool_first_mode

                if is_tool_first_mode() and not can_attempt_tts():
                    logger.debug("TTS deferred: tool-first mode without verified backend")
                    return False
            except Exception:
                pass
        if self._last_timeout_monotonic and (
            time.monotonic() - self._last_timeout_monotonic
        ) < max(1.0, cfg.TTS_TIMEOUT_SECONDS):
            raise TTSError("TTS recovery cooldown active after a timeout.")

        try:
            from voice.audio_verified import block_unverified_speech_with_warning
            from voice.tts_playback_trace import is_tts_safe_mode

            if is_tts_safe_mode():
                if not block_unverified_speech_with_warning():
                    return False
                return self._speak_with_timeout(safe)
        except Exception:
            pass

        try:
            from voice.tts_backend import normal_speech_must_not_use_edge_tts
            from voice.tts_playback_trace import is_tts_safe_mode

            if is_tts_safe_mode() or normal_speech_must_not_use_edge_tts():
                return self._speak_with_timeout(safe)
        except Exception:
            pass

        if cfg.TTS_ASYNC:
            self.speak_async(safe)
            return True  # queued; failures recorded via tts_status + console warning

        return self._speak_with_timeout(safe)

    def _notify_tts_started(self) -> None:
        try:
            from voice.audio_verified import may_show_speaking_overlay

            if not may_show_speaking_overlay():
                return
        except Exception:
            return
        try:
            from voice.tts_watchdog import begin_speak_session

            begin_speak_session()
        except Exception:
            pass
        try:
            from conversation.semantic_stream.engine import on_jarvis_speaking_start

            on_jarvis_speaking_start()
        except Exception:
            pass
        try:
            from ui.overlay_app import notify_overlay_tts_started

            notify_overlay_tts_started()
        except Exception:
            pass
        try:
            from voice.tts_output_policy import log_speech_synthesis_started, notify_overlay_speaking

            notify_overlay_speaking(streaming=False)
            log_speech_synthesis_started(voice_path="tts.speak")
        except Exception:
            pass

    def _notify_tts_finished(self) -> None:
        try:
            from voice.tts_watchdog import end_speak_session

            end_speak_session()
        except Exception:
            pass
        try:
            from conversation.semantic_stream.engine import on_jarvis_speaking_end

            on_jarvis_speaking_end()
        except Exception:
            pass
        try:
            from ui.overlay_app import get_overlay_controller, notify_overlay_tts_finished
            from ui.overlay_state import OverlayPhase

            ctrl = get_overlay_controller()
            if ctrl._state.snapshot().phase == OverlayPhase.ERROR:
                return
            notify_overlay_tts_finished()
        except Exception:
            pass

    def _overlay_tts_warning(self, message: str) -> None:
        try:
            from ui.overlay_app import notify_overlay_error

            notify_overlay_error(f"TTS: {message}"[:200])
        except Exception:
            pass

    def _record_success(self, provider: str, text: str) -> None:
        try:
            from voice.audio_status import (
                record_normal_speech_success,
                record_tts_success,
                set_fallback_active,
                user_confirmed_direct_audio,
            )

            set_fallback_active("fallback" in provider)
            record_normal_speech_success(text_preview=text, path=provider)
            if provider in ("subprocess_pyttsx3", "shell_subprocess_pyttsx3"):
                record_tts_success(provider=provider, text_preview=text)
            elif user_confirmed_direct_audio():
                record_tts_success(provider=provider, text_preview=text)
        except Exception:
            pass

    def _speak_blocking_subprocess(self, safe: str) -> bool:
        from voice.tts_playback_trace import log_tts_debug
        from voice.tts_subprocess import speak_subprocess_pyttsx3

        log_tts_debug("tts_service_subprocess_path")
        result = None
        try:
            with self._speak_lock:
                result = speak_subprocess_pyttsx3(
                    safe,
                    on_playback_start=self._notify_tts_started,
                )
        finally:
            if result is not None and result.timed_out:
                try:
                    from voice.tts_watchdog import kill_stuck_speech

                    kill_stuck_speech(
                        (result.stderr or "").strip() or "subprocess timeout",
                        from_watchdog=True,
                    )
                except Exception:
                    self._notify_tts_finished()
            else:
                self._notify_tts_finished()
        assert result is not None
        if not result.ok:
            err = (result.stderr or "").strip() or f"exit {result.exit_code}"
            if result.timed_out:
                err = f"timeout: {err}"
            record_tts_run(provider="subprocess_pyttsx3", error=err)
            try:
                from voice.audio_status import record_normal_speech_failure

                record_normal_speech_failure(err)
            except Exception:
                pass
            raise TTSError(f"Subprocess TTS failed: {err}")
        from voice.audio_status import get_selected_verified_audio_backend

        provider = get_selected_verified_audio_backend() or "subprocess_pyttsx3"
        record_tts_run(provider=provider)
        try:
            from voice.audio_status import record_normal_speech_path

            record_normal_speech_path(provider)
        except Exception:
            pass
        self._record_success(provider, safe)
        return True

    def _speak_blocking_direct(self, safe: str, *, force: bool = False) -> bool:
        from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER, Pyttsx3TTSError
        from voice.tts_playback_trace import log_tts_debug, must_use_direct_pyttsx3

        if not force and not must_use_direct_pyttsx3():
            return False

        log_tts_debug("tts_service_direct_path")
        try:
            with self._speak_lock:
                NORMAL_DIRECT_SPEAKER(
                    safe,
                    rate_raw=cfg.TTS_RATE_RAW,
                    on_playback_start=self._notify_tts_started,
                    record_user_success=False,
                )
            record_tts_run(provider="pyttsx3_direct")
            try:
                from voice.audio_status import (
                    record_normal_speech_path,
                    warn_stable_path_mismatch_if_needed,
                )

                record_normal_speech_path("pyttsx3_direct")
                warn_stable_path_mismatch_if_needed()
            except Exception:
                pass
            try:
                from voice.audio_status import user_confirmed_direct_audio

                if user_confirmed_direct_audio():
                    self._record_success("pyttsx3_direct", safe)
            except Exception:
                pass
            return True
        except Pyttsx3TTSError as exc:
            try:
                from voice.audio_status import record_normal_speech_failure

                record_normal_speech_failure(str(exc))
            except Exception:
                pass
            record_tts_run(provider="pyttsx3_direct", error=str(exc))
            msg = f"TTS failed: {exc}"
            self._overlay_tts_warning(msg)
            raise TTSError(msg) from exc
        finally:
            self._notify_tts_finished()

    def _speak_blocking(self, safe: str) -> bool:
        from voice.audio_verified import block_unverified_speech_with_warning
        from voice.tts_backend import (
            must_use_verified_backend_for_normal_speech,
            normal_speech_must_not_use_edge_tts,
            prefer_direct_pyttsx3,
            prefer_subprocess_pyttsx3,
        )
        from voice.tts_playback_trace import is_tts_safe_mode, must_use_direct_pyttsx3

        if not block_unverified_speech_with_warning():
            return False

        if must_use_verified_backend_for_normal_speech() or is_tts_safe_mode():
            if prefer_direct_pyttsx3() or must_use_direct_pyttsx3():
                return self._speak_blocking_direct(safe, force=True)
            if prefer_subprocess_pyttsx3():
                return self._speak_blocking_subprocess(safe)
            if is_tts_safe_mode():
                return False

        if normal_speech_must_not_use_edge_tts():
            return False

        self._notify_tts_started()
        try:
            with self._speak_lock:
                try:
                    from voice.realtime_tts import is_realtime_tts_enabled, speak_realtime

                    if is_realtime_tts_enabled():
                        emotion = getattr(cfg, "REALTIME_TTS_EMOTION", "neutral")
                        provider = speak_realtime(
                            safe,
                            voice=cfg.TTS_VOICE,
                            rate_raw=cfg.TTS_RATE_RAW,
                            emotion=emotion or "neutral",
                        )
                        if provider:
                            record_tts_run(provider=provider)
                            self._record_success(provider, safe)
                            return True
                except Exception as exc:
                    logger.warning("Realtime TTS path failed, legacy fallback: %s", exc)

                engine = normalize_tts_engine(cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE)
                use_stack = (
                    getattr(cfg, "TTS_STREAMING_ENABLED", True)
                    and engine == "edge_tts"
                    and not normal_speech_must_not_use_edge_tts()
                )
                if use_stack:
                    try:
                        from voice.speech_controller import speak_text

                        provider = speak_text(safe)
                        if provider:
                            record_tts_run(provider=provider)
                            self._record_success(provider, safe)
                            return True
                    except Exception as exc:
                        logger.warning("Voice stack speak failed, legacy fallback: %s", exc)
                        try:
                            from voice.tts_playback_trace import record_playback_failure

                            record_playback_failure(
                                exc, engine="edge_tts", path="speech_controller"
                            )
                        except Exception:
                            pass
                        try:
                            from ui.overlay_app import notify_overlay_error

                            notify_overlay_error("Falling back to local voice engine")
                        except Exception:
                            pass
                return self._speak_blocking_legacy(safe)
        finally:
            self._notify_tts_finished()

    def _speak_blocking_legacy(self, safe: str) -> bool:
        from voice.tts_backend import normal_speech_must_not_use_edge_tts

        if normal_speech_must_not_use_edge_tts():
            return False
        engine = normalize_tts_engine(cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE)
        if engine == "edge_tts":
            try:
                self._speak_edge(safe)
                record_tts_run(provider="edge_tts")
                self._record_success("edge_tts", safe)
                return True
            except Exception as exc:
                logger.warning("edge-tts failed, falling back to pyttsx3: %s", exc)
                record_tts_run(provider="edge_tts", error=str(exc))
                _warn_tts_console(f"edge-tts failed: {exc}; trying pyttsx3")
                try:
                    self._speak_pyttsx3(safe)
                    record_tts_run(provider="pyttsx3_fallback")
                    self._record_success("pyttsx3_fallback", safe)
                    return True
                except Exception as fb_exc:
                    record_tts_run(provider="pyttsx3_fallback", error=str(fb_exc))
                    msg = f"TTS failed (edge-tts: {exc}; pyttsx3: {fb_exc})"
                    self._overlay_tts_warning(msg)
                    raise TTSError(msg) from fb_exc
        try:
            self._speak_pyttsx3(safe)
            record_tts_run(provider="pyttsx3")
            self._record_success("pyttsx3", safe)
            return True
        except Exception as exc:
            record_tts_run(provider="pyttsx3", error=str(exc))
            msg = f"TTS failed: {exc}"
            self._overlay_tts_warning(msg)
            raise TTSError(msg) from exc

    def _speak_with_timeout(self, safe: str) -> bool:
        from services.runtime_monitor import (
            OperationTimeoutError,
            get_runtime_monitor,
            run_with_timeout,
        )
        from voice.tts_watchdog import get_speak_timeout_seconds, set_pending_speak_timeout

        timeout = get_speak_timeout_seconds(safe, rate_raw=cfg.TTS_RATE_RAW)
        set_pending_speak_timeout(timeout)
        t0 = time.perf_counter()
        try:
            ok = run_with_timeout(
                "tts.speak",
                timeout,
                self._speak_blocking,
                safe,
                detail=safe[:120],
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            try:
                from services.observability import get_observability

                obs = get_observability()
                obs.record_latency("tts.speak", elapsed_ms, chars=len(safe))
                obs.profile_stage("voice", "tts", elapsed_ms, chars=len(safe))
            except Exception:
                pass
            return ok
        except OperationTimeoutError as exc:
            if self._recover_completion_hang_timeout(safe, exc):
                return True
            self._last_timeout_monotonic = time.monotonic()
            msg = f"TTS timeout after {timeout:.1f}s; engine reset requested."
            monitor = get_runtime_monitor()
            try:
                self.reset_engine()
                monitor.record_recovery(
                    "tts",
                    "reset_engine",
                    reason=str(exc),
                    ok=True,
                )
            except Exception as reset_exc:
                monitor.record_recovery(
                    "tts",
                    "reset_engine",
                    reason=str(exc),
                    ok=False,
                    detail=str(reset_exc),
                )
            self._notify_tts_finished()
            self._overlay_tts_warning(msg)
            try:
                from services.observability import get_observability

                get_observability().record_failure(
                    component="tts",
                    error=exc,
                    context={"timeout_seconds": timeout, "chars": len(safe)},
                )
            except Exception:
                pass
            raise TTSError(msg) from exc
        except Exception as exc:
            try:
                from services.observability import get_observability

                get_observability().record_failure(
                    component="tts",
                    error=exc,
                    context={"chars": len(safe)},
                )
            except Exception:
                pass
            raise

    def _recover_completion_hang_timeout(self, safe: str, exc: OperationTimeoutError) -> bool:
        """Treat audible playback as success when COM completion never returns."""
        from services.runtime_monitor import get_runtime_monitor
        from voice.audio_status import playback_audible_confirmed, recent_completion_hang_success
        from voice.tts_watchdog import get_speak_elapsed_ms

        elapsed = get_speak_elapsed_ms()
        hang_success = recent_completion_hang_success(within_seconds=20.0)
        heuristic_ok = (
            playback_audible_confirmed()
            and elapsed is not None
            and elapsed >= 300.0
        )
        if not hang_success and not heuristic_ok:
            return False

        monitor = get_runtime_monitor()
        monitor.retract_last_timeout("tts.speak")
        monitor.record_recovery(
            "tts",
            "completion_hang",
            reason=str(exc),
            ok=True,
            detail=f"chars={len(safe)} elapsed_ms={elapsed}",
        )
        try:
            self.reset_engine()
        except Exception:
            pass
        self._notify_tts_finished()
        try:
            from voice.audio_status import record_normal_speech_path

            record_normal_speech_path("pyttsx3_direct")
        except Exception:
            pass
        try:
            if playback_audible_confirmed():
                self._record_success("pyttsx3_direct", safe)
        except Exception:
            pass
        logger.info(
            "TTS completion hang recovered (elapsed_ms=%s hang_success=%s)",
            elapsed,
            hang_success,
        )
        return True

    def _speak_edge(self, safe: str) -> None:
        from voice.tts_edge import EdgeTTSError, speak_edge_tts

        voice = cfg.TTS_VOICE or "en-US-GuyNeural"
        speak_edge_tts(safe, voice=voice, rate_raw=cfg.TTS_RATE_RAW)

    def _speak_pyttsx3(self, safe: str, *, on_playback_start=None) -> None:
        from voice.tts_playback_trace import must_use_direct_pyttsx3
        from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER, Pyttsx3TTSError, speak_pyttsx3

        try:
            if must_use_direct_pyttsx3():
                NORMAL_DIRECT_SPEAKER(
                    safe,
                    rate_raw=cfg.TTS_RATE_RAW,
                    on_playback_start=on_playback_start,
                    record_user_success=False,
                )
                try:
                    from voice.audio_status import record_normal_speech_path

                    record_normal_speech_path("pyttsx3_direct")
                except Exception:
                    pass
            else:
                speak_pyttsx3(
                    safe,
                    rate_raw=cfg.TTS_RATE_RAW,
                    on_playback_start=on_playback_start,
                )
        except Pyttsx3TTSError as exc:
            raise TTSError(str(exc)) from exc

    def speak_async(self, text: str) -> None:
        """Queue TTS on a worker thread so wake/listen is not blocked."""
        if not self.enabled:
            return
        try:
            from voice.tts_playback_trace import is_tts_safe_mode

            if is_tts_safe_mode():
                self._speak_with_timeout(sanitize_for_speech(text))
                return
        except Exception:
            pass
        safe = sanitize_for_speech(text)
        if not safe:
            return
        if self._last_timeout_monotonic and (
            time.monotonic() - self._last_timeout_monotonic
        ) < max(1.0, cfg.TTS_TIMEOUT_SECONDS):
            msg = "TTS recovery cooldown active after a timeout; skipped speech."
            logger.warning(msg)
            record_tts_async_failure(
                msg,
                provider=normalize_tts_engine(cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE),
            )
            self._overlay_tts_warning(msg)
            return
        if self._worker and self._worker.is_alive():
            provider = normalize_tts_engine(cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE)
            msg = "Previous TTS worker is still running; skipped overlapping request."
            logger.warning(msg)
            record_tts_async_failure(msg, provider=provider)
            self._overlay_tts_warning(msg)
            try:
                from services.runtime_monitor import get_runtime_monitor

                get_runtime_monitor().record_recovery(
                    "tts",
                    "skip_overlapping_request",
                    reason="tts_worker_alive",
                    ok=True,
                )
            except Exception:
                pass
            return

        def _run() -> None:
            t0 = time.perf_counter()
            provider = normalize_tts_engine(cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE)
            try:
                self._speak_with_timeout(safe)
            except TTSError as exc:
                msg = str(exc)
                logger.warning("Async TTS failed: %s; retrying sync", msg)
                try:
                    if self._speak_blocking(safe):
                        return
                except TTSError as retry_exc:
                    msg = f"{msg}; sync retry: {retry_exc}"
                except Exception as retry_exc:
                    msg = f"{msg}; sync retry: {retry_exc}"
                record_tts_async_failure(msg, provider=provider)
                _warn_tts_console(msg)
                print(f"[TTS ERROR] {msg}", flush=True)
                self._overlay_tts_warning(msg)
                try:
                    from voice.latency_tracker import mark_tts_failed

                    mark_tts_failed(msg)
                except Exception:
                    pass
            except Exception as exc:
                msg = str(exc)
                logger.warning("Async TTS failed (unexpected): %s", msg)
                record_tts_async_failure(msg, provider=provider)
                _warn_tts_console(msg)
                print(f"[TTS ERROR] {msg}", flush=True)
                try:
                    from voice.tts_playback_trace import record_playback_failure

                    record_playback_failure(exc, engine=provider, path="async")
                except Exception:
                    pass
                try:
                    from voice.latency_tracker import mark_tts_failed

                    mark_tts_failed(msg)
                except Exception:
                    pass
            else:
                try:
                    from voice.latency_tracker import set_tts_ms

                    set_tts_ms((time.perf_counter() - t0) * 1000.0)
                except Exception:
                    pass

        self._worker = threading.Thread(target=_run, name="jarvis-tts", daemon=True)
        self._worker.start()

    def reset_engine(self) -> None:
        """Clear cached engines (for tests)."""
        from voice.tts_pyttsx3 import reset_pyttsx3_engine

        reset_pyttsx3_engine()

    def shutdown_worker(self, *, join_timeout: float = 1.5) -> None:
        """Join async TTS worker if still running (pytest cleanup)."""
        try:
            from voice.streaming_player import request_stop_speaking

            request_stop_speaking()
        except Exception:
            pass
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=max(0.05, join_timeout))
        self._worker = None


def shutdown_tts_service(*, join_timeout: float = 1.5) -> None:
    """Stop any in-flight TTS workers (best-effort)."""
    try:
        from voice.streaming_player import request_stop_speaking

        request_stop_speaking()
    except Exception:
        pass
    deadline = time.monotonic() + join_timeout
    for thread in threading.enumerate():
        if thread.name != "jarvis-tts" or not thread.is_alive():
            continue
        remaining = max(0.05, deadline - time.monotonic())
        thread.join(timeout=remaining)
