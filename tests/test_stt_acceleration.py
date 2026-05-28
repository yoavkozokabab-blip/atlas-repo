"""STT acceleration auto-detect, profiles, and benchmark."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import classify_rules
from core.types import Intent
from voice.stt_acceleration import (
    AccelerationProbe,
    configure_stt_runtime,
    probe_acceleration,
    reset_stt_acceleration_state,
    resolve_stt_runtime,
    set_acceleration_probe_override,
)
from voice.stt_profile import apply_voice_profile


@pytest.fixture(autouse=True)
def _reset_accel():
    reset_stt_acceleration_state()
    yield
    reset_stt_acceleration_state()


def _probe(*, cuda: int = 0, directml: bool = False, openvino: bool = False) -> AccelerationProbe:
    return AccelerationProbe(
        cuda_device_count=cuda,
        cuda_reason="mock",
        directml_available=directml,
        directml_reason="mock directml",
        openvino_available=openvino,
        openvino_reason="mock openvino",
        onnx_providers=("DmlExecutionProvider",) if directml else ("CPUExecutionProvider",),
    )


def test_cuda_explicit_falls_back_without_gpu():
    set_acceleration_probe_override(_probe(cuda=0))
    choice = resolve_stt_runtime(
        device_request="cuda",
        acceleration_auto=False,
        fast_profile=False,
        compute_type_override="",
        prefer_directml=False,
    )
    assert choice.whisper_device == "cpu"
    assert choice.compute_type == "int8"
    assert choice.gpu_warning


def test_auto_chooses_cuda_when_mocked():
    set_acceleration_probe_override(_probe(cuda=1))
    choice = resolve_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=False,
        compute_type_override="",
        prefer_directml=False,
    )
    assert choice.whisper_device == "cuda"
    assert choice.acceleration == "cuda"
    assert choice.compute_type == "float16"


def test_auto_chooses_directml_when_preferred():
    set_acceleration_probe_override(_probe(cuda=0, directml=True))
    choice = resolve_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=True,
        compute_type_override="",
        prefer_directml=True,
    )
    assert choice.backend == "onnx_directml"
    assert choice.acceleration == "directml"
    assert choice.onnx_provider == "DmlExecutionProvider"


def test_auto_cpu_when_directml_not_preferred():
    set_acceleration_probe_override(_probe(cuda=0, directml=True))
    choice = resolve_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=True,
        compute_type_override="",
        prefer_directml=False,
    )
    assert choice.backend == "faster_whisper"
    assert choice.acceleration == "cpu"


def test_cpu_fallback_explicit():
    set_acceleration_probe_override(_probe(cuda=0, directml=False))
    choice = resolve_stt_runtime(
        device_request="cpu",
        acceleration_auto=False,
        fast_profile=False,
        compute_type_override="int8",
        prefer_directml=False,
    )
    assert choice.whisper_device == "cpu"
    assert choice.compute_type == "int8"


def test_startup_status_reports_backend(capsys):
    set_acceleration_probe_override(_probe(cuda=0, directml=True))
    configure_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=True,
        compute_type_override="",
        prefer_directml=True,
    )
    from voice.transcriber import print_stt_startup_info

    print_stt_startup_info()
    out = capsys.readouterr().out
    assert "STT backend (auto)" in out
    assert "Backend: onnx_directml" in out
    assert "DirectML available: yes" in out
    assert "DmlExecutionProvider" in out


def test_benchmark_stt_registered_and_mocked():
    from actions.stt_actions import BenchmarkSttAction
    from core.types import CommandRequest

    with patch("actions.stt_actions.run_stt_benchmark", return_value="STT benchmark\n  Latency_ms: 12.0"):
        result = BenchmarkSttAction().execute(
            CommandRequest(
                raw_text="benchmark stt",
                intent=Intent.BENCHMARK_STT,
                confidence=1.0,
            )
        )
    assert "Latency_ms" in result.summary


def test_classify_benchmark_stt():
    req = classify_rules("benchmark stt")
    assert req.intent == Intent.BENCHMARK_STT


def test_benchmark_uses_synthetic_audio_only(monkeypatch, tmp_path):
    monkeypatch.setattr("voice.stt_benchmark.get_stt_runtime", lambda: configure_stt_runtime(
        device_request="cpu",
        acceleration_auto=False,
        fast_profile=False,
        compute_type_override="int8",
        prefer_directml=False,
    ))
    fake = MagicMock(
        text="",
        language="en",
        model="small",
        device="cpu",
        compute_type="int8",
    )
    with patch("voice.stt_benchmark.transcribe_audio_detailed", return_value=fake):
        from voice.stt_benchmark import run_stt_benchmark

        report = run_stt_benchmark(work_dir=tmp_path)
    assert "synthetic" in report.lower()
    assert "latency_ms" in report


def test_fast_profile_overrides():
    out = apply_voice_profile(
        voice_profile="fast",
        stt_fast_profile=False,
        fast_voice_mode=False,
        model_raw="medium",
        beam_size=5,
        wake_max_listen_seconds=6.0,
        low_confidence_block_wake_env=True,
    )
    assert out.applied
    assert out.model == "small"
    assert out.beam_size == 2
    assert out.wake_max_listen_seconds == 4.0
    assert out.fast_voice_mode is True
    assert out.low_confidence_block_wake is False


def test_accurate_profile_overrides():
    out = apply_voice_profile(
        voice_profile="accurate",
        stt_fast_profile=False,
        fast_voice_mode=False,
        model_raw="small",
        beam_size=1,
        wake_max_listen_seconds=4.0,
        low_confidence_block_wake_env=False,
    )
    assert out.profile_name == "accurate"
    assert out.model == "medium"
    assert out.beam_size == 3
    assert out.wake_max_listen_seconds == 5.0
    assert out.low_confidence_block_wake is True


def test_cuda_load_fallback_to_cpu(monkeypatch):
    set_acceleration_probe_override(_probe(cuda=1))
    configure_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=False,
        compute_type_override="",
        prefer_directml=False,
    )
    calls: list[tuple[str, str]] = []

    class _FakeModel:
        def __init__(self, _name, *, device, compute_type):
            calls.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("no cuda")

        def transcribe(self, *_a, **_k):
            return iter([]), MagicMock(language_probability=0.9, duration=1.0)

    monkeypatch.setattr("voice.transcriber._model_cache", None)
    with patch("faster_whisper.WhisperModel", _FakeModel):
        from voice.transcriber import _load_faster_whisper

        _load_faster_whisper()
    assert ("cuda", "float16") in calls
    assert ("cpu", "int8") in calls


def test_probe_has_no_network():
    with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
        probe = probe_acceleration()
    assert probe.onnx_providers is not None
