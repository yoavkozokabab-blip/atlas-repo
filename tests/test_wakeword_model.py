"""Wake word model path resolution (no default-model fallback)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState
def test_resolve_custom_model_path(tmp_path, monkeypatch):
    onnx = tmp_path / "custom_wake.onnx"
    onnx.write_bytes(b"fake")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL_PATH", str(onnx))
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL", "jarvis")

    from voice.wakeword import resolve_wake_word_model

    res = resolve_wake_word_model()
    assert res.ok
    assert res.model_path == onnx.resolve()


def test_missing_model_no_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL_PATH", "")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL", "jarvis")

    from voice.wakeword import (
        MODEL_NOT_FOUND_MSG,
        WakeWordDetector,
        resolve_wake_word_model,
    )

    with patch("voice.wakeword._glob_resource_models", return_value=[]):
        with patch("voice.wakeword._official_model_candidates", return_value=[]):
            res = resolve_wake_word_model()
    assert not res.ok
    assert res.error == MODEL_NOT_FOUND_MSG
    assert res.searched_paths == []

    app = JarvisApp(runtime=RuntimeState(wake_word_enabled=True))
    started: list[bool] = []

    def factory():
        raise AssertionError("Model() must not be called when file missing")

    detector = WakeWordDetector(app, lambda _s: None, model_factory=factory)
    detector._resolution = res
    detector._model_file = None
    ok = detector.start()
    assert ok is False
    assert detector._thread is None


def test_load_model_uses_explicit_path_only(monkeypatch, tmp_path):
    onnx = tmp_path / "hey_jarvis_v0.1.onnx"
    onnx.write_bytes(b"x")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL_PATH", str(onnx))

    from voice.wakeword import WakeWordDetector, resolve_wake_word_model

    res = resolve_wake_word_model()
    captured: list[list] = []

    class FakeOww:
        def __init__(self, wakeword_models=None, inference_framework=None, **kwargs):
            captured.append(list(wakeword_models or []))
            self.prediction_buffer = {"hey_jarvis": [0.0]}

        def predict(self, _a):
            pass

    app = JarvisApp(runtime=RuntimeState())
    det = WakeWordDetector(
        app,
        lambda _s: None,
        model_resolution=res,
        model_factory=lambda: FakeOww(wakeword_models=[str(res.model_path)], inference_framework="onnx"),
    )
    det._load_model()
    assert captured == [[str(onnx.resolve())]]
    assert "alexa" not in str(captured)


def test_no_fallback_to_default_pretrained_set():
    """Ensure removed code path never calls Model() with empty wakeword_models."""
    from voice import wakeword as ww

    source = Path(ww.__file__).read_text(encoding="utf-8")
    assert "trying default pre-trained" not in source
    assert "wakeword_models=[]" not in source
    assert "return Model(inference_framework=" not in source


def test_jarvis_alias_searches_hey_jarvis_glob(monkeypatch, tmp_path):
    resources = tmp_path / "models"
    resources.mkdir()
    onnx = resources / "hey_jarvis_v0.1.onnx"
    onnx.write_bytes(b"ok")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL_PATH", "")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL", "jarvis")

    from voice.wakeword import resolve_wake_word_model

    with patch("voice.wakeword._openwakeword_resources_dir", return_value=resources):
        with patch("voice.wakeword._official_model_candidates", return_value=[]):
            res = resolve_wake_word_model()
    assert res.ok
    assert res.model_path == onnx.resolve()


def test_status_lists_searched_paths(monkeypatch, tmp_path):
    missing = tmp_path / "nope.onnx"
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL_PATH", str(missing))

    from voice.wakeword import format_wake_word_model_status, resolve_wake_word_model

    with (
        patch("voice.wakeword._glob_resource_models", return_value=[]),
        patch("voice.wakeword._official_model_candidates", return_value=[]),
    ):
        res = resolve_wake_word_model()
    text = format_wake_word_model_status(res)
    assert "Searched paths:" in text
    assert str(missing) in text
    assert "MISSING" in text


def test_push_to_talk_unaffected_when_wake_start_fails(monkeypatch):
    from voice.voice_loop import process_voice_transcript

    app = JarvisApp(runtime=RuntimeState(voice_enabled=True))
    with patch.object(app, "handle_text_command") as handle:
        process_voice_transcript(app, "open cursor", print_result=False)
    handle.assert_called_once()
