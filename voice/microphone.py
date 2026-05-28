"""Push-to-talk microphone capture."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from config import (
    STT_DEBUG_MIC,
    STT_DEVICE,
    STT_RECORDING_MAX_SECONDS,
    STT_SAMPLE_RATE,
    STT_SILENCE_SECONDS,
    STT_SILENCE_THRESHOLD,
)
from voice.fast_voice import (
    effective_max_record_seconds,
    effective_wake_min_speech_seconds,
    effective_wake_min_total_seconds,
    effective_wake_post_speech_buffer_ms,
    effective_wake_silence_seconds,
    silence_stop_enabled,
    wake_early_stop_enabled,
)
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.mic")

CHUNK_SAMPLES = 1280  # ~80ms at 16 kHz


@dataclass
class CaptureStats:
    session_seconds: float = 0.0
    speech_seconds: float = 0.0
    silence_cutoff_seconds: float = 0.0


_last_capture_stats: CaptureStats | None = None


def get_last_capture_stats() -> CaptureStats | None:
    return _last_capture_stats


class MicrophoneError(Exception):
    """Raised when microphone hardware or drivers are unavailable."""


def check_microphone_available() -> None:
    """Verify that an input device exists; raise MicrophoneError if not."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise MicrophoneError(
            "sounddevice is not installed. Run: pip install sounddevice scipy"
        ) from exc

    try:
        devices = sd.query_devices()
        default_in = sd.default.device[0]
        if default_in is None or default_in < 0:
            inputs = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if not inputs:
                raise MicrophoneError("No microphone input devices detected.")
    except Exception as exc:
        raise MicrophoneError(f"Could not query audio devices: {exc}") from exc


def _resolve_device() -> int | None:
    if not STT_DEVICE:
        return None
    try:
        return int(STT_DEVICE)
    except ValueError:
        return None


def _record_stream(
    *,
    stop_event: threading.Event,
    sample_rate: int,
    device: int | None,
    max_seconds: float | None = None,
    silence_stop: bool = False,
    silence_seconds: float | None = None,
    silence_threshold: float | None = None,
    require_voice_before_silence_stop: bool = False,
    post_speech_buffer_ms: float = 0.0,
    min_speech_seconds: float = 0.0,
    min_total_seconds: float = 0.0,
    capture_stats: CaptureStats | None = None,
) -> np.ndarray:
    import sounddevice as sd

    chunks: list[np.ndarray] = []
    cap = max_seconds if max_seconds is not None else float(STT_RECORDING_MAX_SECONDS)
    sil_sec = silence_seconds if silence_seconds is not None else STT_SILENCE_SECONDS
    sil_thr = silence_threshold if silence_threshold is not None else STT_SILENCE_THRESHOLD
    last_voice = [time.monotonic()]
    voice_detected = [False]
    speech_seconds = [0.0]
    min_samples_before_silence = int(
        sample_rate * max(min_total_seconds, 0.35)
    )
    post_buffer_sec = max(0.0, post_speech_buffer_ms / 1000.0)
    silence_tail_deadline: list[float | None] = [None]
    chunk_seconds = CHUNK_SAMPLES / float(sample_rate)

    energy_logged = 0

    def callback(indata, _frames, _time, status) -> None:
        nonlocal energy_logged
        if status:
            logger.warning("Audio status: %s", status)
        chunks.append(indata.copy())
        rms = float(np.sqrt(np.mean(indata.astype(np.float64) ** 2)))
        if rms >= sil_thr:
            voice_detected[0] = True
            last_voice[0] = time.monotonic()
            speech_seconds[0] += chunk_seconds
        if STT_DEBUG_MIC and energy_logged < 20:
            peak = float(np.max(np.abs(indata)))
            logger.debug("Mic energy rms=%.5f peak=%.5f", rms, peak)
            energy_logged += 1

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=CHUNK_SAMPLES,
        callback=callback,
        device=device,
    ):
        started = time.monotonic()
        while not stop_event.is_set():
            elapsed = time.monotonic() - started
            if elapsed >= cap:
                logger.info("Max recording length (%.1fs) reached.", cap)
                break
            now = time.monotonic()
            sample_count = sum(c.shape[0] for c in chunks)
            idle = now - last_voice[0]
            can_stop = _silence_stop_ready(
                silence_stop=silence_stop,
                has_chunks=bool(chunks),
                sample_count=sample_count,
                min_samples_before_silence=min_samples_before_silence,
                now=now,
                last_voice_at=last_voice[0],
                silence_seconds=sil_sec,
                require_voice_before_silence_stop=require_voice_before_silence_stop,
                voice_detected=voice_detected[0],
            )
            if can_stop and min_speech_seconds > 0 and speech_seconds[0] < min_speech_seconds:
                can_stop = False
            if can_stop:
                if silence_tail_deadline[0] is None:
                    silence_tail_deadline[0] = now + post_buffer_sec
                    logger.info(
                        "Speech pause detected; tail buffer %.0fms",
                        post_speech_buffer_ms,
                    )
                elif post_buffer_sec <= 0 or now >= silence_tail_deadline[0]:
                    logger.info("Silence stop (%.1fs idle + tail).", sil_sec)
                    break
            else:
                silence_tail_deadline[0] = None
            time.sleep(0.05)

    if not chunks:
        if capture_stats is not None:
            capture_stats.session_seconds = 0.0
        return np.array([], dtype=np.float32)
    audio = np.concatenate(chunks, axis=0)
    if capture_stats is not None:
        capture_stats.session_seconds = audio.shape[0] / float(sample_rate)
        capture_stats.speech_seconds = min(
            capture_stats.session_seconds, speech_seconds[0]
        )
        capture_stats.silence_cutoff_seconds = max(
            0.0, capture_stats.session_seconds - capture_stats.speech_seconds
        )
    return audio


