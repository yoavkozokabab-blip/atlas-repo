"""pyttsx3 TTS fallback (offline SAPI) with optional sounddevice routing."""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from config import TTS_LANGUAGE, TTS_VOICE, TTS_VOLUME, TTS_WARN_INACTIVE_DEVICE
from core.logger import setup_logger
from voice.pyttsx3_completion import (
    COMPLETION_HANDLER,
    COMPLETION_PIPELINE_VERSION,
    run_and_wait_nonblocking,
)
from voice.tts_config import resolve_pyttsx_rate

logger = setup_logger("jarvis.voice.tts.pyttsx3")

_engine: object | None = None
_engine_lock = threading.Lock()
_inactive_device_warned = False


class Pyttsx3TTSError(Exception):
    """pyttsx3 engine failure."""


def _configure_engine(engine, rate_raw: str) -> None:
    try:
        engine.setProperty("rate", resolve_pyttsx_rate(rate_raw))
        engine.setProperty("volume", max(0.0, min(1.0, TTS_VOLUME)))
    except Exception as exc:
        logger.warning("Could not set pyttsx3 rate/volume: %s", exc)
    _select_voice(engine)


def _get_engine(rate_raw: str):
    global _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            import pyttsx3
        except ImportError as exc:
            raise Pyttsx3TTSError(
                "pyttsx3 is not installed. Run: pip install pyttsx3"
            ) from exc
        try:
            engine = pyttsx3.init()
        except Exception as exc:
            raise Pyttsx3TTSError(f"Could not initialize pyttsx3: {exc}") from exc
        _configure_engine(engine, rate_raw)
        _engine = engine
        return _engine


def _select_voice(engine) -> None:
    if not TTS_VOICE and not TTS_LANGUAGE:
        return
    try:
        voices = engine.getProperty("voices") or []
    except Exception:
        return
    target = (TTS_VOICE or "").lower()
    lang = (TTS_LANGUAGE or "").lower()
    for voice in voices:
        vid = (getattr(voice, "id", "") or "").lower()
        name = (getattr(voice, "name", "") or "").lower()
        langs = getattr(voice, "languages", []) or []
        lang_str = " ".join(str(x) for x in langs).lower()
        if target and (target in vid or target in name):
            engine.setProperty("voice", voice.id)
            return
        if lang and (lang in lang_str or lang in name or lang in vid):
            engine.setProperty("voice", voice.id)
            return


def _resolve_playback_device() -> int | None:
    from voice.windows_audio_routing import resolve_subprocess_playback_route

    route = resolve_subprocess_playback_route()
    return route.device_index


def uses_sounddevice_routing() -> bool:
    from voice.tts_playback_trace import must_use_direct_pyttsx3

    if must_use_direct_pyttsx3():
        return False
    return _resolve_playback_device() is not None


def _play_wav_on_device(path: Path, device: int | None) -> None:
    from scipy.io import wavfile
    import sounddevice as sd

    rate, data = wavfile.read(path)
    if data.ndim > 1:
        data = data[:, 0]
    samples = data.astype(np.float32) / max(1.0, float(np.max(np.abs(data))))
    sd.play(samples, int(rate), device=device)
    sd.wait()


def _import_numpy():
    import numpy as np

    return np


def _speak_via_sounddevice_wav(engine, text: str, device: int | None) -> None:
    np = _import_numpy()
    fd, name = tempfile.mkstemp(suffix=".wav", prefix="jarvis_tts_")
    os.close(fd)
    path = Path(name)
    try:
        engine.save_to_file(text, str(path))
        engine.runAndWait()
        if not path.is_file() or path.stat().st_size < 44:
            raise Pyttsx3TTSError("pyttsx3 produced no WAV output for routing")
        _play_wav_on_device(path, device)
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _maybe_warn_inactive_device() -> None:
    global _inactive_device_warned
    if _inactive_device_warned or not TTS_WARN_INACTIVE_DEVICE:
        return
    from voice.audio_devices import get_session_output_device, is_audible_route_verified
    from voice.windows_audio_routing import force_windows_default_output, resolve_subprocess_playback_route

    if get_session_output_device() is not None:
        return
    if is_audible_route_verified():
        return
    route = resolve_subprocess_playback_route()
    if route.device_index is not None or force_windows_default_output():
        return
    _inactive_device_warned = True
    msg = "Speech played to inactive audio device."
    logger.warning(msg)
    try:
        from ui.overlay_app import notify_overlay_error

        notify_overlay_error(msg)
    except Exception:
        pass


