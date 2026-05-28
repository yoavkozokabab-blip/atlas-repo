"""Fast voice mode, grammar, latency, overlay queue, async TTS."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from brain.intent_classifier import classify_rules
from brain.router import CommandRouter
from brain.voice_grammar import match_voice_grammar
from core.app import JarvisApp
from core.runtime_state import RuntimeState, reset_runtime_state
from core.types import Intent
from voice.fast_voice import effective_max_record_seconds, effective_wake_listen_seconds
from voice.latency_tracker import (
    begin_voice_command,
    finish_and_log,
    get_last_latency,
    reset_latency_tracker,
    set_record_ms,
    set_route_timing,
    set_transcribe_ms,
)
from voice.microphone import _record_stream, _silence_stop_ready, record_for_seconds
from voice.transcriber import reset_model_cache
from voice.transcript_cleanup import cleanup_transcript
from voice.tts import TTSService
from voice.wake_greeting import play_wake_greeting_async


@pytest.fixture(autouse=True)
def _reset_voice_state():
    reset_latency_tracker()
    reset_model_cache()
    yield
    reset_latency_tracker()
    reset_model_cache()


def test_cleanup_transcript_fixes_common_mistakes():
    assert cleanup_transcript("open dash board") == "open dashboard"
    assert cleanup_transcript("show dash board health") == "show dashboard health"
    assert cleanup_transcript("run diagnostic") == "run diagnostics"
    assert cleanup_transcript("open chat gpt") == "open chatgpt"
    assert cleanup_transcript("open trading view") == "open tradingview"


@pytest.mark.parametrize(
    "phrase, intent, website",
    [
        ("open dashboard", Intent.OPEN_TRADING_DASHBOARD, None),
        ("show dashboard health", Intent.SHOW_DASHBOARD_HEALTH, None),
        ("run diagnostics", Intent.RUN_DIAGNOSTICS, None),
        ("open youtube", Intent.OPEN_WEBSITE, "youtube"),
        ("open chatgpt", Intent.OPEN_WEBSITE, "chatgpt"),
        ("show runtime status", Intent.SHOW_RUNTIME_STATUS, None),
        ("what can you do", Intent.SHOW_CAPABILITIES, None),
        ("list workflows", Intent.LIST_WORKFLOWS, None),
        ("check trading", Intent.RUN_WORKFLOW, None),
        ("show last errors", Intent.SHOW_LAST_ERRORS, None),
    ],
)
def test_voice_grammar_fuzzy_match(phrase, intent, website):
    req = match_voice_grammar(phrase)
    assert req is not None
    assert req.intent == intent
    assert req.confidence >= 0.85
    if website:
        assert req.params.get("website") == website


def test_voice_grammar_maps_near_miss():
    req = match_voice_grammar("open dashbord")
    assert req is not None
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD


def test_classify_rules_uses_grammar_before_slow_path():
    req = classify_rules(cleanup_transcript("open dash board"))
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD


def test_stt_preload_loads_once(monkeypatch):
    loads: list[str] = []

    class FakeModel:
        def transcribe(self, *a, **k):
            return iter([]), MagicMock(language_probability=1.0, duration=0.1)

    monkeypatch.setattr("config.STT_ENGINE", "faster_whisper", raising=False)
    monkeypatch.setattr("voice.stt_config.normalize_stt_model", lambda m: "small", raising=False)
    monkeypatch.setattr("config.STT_MODEL", "small", raising=False)
    monkeypatch.setattr("config.STT_COMPUTE_TYPE", "int8", raising=False)
    monkeypatch.setattr("config.STT_DEVICE", "cpu", raising=False)

    def fake_load():
        loads.append("load")
        import voice.transcriber as tr

        tr._model_cache = FakeModel()
        tr._loaded_model_label = "small"
        tr._loaded_compute_type = "int8"
        return FakeModel()

    monkeypatch.setattr("voice.transcriber._load_faster_whisper", fake_load)
    import voice.transcriber as tr
    from voice.transcriber import get_stt_status, preload_stt_model

    assert preload_stt_model() is True
    assert get_stt_status().model_loaded
    assert preload_stt_model() is True
    assert loads == ["load"]
    assert tr._model_cache is not None


def test_silence_stop_shortens_recording(monkeypatch):
    monkeypatch.setattr("config.STT_SILENCE_STOP_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_SILENCE_SECONDS", 0.15, raising=False)
    monkeypatch.setattr("config.STT_SILENCE_THRESHOLD", 0.05, raising=False)

    stop = threading.Event()

    def fake_input_stream(**kwargs):
        cb = kwargs["callback"]

        class Ctx:
            def __enter__(self):
                for _ in range(3):
                    cb(np.zeros((160, 1), dtype=np.float32), None, None, None)
                for _ in range(2):
                    cb(np.ones((160, 1), dtype=np.float32) * 0.2, None, None, None)
                for _ in range(30):
                    cb(np.zeros((160, 1), dtype=np.float32), None, None, None)
                return self

            def __exit__(self, *a):
                return False

        return Ctx()

    monkeypatch.setattr("sounddevice.InputStream", fake_input_stream)
    t0 = time.perf_counter()
    audio = _record_stream(
        stop_event=stop,
        sample_rate=16000,
        device=None,
        max_seconds=10.0,
        silence_stop=True,
        silence_seconds=0.15,
    )
    elapsed = time.perf_counter() - t0
    assert audio.size > 0
    assert elapsed < 3.0


def test_fast_voice_caps_wake_listen(monkeypatch):
    monkeypatch.setattr("config.FAST_VOICE_MODE", True, raising=False)
    monkeypatch.setattr("config.STT_MAX_RECORD_SECONDS", 5, raising=False)
    monkeypatch.setattr("config.WAKE_MAX_LISTEN_SECONDS", 4, raising=False)
    assert effective_wake_listen_seconds() == 4.0
    assert effective_max_record_seconds(wake_session=True) == 4.0
    assert effective_max_record_seconds(wake_session=False) == 5.0


def test_wake_early_stop_triggers_only_after_speech_end():
    common = {
        "silence_stop": True,
        "has_chunks": True,
        "sample_count": 16000,
        "min_samples_before_silence": 5600,
        "now": 10.0,
        "last_voice_at": 9.0,
        "silence_seconds": 0.25,
        "require_voice_before_silence_stop": True,
    }
    assert not _silence_stop_ready(**common, voice_detected=False)
    assert _silence_stop_ready(**common, voice_detected=True)


def test_wake_recording_uses_early_stop_after_speech(monkeypatch, tmp_path):
    calls: dict[str, object] = {}
    wav = tmp_path / "wake.wav"
    monkeypatch.setattr("config.WAKE_EARLY_STOP_ENABLED", True, raising=False)
    monkeypatch.setattr("config.WAKE_MAX_LISTEN_SECONDS", 4, raising=False)
    monkeypatch.setattr("voice.microphone.check_microphone_available", lambda: None)
    monkeypatch.setattr("voice.microphone._save_wav", lambda _audio, _rate: wav)

    def fake_record_stream(**kwargs):
        calls.update(kwargs)
        return np.ones((10, 1), dtype=np.float32)

    monkeypatch.setattr("voice.microphone._record_stream", fake_record_stream)
    assert record_for_seconds(10, wake_session=True) == wav
    assert calls["max_seconds"] == 4.0
    assert calls["silence_stop"] is True
    assert calls["require_voice_before_silence_stop"] is True


def test_manual_voice_recording_keeps_manual_silence_mode(monkeypatch, tmp_path):
    calls: dict[str, object] = {}
    wav = tmp_path / "manual.wav"
    monkeypatch.setattr("config.STT_SILENCE_STOP_ENABLED", True, raising=False)
    monkeypatch.setattr("config.WAKE_EARLY_STOP_ENABLED", True, raising=False)
    monkeypatch.setattr("voice.microphone.check_microphone_available", lambda: None)
    monkeypatch.setattr("voice.microphone._save_wav", lambda _audio, _rate: wav)

    def fake_record_stream(**kwargs):
        calls.update(kwargs)
        return np.ones((10, 1), dtype=np.float32)

    monkeypatch.setattr("voice.microphone._record_stream", fake_record_stream)
    assert record_for_seconds(1, wake_session=False) == wav
    assert calls["silence_stop"] is True
    assert calls["require_voice_before_silence_stop"] is True


def test_latency_logged_for_voice_route(monkeypatch, tmp_path):
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", tmp_path / "hist.jsonl", raising=False)
    begin_voice_command(source="voice")
    set_record_ms(120.0)
    set_transcribe_ms(340.0)
    set_route_timing(classify_ms=12.0, execute_ms=45.0, intent="show_capabilities")
    rec = finish_and_log()
    assert rec is not None
    assert rec.record_ms == 120.0
    assert rec.transcribe_ms == 340.0
    assert rec.classify_ms == 12.0
    assert rec.execute_ms == 45.0
    assert rec.total_ms is not None


def test_show_voice_performance_status_action(monkeypatch):
    monkeypatch.setattr("config.FAST_VOICE_MODE", True, raising=False)
    monkeypatch.setattr("config.STT_MODEL", "small", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    from actions.voice_performance_actions import ShowVoicePerformanceStatusAction
    from core.types import CommandRequest

    result = ShowVoicePerformanceStatusAction().execute(
        CommandRequest(
            raw_text="show voice performance status",
            intent=Intent.SHOW_VOICE_PERFORMANCE_STATUS,
            confidence=1.0,
        )
    )
    assert "FAST_VOICE_MODE=True" in result.summary
    assert "STT_MODEL=small" in result.summary
    assert "TTS_ASYNC=True" in result.summary


def test_classify_show_voice_performance_status():
    req = classify_rules("show voice performance status")
    assert req.intent == Intent.SHOW_VOICE_PERFORMANCE_STATUS


def test_show_latency_status_action():
    begin_voice_command()
    set_record_ms(50.0)
    finish_and_log()
    from actions.latency_actions import ShowLatencyStatusAction
    from core.types import CommandRequest

    result = ShowLatencyStatusAction().execute(
        CommandRequest(raw_text="show latency status", intent=Intent.SHOW_LATENCY_STATUS, confidence=1.0)
    )
    assert "record_ms" in result.summary


def test_overlay_updates_are_queued(monkeypatch):
    monkeypatch.setattr("ui.overlay_app.OVERLAY_QT_ENABLED", True, raising=False)
    from ui.overlay_app import OverlayController

    ctrl = OverlayController()
    seen: list[str] = []

    def mark() -> None:
        seen.append("ok")

    ctrl._enqueue_update(mark)
    time.sleep(0.25)
    assert "ok" in seen


def test_overlay_drops_when_queue_full(monkeypatch):
    monkeypatch.setattr("config.OVERLAY_UPDATE_QUEUE_SIZE", 2, raising=False)
    from ui.overlay_app import OverlayController

    ctrl = OverlayController()
    ctrl._update_queue = queue.Queue(maxsize=2)
    ctrl._enqueue_update(lambda: None)
    ctrl._enqueue_update(lambda: None)
    ctrl._enqueue_update(lambda: None)
    assert ctrl._update_queue.qsize() <= 2


def test_async_tts_does_not_block(monkeypatch):
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    tts = TTSService(enabled=True)
    gate = threading.Event()

    def slow(_safe: str) -> bool:
        gate.wait(timeout=2.0)
        return True

    with patch.object(tts, "_speak_blocking", side_effect=slow):
        t0 = time.perf_counter()
        tts.speak("hello")
        assert time.perf_counter() - t0 < 0.5
    gate.set()


def test_router_still_validates_security(monkeypatch, tmp_path):
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", tmp_path / "hist.jsonl", raising=False)
    router = CommandRouter()
    with patch.object(router.registry, "execute") as execute:
        result = router.route("enable kill switch", input_mode="voice")
    execute.assert_not_called()
    assert result.status.value in ("confirmation_required", "blocked", "failed", "clarification_needed")


def test_wake_greeting_async_does_not_block_record(monkeypatch):
    order: list[str] = []
    runtime = RuntimeState(speak_enabled=True)
    app = JarvisApp(speak_enabled=True, runtime=runtime)
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_ENABLED", True, raising=False)
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_ASYNC", True, raising=False)

    def slow_greet(_app):
        order.append("greeting_start")
        time.sleep(0.3)
        order.append("greeting_end")

    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting", slow_greet)
    order.append("before")
    play_wake_greeting_async(app)
    order.append("after")
    assert order[0] == "before"
    assert "after" in order
    assert order.index("after") <= 2
    time.sleep(0.4)
    assert "greeting_start" in order
    assert "greeting_end" in order


@pytest.fixture
def app():
    reset_runtime_state()
    return JarvisApp(speak_enabled=True, runtime=RuntimeState(speak_enabled=True))


def test_wakeword_loop_listening_before_record(app, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")
    order: list[str] = []

    monkeypatch.setattr(
        "voice.wake_greeting.play_wake_greeting_async",
        lambda _a: order.append("greeting_async"),
    )
    monkeypatch.setattr(
        "ui.overlay_app.notify_overlay_listening",
        lambda: order.append("listening"),
    )
    monkeypatch.setattr(
        "voice.wakeword_loop.record_for_seconds",
        lambda _s, **k: order.append("record") or wav,
    )
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="open dashboard",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    monkeypatch.setattr("voice.wake_greeting.strip_wake_phrase_from_transcript", lambda t: t)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcribing", lambda: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcript", lambda _t: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_thinking", lambda: None)
    monkeypatch.setattr(
        "voice.voice_loop.process_voice_transcript",
        lambda *a, **k: order.append("command"),
    )

    from voice.wakeword_loop import run_post_wake_listening_session

    run_post_wake_listening_session(app)
    assert order.index("listening") < order.index("record")
    assert order.index("greeting_async") < order.index("record")
