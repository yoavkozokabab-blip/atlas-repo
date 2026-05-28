"""Hard A/B audio route proof — engine completion vs user-confirmed audible output."""

from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import TTS_RATE_RAW
from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER, Pyttsx3TTSError


@dataclass
class AudioRouteProveStep:
    test_num: int
    method: str
    engine_completed: bool
    engine_error: str = ""
    user_heard: bool | None = None


@dataclass
class AudioRouteProveReport:
    steps: list[AudioRouteProveStep] = field(default_factory=list)
    process_context: str = ""
    selected_backend: str | None = None
    summary: str = ""


def parse_yes_no(text: str) -> bool | None:
    t = (text or "").strip().lower()
    if t in {"yes", "y", "yeah", "yep", "heard", "affirmative"}:
        return True
    if t in {"no", "n", "nope", "nah", "negative", "nothing", "silent"}:
        return False
    return None


def ask_user_heard_test(
    test_num: int,
    *,
    input_fn: Callable[[str], str] | None = None,
    timeout_seconds: float = 120.0,
) -> bool | None:
    prompt = f"Did you hear test {test_num}? say yes or no"
    if input_fn is not None:
        print(prompt, flush=True)
        for _ in range(2):
            try:
                answer = input_fn(f"{prompt}: ")
            except (EOFError, OSError):
                return None
            parsed = parse_yes_no(answer)
            if parsed is not None:
                return parsed
            print("Please answer yes or no.", flush=True)
        return None
    from ui.console_modal import run_modal_yes_no_prompt

    return run_modal_yes_no_prompt(prompt, timeout_seconds=timeout_seconds)


def _gap(seconds: float = 2.0) -> None:
    time.sleep(max(0.0, seconds))


def prove_test1_direct_pyttsx3() -> tuple[bool, str]:
    """Same function object as forced normal TTS (NORMAL_DIRECT_SPEAKER)."""
    try:
        NORMAL_DIRECT_SPEAKER(
            "Test one direct pyttsx3",
            rate_raw=TTS_RATE_RAW,
            record_user_success=False,
        )
        return True, ""
    except Pyttsx3TTSError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def prove_test2_winsound_beep() -> tuple[bool, str]:
    try:
        import winsound

        winsound.Beep(880, 700)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _write_test_wav(path: Path, *, freq: float = 880.0, duration: float = 0.7) -> None:
    rate = 44100
    n = int(rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            sample = int(32767 * 0.45 * math.sin(2.0 * math.pi * freq * i / rate))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)


def prove_test3_wav_winsound() -> tuple[bool, str]:
    fd, name = tempfile.mkstemp(suffix=".wav", prefix="jarvis_prove_")
    os.close(fd)
    path = Path(name)
    try:
        _write_test_wav(path)
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def prove_test4_wav_sounddevice() -> tuple[bool, str]:
    fd, name = tempfile.mkstemp(suffix=".wav", prefix="jarvis_prove_sd_")
    os.close(fd)
    path = Path(name)
    try:
        _write_test_wav(path, freq=660.0)
        from scipy.io import wavfile
        import sounddevice as sd

        rate, data = wavfile.read(path)
        if getattr(data, "ndim", 1) > 1:
            data = data[:, 0]
        samples = data.astype("float32") / max(1.0, float(abs(data).max()))
        sd.play(samples, int(rate))
        sd.wait()
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def format_process_audio_context() -> str:
    lines = [
        "JARVIS process audio context",
        f"  python executable: {sys.executable}",
        f"  python version: {sys.version.split()[0]}",
        f"  cwd: {os.getcwd()}",
        f"  argv0: {sys.argv[0] if sys.argv else 'n/a'}",
        f"  main thread: {threading.current_thread().name}",
        f"  pid: {os.getpid()}",
    ]
    exe_name = Path(sys.executable).name.lower()
    if "pythonw" in exe_name:
        lines.append("  launcher: pythonw (no console — input() may fail)")
    else:
        lines.append("  launcher: python.exe (console)")
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        lines.append(f"  foreground hwnd: {hwnd}")
    except Exception as exc:
        lines.append(f"  foreground hwnd: unavailable ({exc})")
    env_keys = (
        "VOICE_RUNTIME_MODE",
        "TTS_SAFE_MODE",
        "TTS_ASYNC",
        "JARVIS_TEST_MODE",
        "JARVIS_ALLOW_AUDIO_PLAYBACK",
    )
    for key in env_keys:
        val = os.environ.get(key)
        if val is not None:
            lines.append(f"  env {key}={val}")
    try:
        import sounddevice as sd

        dev = sd.default.device
        lines.append(f"  sounddevice default: {dev}")
    except Exception as exc:
        lines.append(f"  sounddevice default: unavailable ({exc})")
    return "\n".join(lines)