def _run_and_wait_with_watchdog(
    engine: object | None,
    *,
    text: str = "",
    rate_raw: str = "",
    on_playback_start: Callable[[], None] | None = None,
    create_engine_on_worker: bool = False,
):
    """Direct v2 grace-recovery completion pipeline (no legacy fallback)."""
    print(f"[TTS_DIRECT] using_completion_pipeline={COMPLETION_PIPELINE_VERSION}", flush=True)
    print(f"[TTS_DIRECT] completion_pipeline_source={COMPLETION_HANDLER}", flush=True)
    return run_and_wait_nonblocking(
        engine,
        text=text,
        rate_raw=rate_raw,
        on_playback_start=on_playback_start,
        create_engine_on_worker=create_engine_on_worker,
    )


def speak_pyttsx3_direct(
    text: str,
    *,
    rate_raw: str,
    on_playback_start: Callable[[], None] | None = None,
    record_user_success: bool = True,
) -> None:
    """
    Direct SAPI playback (same as standalone pyttsx3 test).
    Fresh pyttsx3.init() per request under global speech lock; no engine reuse.
    """
    from voice.playback_guard import should_play_audio
    from voice.pyttsx3_lifecycle import direct_speech_lock
    from voice.tts_playback_trace import (
        log_tts_debug,
        must_use_direct_pyttsx3,
        record_playback_failure,
        record_playback_finish,
        record_playback_start,
    )

    if not should_play_audio():
        log_tts_debug("playback_skipped_test_guard", engine="pyttsx3_direct")
        return

    print("[TTS_DIRECT] init", flush=True)
    print(f"[TTS_DIRECT] using_completion_pipeline={COMPLETION_PIPELINE_VERSION}", flush=True)
    print(f"[TTS_DIRECT] completion_pipeline_source={COMPLETION_HANDLER}", flush=True)
    record_playback_start(engine="pyttsx3_direct", device="sapi_default", path="direct_com_thread")
    t0 = __import__("time").perf_counter()
    try:
        with direct_speech_lock():
            print(f"[TTS_DIRECT] say text length {len(text)}", flush=True)
            log_tts_debug("pyttsx3_say_start", chars=len(text))
            result = _run_and_wait_with_watchdog(
                None,
                text=text,
                rate_raw=rate_raw,
                on_playback_start=on_playback_start,
                create_engine_on_worker=True,
            )
            if not result.ok:
                err = result.error or "pyttsx3 direct playback failed"
                if result.fallback_path:
                    err = f"{err} (fallback {result.fallback_path} also failed)"
                if "run loop already started" in err.lower():
                    err = f"{err} (abandoned hung engine; retry with fresh engine)"
                raise Pyttsx3TTSError(err)
            if result.fallback_path:
                print(f"[TTS_DIRECT] emergency fallback used: {result.fallback_path}", flush=True)
            if result.completion_hang:
                print(
                    f"[TTS_DIRECT] completion hang recovered ({result.elapsed_ms:.0f}ms "
                    f"est {result.estimated_ms:.0f}ms)",
                    flush=True,
                )
            if result.delayed_completion_recovered:
                print(
                    f"[TTS_DIRECT] delayed completion recovered ({result.elapsed_ms:.0f}ms)",
                    flush=True,
                )
        log_tts_debug("pyttsx3_say_finish")
        record_playback_finish(
            engine="pyttsx3_direct",
            ok=True,
            elapsed_ms=(__import__("time").perf_counter() - t0) * 1000.0,
        )
        print("[TTS_DIRECT] success", flush=True)
        try:
            from voice.audio_status import maybe_auto_verify_direct_speech_debug

            maybe_auto_verify_direct_speech_debug()
        except Exception:
            pass
        try:
            from voice.audio_status import record_direct_engine_completed

            record_direct_engine_completed(text_preview=text)
            if record_user_success:
                from voice.audio_status import record_direct_speech_success

                record_direct_speech_success(text_preview=text)
        except Exception:
            pass
        if must_use_direct_pyttsx3():
            try:
                from voice.audio_status import record_normal_speech_path

                record_normal_speech_path("pyttsx3_direct")
            except Exception:
                pass
    except Exception as exc:
        print("[TTS_DIRECT] failure", flush=True)
        record_playback_failure(exc, engine="pyttsx3_direct", path="direct", context="say")
        try:
            from voice.audio_status import record_normal_speech_failure

            record_normal_speech_failure(str(exc))
        except Exception:
            pass
        raise Pyttsx3TTSError(f"pyttsx3 direct playback failed: {exc}") from exc