def _silence_stop_ready(
    *,
    silence_stop: bool,
    has_chunks: bool,
    sample_count: int,
    min_samples_before_silence: int,
    now: float,
    last_voice_at: float,
    silence_seconds: float,
    require_voice_before_silence_stop: bool,
    voice_detected: bool,
) -> bool:
    if not silence_stop or not has_chunks:
        return False
    if sample_count < min_samples_before_silence:
        return False
    if require_voice_before_silence_stop and not voice_detected:
        return False
    return (now - last_voice_at) >= silence_seconds


def _save_wav(audio: np.ndarray, sample_rate: int) -> Path:
    from scipy.io import wavfile

    if audio.size == 0:
        raise MicrophoneError("No audio captured.")

    audio = np.squeeze(audio)
    if audio.ndim > 1:
        audio = audio[:, 0]
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    if STT_DEBUG_MIC:
        logger.debug("Recorded audio peak=%.4f rms=%.5f samples=%s", peak, rms, audio.size)
    if peak > 1e-6:
        audio = audio / max(peak, 1.0)

    pcm = (audio * 32767).astype(np.int16)
    fd, name = tempfile.mkstemp(suffix=".wav", prefix="jarvis_")
    os.close(fd)
    path = Path(name)
    wavfile.write(path, sample_rate, pcm)
    return path


def record_until_enter(
    *,
    sample_rate: int | None = None,
    max_seconds: int | None = None,
) -> Path:
    """
    Press Enter to start, Enter again to stop.
    Returns path to a temporary WAV file.
    """
    del max_seconds  # uses config STT_RECORDING_MAX_SECONDS via _record_stream
    check_microphone_available()
    rate = sample_rate or STT_SAMPLE_RATE
    device = _resolve_device()

    print("Press Enter to start recording...")
    try:
        input()
    except EOFError as exc:
        raise MicrophoneError("stdin closed; cannot start recording.") from exc

    print("Recording... Press Enter to stop.")
    stop_event = threading.Event()

    def wait_for_stop() -> None:
        try:
            input()
        except EOFError:
            pass
        finally:
            stop_event.set()

    threading.Thread(target=wait_for_stop, daemon=True).start()

    use_silence = silence_stop_enabled()
    try:
        audio = _record_stream(
            stop_event=stop_event,
            sample_rate=rate,
            device=device,
            max_seconds=effective_max_record_seconds(wake_session=False),
            silence_stop=use_silence,
            require_voice_before_silence_stop=use_silence,
        )
        return _save_wav(audio, rate)
    except Exception as exc:
        if isinstance(exc, MicrophoneError):
            raise
        raise MicrophoneError(f"Recording failed: {exc}") from exc