def resolve_verified_backend_from_user_results(
    *,
    direct: bool | None,
    winsound: bool | None,
    wav_winsound: bool | None,
    sounddevice: bool | None,
) -> str | None:
    order = [
        ("direct_pyttsx3", direct),
        ("winsound", winsound),
        ("wav_winsound", wav_winsound),
        ("sounddevice", sounddevice),
    ]
    heard = [name for name, val in order if val is True]
    if not heard:
        return None
    return heard[0]


def run_audio_route_prove(
    *,
    gap_seconds: float = 2.0,
    input_fn: Callable[[str], str] | None = None,
) -> AudioRouteProveReport:
    from voice.audio_status import (
        record_user_heard_result,
        set_selected_verified_audio_backend,
    )

    report = AudioRouteProveReport()
    tests: list[tuple[int, str, Callable[[], tuple[bool, str]]]] = [
        (1, "direct_pyttsx3", prove_test1_direct_pyttsx3),
        (2, "winsound", prove_test2_winsound_beep),
        (3, "wav_winsound", prove_test3_wav_winsound),
        (4, "sounddevice", prove_test4_wav_sounddevice),
    ]

    for idx, (num, method, runner) in enumerate(tests):
        if idx > 0:
            _gap(gap_seconds)
        ok, err = runner()
        step = AudioRouteProveStep(
            test_num=num,
            method=method,
            engine_completed=ok,
            engine_error=err,
        )
        if ok:
            _gap(0.3)
            step.user_heard = ask_user_heard_test(num, input_fn=input_fn)
            record_user_heard_result(method, step.user_heard)
        report.steps.append(step)

    direct = next((s.user_heard for s in report.steps if s.method == "direct_pyttsx3"), None)
    win = next((s.user_heard for s in report.steps if s.method == "winsound"), None)
    ww = next((s.user_heard for s in report.steps if s.method == "wav_winsound"), None)
    sd = next((s.user_heard for s in report.steps if s.method == "sounddevice"), None)

    backend = resolve_verified_backend_from_user_results(
        direct=direct,
        winsound=win,
        wav_winsound=ww,
        sounddevice=sd,
    )
    set_selected_verified_audio_backend(backend)
    report.selected_backend = backend
    report.process_context = format_process_audio_context()

    lines = ["Audio route prove — results", ""]
    for step in report.steps:
        eng = "engine OK" if step.engine_completed else f"engine FAIL ({step.engine_error})"
        if step.user_heard is True:
            usr = "user heard: YES"
        elif step.user_heard is False:
            usr = "user heard: NO"
        else:
            usr = "user heard: (not asked / skipped)"
        lines.append(f"  Test {step.test_num} ({step.method}): {eng}; {usr}")
    lines.append("")
    lines.append(f"  Selected verified backend: {backend or 'none'}")
    if backend == "direct_pyttsx3":
        lines.append("  Normal TTS will use NORMAL_DIRECT_SPEAKER (test 1 function).")
    elif backend is None and any(s.engine_completed for s in report.steps):
        lines.append(
            "  Engine(s) completed but user heard nothing — see process context below."
        )
        lines.append(report.process_context)
    elif backend is None:
        lines.append("  No audible route verified.")
        lines.append(report.process_context)

    report.summary = "\n".join(lines)
    return report