def speak_pyttsx3(
    text: str,
    *,
    rate_raw: str,
    on_playback_start: Callable[[], None] | None = None,
) -> None:
    """Blocking pyttsx3 speech; routes via sounddevice when a device is selected."""
    from voice.playback_guard import should_play_audio
    from voice.tts_playback_trace import (
        is_tts_safe_mode,
        log_tts_debug,
        must_use_direct_pyttsx3,
        record_playback_failure,
        record_playback_finish,
        record_playback_start,
    )

    if not should_play_audio():
        log_tts_debug("playback_skipped_guard", engine="pyttsx3")
        return

    if is_tts_safe_mode() or must_use_direct_pyttsx3():
        return speak_pyttsx3_direct(text, rate_raw=rate_raw, on_playback_start=on_playback_start)

    engine = _get_engine(rate_raw)
    device = _resolve_playback_device()
    device_label = str(device) if device is not None else "sapi_default"
    path = "sounddevice_wav" if device is not None else "direct"
    record_playback_start(engine="pyttsx3", device=device_label, path=path)
    t0 = __import__("time").perf_counter()
    try:
        with _engine_lock:
            if device is not None:
                try:
                    _speak_via_sounddevice_wav(engine, text, device)
                except Exception as route_exc:
                    log_tts_debug(
                        "sounddevice_routing_failed_fallback_direct",
                        error=str(route_exc),
                    )
                    try:
                        from ui.overlay_app import notify_overlay_error

                        notify_overlay_error(
                            "Falling back to local voice engine"
                        )
                    except Exception:
                        pass
                    engine.say(text)
                    if on_playback_start is not None:
                        on_playback_start()
                    engine.runAndWait()
                    path = "direct_fallback"
            else:
                engine.say(text)
                if on_playback_start is not None:
                    on_playback_start()
                engine.runAndWait()
        _maybe_warn_inactive_device()
        record_playback_finish(
            engine="pyttsx3",
            ok=True,
            elapsed_ms=(__import__("time").perf_counter() - t0) * 1000.0,
        )
    except Exception as exc:
        record_playback_failure(exc, engine="pyttsx3", path=path, context="speak")
        raise Pyttsx3TTSError(f"pyttsx3 playback failed: {exc}") from exc


# Single function object for test 1, forced normal mode, and verified direct TTS.
NORMAL_DIRECT_SPEAKER = speak_pyttsx3_direct


def reset_pyttsx3_engine() -> None:
    global _engine, _inactive_device_warned
    with _engine_lock:
        if _engine is not None:
            try:
                _engine.stop()
            except Exception:
                pass
        _engine = None
        _inactive_device_warned = False
    try:
        from voice.pyttsx3_lifecycle import reset_pyttsx3_lifecycle_for_tests

        reset_pyttsx3_lifecycle_for_tests()
    except Exception:
        pass
    import gc

    gc.collect()
