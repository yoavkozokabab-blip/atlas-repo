"""Local STT benchmark (synthetic audio, no mic, no network)."""

from __future__ import annotations

import time
import wave
from pathlib import Path

import numpy as np

from voice.stt_acceleration import configure_stt_runtime, get_stt_runtime, probe_acceleration
from voice.transcriber import get_stt_status, reset_model_cache, transcribe_audio_detailed


def synthetic_benchmark_wav(path: Path, *, seconds: float = 1.5, sample_rate: int = 16000) -> Path:
    """Write a short tonal WAV fixture (speech-like energy, no external files)."""
    t = np.linspace(0, seconds, int(sample_rate * seconds), dtype=np.float32)
    audio = 0.2 * np.sin(2 * np.pi * 220 * t) + 0.1 * np.sin(2 * np.pi * 440 * t)
    audio = (audio * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return path


def _run_one_backend(*, wav: Path) -> tuple[bool, float, str, object]:
    from config import STT_BEAM_SIZE, STT_MODEL

    runtime = get_stt_runtime()
    reset_model_cache()
    t0 = time.perf_counter()
    try:
        result = transcribe_audio_detailed(wav)
        ok = True
        err = ""
    except Exception as exc:
        result = None
        ok = False
        err = str(exc)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    status = get_stt_status()
    lines = [
        f"  backend={runtime.backend}",
        f"  provider={runtime.onnx_provider}",
        f"  device={status.device}",
        f"  model={STT_MODEL}",
        f"  compute={status.compute_type}",
        f"  beam={STT_BEAM_SIZE}",
        f"  latency_ms={elapsed_ms:.1f}",
        f"  ok={'yes' if ok else 'no'}",
    ]
    if err:
        lines.append(f"  error={err}")
    if ok and result is not None and result.text:
        lines.append(f"  transcript_preview={result.text[:60]!r}")
    return ok, elapsed_ms, "\n".join(lines), runtime


def run_stt_benchmark(*, work_dir: Path | None = None) -> str:
    """Run local transcription benchmark(s); return report text."""
    from config import STT_PREFER_DIRECTML

    probe = probe_acceleration()
    root = work_dir or Path("reports") / "stt_bench"
    wav = synthetic_benchmark_wav(root / "_synthetic_bench.wav")

    lines = ["STT benchmark (local synthetic audio)", ""]

    # Active configured backend
    runtime = get_stt_runtime()
    ok, ms, detail, _ = _run_one_backend(wav=wav)
    lines.append("Active profile:")
    lines.append(detail)
    lines.append("")

    # Optional CPU comparison when DirectML is preferred
    if STT_PREFER_DIRECTML and probe.directml_available:
        configure_stt_runtime(
            device_request="auto",
            acceleration_auto=True,
            fast_profile=False,
            compute_type_override="",
            prefer_directml=False,
        )
        lines.append("CPU fallback comparison (faster-whisper):")
        _ok, cpu_ms, cpu_detail, _ = _run_one_backend(wav=wav)
        lines.append(cpu_detail)
        if ok and _ok:
            lines.append(f"  avg_latency_delta_ms={ms - cpu_ms:+.1f}")
        lines.append("")

    lines.append("Detected acceleration:")
    lines.extend(probe.summary_lines())
    try:
        from voice.stt_directml import directml_diagnostics

        dml = directml_diagnostics()
        lines.append(f"  onnx-asr installed: {'yes' if dml.get('onnx_asr_installed') else 'no'}")
        lines.append(f"  chosen_provider: {dml.get('chosen_provider')}")
    except Exception:
        pass

    from config import (
        STT_ACCELERATION_AUTO,
        STT_COMPUTE_TYPE,
        STT_DEVICE_REQUEST,
        STT_FAST_PROFILE,
        STT_PREFER_DIRECTML,
        VOICE_PROFILE,
    )

    configure_stt_runtime(
        device_request=STT_DEVICE_REQUEST,
        acceleration_auto=STT_ACCELERATION_AUTO,
        fast_profile=STT_FAST_PROFILE or VOICE_PROFILE == "fast",
        compute_type_override=STT_COMPUTE_TYPE,
        prefer_directml=STT_PREFER_DIRECTML,
    )

    try:
        wav.unlink(missing_ok=True)
    except OSError:
        pass
    return "\n".join(lines)
