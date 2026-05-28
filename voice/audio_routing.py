"""Audio routing tests and session output selection (no persistent OS changes)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from core.logger import setup_logger
from voice.audio_devices import (
    format_audio_devices_report,
    get_session_output_device,
    list_playback_devices,
    set_session_output_device,
)
from voice.tts import TTSError, TTSService

logger = setup_logger("jarvis.voice.audio_routing")

_CYCLE_INDEX = 0


@dataclass
class RoutingTestResult:
    ok: bool
    message: str
    device_index: int | None = None


def _play_tone(*, device: int | None, frequency: float, duration_s: float = 0.35) -> None:
    import sounddevice as sd

    rate = 44100
    t = np.linspace(0, duration_s, int(rate * duration_s), endpoint=False)
    wave = (0.25 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
    sd.play(wave, rate, device=device)
    sd.wait()


def test_left_channel() -> RoutingTestResult:
    try:
        device = get_session_output_device()
        _play_tone(device=device, frequency=440.0)
        TTSService(enabled=True).speak("Left channel test.")
        return RoutingTestResult(True, "Left channel test played (tone + speech).", device)
    except Exception as exc:
        return RoutingTestResult(False, f"Left channel test failed: {exc}")


def test_right_channel() -> RoutingTestResult:
    try:
        device = get_session_output_device()
        _play_tone(device=device, frequency=660.0)
        TTSService(enabled=True).speak("Right channel test.")
        return RoutingTestResult(True, "Right channel test played (tone + speech).", device)
    except Exception as exc:
        return RoutingTestResult(False, f"Right channel test failed: {exc}")


def test_audio_routing() -> RoutingTestResult:
    try:
        phrase = "Audio routing test. JARVIS."
        ok = TTSService(enabled=True).speak(phrase)
        report = format_audio_devices_report()
        if not ok:
            return RoutingTestResult(False, f"TTS returned false.\n{report}")
        return RoutingTestResult(True, f"Routing test OK.\n{report}")
    except TTSError as exc:
        return RoutingTestResult(False, f"Routing test failed: {exc}\n{format_audio_devices_report()}")


def cycle_audio_output() -> RoutingTestResult:
    """Speak a short phrase on each output device in rotation (session-only preference)."""
    global _CYCLE_INDEX
    devices = list_playback_devices()
    if not devices:
        return RoutingTestResult(False, "No playback devices found.")
    idx = _CYCLE_INDEX % len(devices)
    _CYCLE_INDEX += 1
    dev = devices[idx]
    set_session_output_device(dev.index, label=dev.name)
    try:
        _play_tone(device=dev.index, frequency=523.25)
        TTSService(enabled=True).speak(f"Testing output device {dev.index}.")
        time.sleep(0.05)
        return RoutingTestResult(
            True,
            (
                f"Cycled to device [{dev.index}] {dev.name}.\n"
                "If you heard this, say: use audio device "
                f"{dev.index}\n"
                "Otherwise say: cycle audio output"
            ),
            dev.index,
        )
    except Exception as exc:
        return RoutingTestResult(False, f"Cycle failed on [{dev.index}] {dev.name}: {exc}")
