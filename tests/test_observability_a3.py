"""Phase A3 observability coverage."""

from __future__ import annotations

import json
import time
from pathlib import Path

from core.results import result_success
from core.types import Intent
from services.observability import get_observability, reset_observability


def _redirect_observability(tmp_path: Path):
    obs = get_observability()
    obs.event_path = tmp_path / "observability.jsonl"
    obs.trace_path = tmp_path / "traces.jsonl"
    reset_observability()
    return obs


def test_structured_logs_traces_heatmaps_and_failures(tmp_path: Path):
    obs = _redirect_observability(tmp_path)

    obs.structured_log("unit.event", value=1)
    trace_id = obs.start_trace("unit_trace", mode="test")
    time.sleep(0.001)
    obs.finish_trace(trace_id, status="ok")
    obs.record_latency("unit.latency", 42)
    obs.profile_stage("pipeline", "stage", 55)
    fingerprint = obs.record_failure(component="unit", error=RuntimeError("boom"))

    snap = obs.snapshot()
    assert snap["latency_heatmaps"]["unit.latency"]["count"] == 1
    assert snap["pipeline_profiles"]["pipeline.stage"]["count"] == 1
    assert fingerprint in snap["failures"]
    assert obs.event_path.is_file()
    assert obs.trace_path.is_file()
    first_event = json.loads(obs.event_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_event["event"] == "unit.event"


def test_command_lifecycle_tracing(monkeypatch, tmp_path: Path):
    obs = _redirect_observability(tmp_path)

    from core.app import JarvisApp

    app = JarvisApp(speak_enabled=False)
    monkeypatch.setattr(
        app.router,
        "route",
        lambda *args, **kwargs: result_success(Intent.SHOW_CAPABILITIES, "ok"),
    )

    result = app.handle_text_command("show capabilities", print_result=False)
    snap = obs.snapshot()

    assert result.summary == "ok"
    assert any(t["name"] == "command" for t in snap["traces"])
    assert snap["latency_heatmaps"]["command.lifecycle"]["count"] == 1
    assert any(e["event"] == "command.lifecycle" for e in snap["events"])


def test_stt_and_tts_timing_metrics(monkeypatch, tmp_path: Path):
    obs = _redirect_observability(tmp_path)

    import config
    import voice.transcriber as transcriber
    from voice.transcriber import TranscriptionResult
    from voice.tts import TTSService

    monkeypatch.setattr(config, "STT_TIMEOUT_SECONDS", 1.0, raising=False)
    monkeypatch.setattr(
        transcriber,
        "_transcribe_audio_detailed_inner",
        lambda _path: TranscriptionResult(
            text="hello",
            language="en",
            model="mock",
            device="cpu",
            compute_type="int8",
        ),
    )
    assert transcriber.transcribe_audio_detailed(tmp_path / "fake.wav").text == "hello"

    monkeypatch.setattr(config, "TTS_ASYNC", False, raising=False)
    monkeypatch.setattr(config, "TTS_TIMEOUT_SECONDS", 1.0, raising=False)
    svc = TTSService(enabled=True)
    monkeypatch.setattr(svc, "_speak_blocking", lambda _safe: True)
    assert svc.speak("hello") is True

    snap = obs.snapshot()
    assert snap["latency_heatmaps"]["stt.transcribe"]["count"] == 1
    assert snap["latency_heatmaps"]["tts.speak"]["count"] == 1
    assert snap["pipeline_profiles"]["voice.stt"]["count"] == 1
    assert snap["pipeline_profiles"]["voice.tts"]["count"] == 1


def test_overlay_fps_metric_samples(tmp_path: Path):
    obs = _redirect_observability(tmp_path)
    obs._overlay_started = time.monotonic() - 1.0
    for _ in range(3):
        obs.record_overlay_frame(sample_seconds=0.001)
        time.sleep(0.002)

    snap = obs.snapshot()
    assert snap["overlay"]["fps"] > 0
    assert any(e["event"] == "overlay.fps" for e in snap["events"])
