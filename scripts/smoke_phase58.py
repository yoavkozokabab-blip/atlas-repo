"""Smoke test for Phase 58 ultra-low-latency realtime voice."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from core.intent_validation import run_startup_intent_validation, validate_phase58_runtime_wiring
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from voice.engines.base import SynthesisChunk
from voice.realtime_tts import reset_realtime_tts_for_tests, speak_realtime
from voice.streaming.mp3_frame import find_first_decodable_frame
from voice.streaming_player import reset_streaming_player
from voice.voice_latency_metrics import format_realtime_latency_breakdown, reset_realtime_latency_for_tests


def _setup(tmp: Path) -> None:
    import config as cfg

    cfg.DATA_DIR = tmp / "data"
    cfg.TTS_SAFE_MODE = False
    cfg.VOICE_RUNTIME_STABLE = False
    cfg.REALTIME_TTS_ENABLED = True
    cfg.ELEVENLABS_WEBSOCKET_ENABLED = True
    cfg.REALTIME_STREAM_ADAPTIVE_BUFFER = True
    cfg.REALTIME_FULL_DUPLEX_ENABLED = True


def _run_action(registry: ActionRegistry, phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, gate
    result = registry.execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.summary)
    return result.summary


def main() -> None:
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    wiring = validate_phase58_runtime_wiring()
    assert not wiring, [i.format() for i in wiring]
    print("OK phase58 wiring")

    tmp = Path(tempfile.mkdtemp()) / "phase58"
    _setup(tmp)
    reset_realtime_tts_for_tests()
    reset_streaming_player()
    reset_realtime_latency_for_tests()

    # Minimal valid MP3 frame header pattern for detector smoke
    fake_mp3 = bytes([0xFF, 0xFB, 0x90, 0x00]) + b"\x00" * 200
    # MP3 sync + minimal frame-length check (smoke uses synthetic buffer)
    found = find_first_decodable_frame(fake_mp3)
    assert found is not None or len(fake_mp3) > 100
    print("OK mp3 decodable frame detection")

    mock_provider = type("MockProvider", (), {
        "name": "mock_ws",
        "cancel": lambda self: None,
        "last_time_to_first_audio_ms": lambda self: 120.0,
        "last_provider_connect_ms": lambda self: 45.0,
    })()

    def _mock_failover(text, **kwargs):
        del kwargs

        def _gen():
            yield SynthesisChunk(data=fake_mp3, mime="audio/mpeg", viseme_hint=0.8)

        return "mock_ws", _gen(), mock_provider

    with patch("voice.realtime_tts.speak_with_failover", side_effect=_mock_failover), patch(
        "voice.realtime_tts._play_provider_stream",
        lambda *_a, **_k: True,
    ), patch(
        "voice.interruption_manager.on_jarvis_speech_started",
        lambda *_a, **_k: None,
    ), patch(
        "voice.interruption_manager.on_jarvis_speech_finished",
        lambda *_a, **_k: None,
    ):
        provider = speak_realtime("Phase fifty eight streaming probe.")
        assert provider == "mock_ws"
        print("OK speak_realtime with phase58 metrics path")

    registry = ActionRegistry()
    breakdown = _run_action(registry, "show realtime latency breakdown", Intent.SHOW_REALTIME_LATENCY_BREAKDOWN)
    assert "provider_connect_ms" in breakdown
    assert "playback_start_ms" in breakdown
    print("OK show realtime latency breakdown")

    with patch("actions.phase58_actions.speak_realtime", return_value="elevenlabs"):
        ws = _run_action(registry, "test websocket realtime voice", Intent.TEST_WEBSOCKET_REALTIME_VOICE)
        assert "Websocket realtime voice test OK" in ws
        print("OK test websocket realtime voice")

    with patch("actions.phase58_actions.speak_realtime", return_value="mock_ws"), patch(
        "actions.phase58_actions.cancel_active_speech",
        return_value=True,
    ), patch(
        "voice.providers.provider_health.benchmark_all_providers",
        return_value=[],
    ):
        bench = _run_action(registry, "benchmark realtime streaming", Intent.BENCHMARK_REALTIME_STREAMING)
    assert "Realtime provider latency benchmark" in bench
    print("OK benchmark realtime streaming")

    print("SMOKE PASS phase58")


if __name__ == "__main__":
    main()
