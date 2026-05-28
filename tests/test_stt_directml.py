"""Optional DirectML STT path (onnx-asr + onnxruntime-directml)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from voice.stt_acceleration import (
    AccelerationProbe,
    configure_stt_runtime,
    get_onnx_providers,
    probe_acceleration,
    reset_stt_acceleration_state,
    resolve_stt_runtime,
    set_acceleration_probe_override,
)
from voice.stt_directml import (
    DirectMLSttError,
    directml_diagnostics,
    onnx_asr_model_id,
    reset_directml_model_cache,
    transcribe_onnx_directml,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_stt_acceleration_state()
    reset_directml_model_cache()
    yield
    reset_stt_acceleration_state()
    reset_directml_model_cache()


def _probe(*, cuda: int = 0, directml: bool = False) -> AccelerationProbe:
    return AccelerationProbe(
        cuda_device_count=cuda,
        cuda_reason="mock",
        directml_available=directml,
        directml_reason="mock directml",
        openvino_available=False,
        openvino_reason="mock",
        onnx_providers=("DmlExecutionProvider", "CPUExecutionProvider")
        if directml
        else ("CPUExecutionProvider",),
    )


def test_directml_detection_mocked():
    set_acceleration_probe_override(_probe(directml=True))
    p = probe_acceleration()
    assert p.directml_available is True
    assert "DmlExecutionProvider" in p.onnx_providers


def test_provider_chain_prefers_dml():
    set_acceleration_probe_override(_probe(directml=True))
    providers = get_onnx_providers(prefer_directml=True)
    assert providers[0] == "DmlExecutionProvider"


def test_resolve_prefers_onnx_directml_when_enabled():
    set_acceleration_probe_override(_probe(cuda=0, directml=True))
    choice = resolve_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=False,
        compute_type_override="",
        prefer_directml=True,
    )
    assert choice.backend == "onnx_directml"
    assert choice.acceleration == "directml"
    assert choice.onnx_provider == "DmlExecutionProvider"


def test_cpu_fallback_when_directml_unavailable():
    set_acceleration_probe_override(_probe(directml=False))
    choice = resolve_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=False,
        compute_type_override="int8",
        prefer_directml=True,
    )
    assert choice.backend == "faster_whisper"
    assert choice.acceleration == "cpu"
    assert choice.fallback_reason is not None


def test_transcribe_falls_back_without_onnx_asr(tmp_path, monkeypatch):
    set_acceleration_probe_override(_probe(directml=True))
    configure_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=False,
        compute_type_override="",
        prefer_directml=True,
    )
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")

    monkeypatch.setattr(
        "voice.stt_directml._onnx_asr_available",
        lambda: False,
    )

    with pytest.raises(DirectMLSttError):
        transcribe_onnx_directml(wav, stt_model="small", language="en")


def test_transcribe_onnx_directml_mocked(tmp_path, monkeypatch):
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")
    fake_model = MagicMock()
    fake_model.recognize.return_value = "open dashboard"

    monkeypatch.setattr(
        "voice.stt_directml._onnx_asr_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "voice.stt_directml.load_onnx_asr_model",
        lambda **_: fake_model,
    )
    monkeypatch.setattr(
        "voice.stt_directml._loaded_provider",
        "DmlExecutionProvider",
        raising=False,
    )
    monkeypatch.setattr(
        "voice.stt_directml._loaded_label",
        "onnx-asr/test [DmlExecutionProvider]",
        raising=False,
    )

    text, provider, label = transcribe_onnx_directml(
        wav, stt_model="small", language="en", prefer_directml=True
    )
    assert text == "open dashboard"
    assert provider == "DmlExecutionProvider"


def test_transcriber_directml_fallback_to_cpu(monkeypatch, tmp_path):
    set_acceleration_probe_override(_probe(directml=True))
    configure_stt_runtime(
        device_request="auto",
        acceleration_auto=True,
        fast_profile=False,
        compute_type_override="",
        prefer_directml=True,
    )
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")

    with (
        patch(
            "voice.transcriber._transcribe_onnx_directml",
            side_effect=RuntimeError("dml boom"),
        ),
        patch(
            "voice.transcriber._transcribe_faster_whisper",
            return_value=MagicMock(
            text="ok",
            language="en",
            model="small",
            device="cpu",
            compute_type="int8",
            low_confidence=False,
            recommendation=None,
            ),
        ),
    ):
        from voice.transcriber import transcribe_audio_detailed

        result = transcribe_audio_detailed(wav)
    assert result.text == "ok"


def test_onnx_asr_model_mapping():
    assert onnx_asr_model_id("small") == "onnx-community/whisper-small"
    assert onnx_asr_model_id("medium") == "onnx-community/whisper-small"


def test_directml_diagnostics_structure():
    diag = directml_diagnostics()
    assert "directml_available" in diag
    assert "chosen_provider" in diag