def _wait_hotkey(key: str) -> None:
    """Wait for a single key press (Windows msvcrt)."""
    if sys.platform != "win32":
        print(f"Press Enter (hotkey '{key}' is Windows-only)...")
        input()
        return

    import msvcrt

    print(f"Press [{key}] when ready...")
    while True:
        ch = msvcrt.getch()
        if isinstance(ch, bytes):
            try:
                ch = ch.decode("utf-8", errors="ignore")
            except Exception:
                ch = chr(ch[0]) if ch else ""
        if ch == key or (key == " " and ch == " "):
            return


def record_for_seconds(
    seconds: float,
    *,
    sample_rate: int | None = None,
    wake_session: bool = True,
) -> Path:
    """
    Record for a fixed duration (wake-word post-detection session).
    Returns a temporary WAV path — caller must delete via ensure_no_audio_persistence.
    """
    check_microphone_available()
    rate = sample_rate or STT_SAMPLE_RATE
    device = _resolve_device()
    stop_event = threading.Event()
    cap = effective_max_record_seconds(wake_session=wake_session)
    duration = min(float(seconds), cap)

    def timer_stop() -> None:
        time.sleep(max(0.5, duration))
        stop_event.set()

    threading.Thread(target=timer_stop, daemon=True).start()
    # Wake early-stop waits for speech first, then stops after the speech tail.
    use_silence = wake_early_stop_enabled() if wake_session else silence_stop_enabled()
    sil_sec = effective_wake_silence_seconds() if wake_session else None
    stats = CaptureStats()
    global _last_capture_stats
    _last_capture_stats = stats
    try:
        audio = _record_stream(
            stop_event=stop_event,
            sample_rate=rate,
            device=device,
            max_seconds=duration,
            silence_stop=use_silence,
            silence_seconds=sil_sec,
            require_voice_before_silence_stop=wake_session or silence_stop_enabled(),
            post_speech_buffer_ms=effective_wake_post_speech_buffer_ms()
            if wake_session
            else 0.0,
            min_speech_seconds=effective_wake_min_speech_seconds()
            if wake_session
            else 0.0,
            min_total_seconds=effective_wake_min_total_seconds()
            if wake_session
            else 0.0,
            capture_stats=stats if wake_session else None,
        )
        return _save_wav(audio, rate)
    except Exception as exc:
        if isinstance(exc, MicrophoneError):
            raise
        raise MicrophoneError(f"Recording failed: {exc}") from exc


def record_until_hotkey(
    key: str = " ",
    *,
    sample_rate: int | None = None,
) -> Path:
    """
    Optional mode: press SPACE (or configured key) to start, again to stop.
    Falls back to Enter on non-Windows platforms.
    """
    check_microphone_available()
    rate = sample_rate or STT_SAMPLE_RATE
    device = _resolve_device()

    _wait_hotkey(key)
    print("Recording... Press the same key again to stop.")
    stop_event = threading.Event()

    def wait_hotkey_stop() -> None:
        if sys.platform == "win32":
            import msvcrt

            while not stop_event.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    try:
                        decoded = ch.decode("utf-8", errors="ignore") if isinstance(ch, bytes) else ch
                    except Exception:
                        decoded = ""
                    if decoded == key or (key == " " and decoded == " "):
                        stop_event.set()
                        return
                time.sleep(0.05)
        else:
            input()
            stop_event.set()

    threading.Thread(target=wait_hotkey_stop, daemon=True).start()

    try:
        audio = _record_stream(
            stop_event=stop_event,
            sample_rate=rate,
            device=device,
            max_seconds=effective_max_record_seconds(wake_session=False),
        )
        return _save_wav(audio, rate)
    except Exception as exc:
        if isinstance(exc, MicrophoneError):
            raise
        raise MicrophoneError(f"Recording failed: {exc}") from exc
