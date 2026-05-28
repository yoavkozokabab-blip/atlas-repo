"""Startup TTS self-test (optional, local only)."""

from __future__ import annotations

from core.logger import setup_logger
from voice.audio_status import probe_output_device, set_startup_self_test_result
from voice.tts import TTSError, TTSService
from voice.tts_config import normalize_tts_engine

logger = setup_logger("jarvis.voice.tts_startup")


def run_tts_startup_self_test(*, enabled: bool) -> None:
    """
    Synthesize a short phrase when TTS is enabled to verify playback path.
    Logs engine/device; never aborts startup on failure.
    """
    if not enabled:
        set_startup_self_test_result("skipped (TTS disabled)")
        return
    try:
        from config import TTS_ENGINE, TTS_STARTUP_SELF_TEST

        if not TTS_STARTUP_SELF_TEST:
            set_startup_self_test_result("skipped (TTS_STARTUP_SELF_TEST=false)")
            return
    except Exception:
        set_startup_self_test_result("skipped (config)")
        return

    from voice.audio_devices import load_persisted_routing, log_startup_audio_devices
    from voice.audio_verified import has_verified_audio_backend

    load_persisted_routing()
    log_startup_audio_devices()
    if not has_verified_audio_backend():
        set_startup_self_test_result("skipped (no verified audio backend)")
        logger.info("TTS startup self-test skipped: verified backend required")
        return
    try:
        from config import VOICE_STACK_STARTUP_CALIBRATION
        from voice.tts_playback_trace import is_tts_safe_mode

        if VOICE_STACK_STARTUP_CALIBRATION and not is_tts_safe_mode():
            from voice.voice_stack_store import apply_voice_profile_to_runtime

            prof = apply_voice_profile_to_runtime()
            logger.info(
                "Voice stack profile applied: engine=%s voice=%s emotion=%s",
                prof.engine,
                prof.voice,
                prof.emotion,
            )
    except Exception as exc:
        logger.debug("Voice stack startup apply skipped: %s", exc)
    engine = normalize_tts_engine(TTS_ENGINE)
    device = probe_output_device()
    phrase = "JARVIS online."
    try:
        ok = TTSService(enabled=True).speak(phrase)
        if ok:
            try:
                from voice.audio_status import set_selected_verified_audio_backend

                set_selected_verified_audio_backend("verified_local_pyttsx3")
            except Exception:
                pass
            msg = f"ok engine={engine} device={device}"
            set_startup_self_test_result(msg)
            logger.info("TTS startup self-test: %s", msg)
            print(f"[INFO] TTS startup self-test: {msg}", flush=True)
        else:
            set_startup_self_test_result(f"no audio engine={engine}")
            print("[WARNING] TTS startup self-test: speak returned false", flush=True)
    except TTSError as exc:
        set_startup_self_test_result(f"failed: {exc}")
        logger.warning("TTS startup self-test failed: %s", exc)
        print(f"[WARNING] TTS startup self-test failed: {exc}", flush=True)
        try:
            from ui.overlay_app import notify_overlay_error

            notify_overlay_error(f"TTS startup failed: {exc}")
        except Exception:
            pass
