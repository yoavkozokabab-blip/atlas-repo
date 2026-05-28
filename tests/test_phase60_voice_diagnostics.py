from __future__ import annotations


def test_endpoint_state_has_energy_and_vad_probability() -> None:
    import numpy as np

    from voice.streaming_stt.endpoint_detector import StreamEndpointDetector

    det = StreamEndpointDetector(
        silence_threshold=0.01,
        endpoint_silence_ms=300,
        sample_rate=16000,
        chunk_seconds=0.1,
    )
    noisy = (np.ones((1600,), dtype=np.float32) * 0.02).astype(np.float32)
    state = det.observe_chunk(noisy)
    assert state.energy > 0
    assert 0.0 <= state.vad_probability <= 1.0


def test_voice_turn_diagnostics_records_values() -> None:
    from voice.voice_turn_diagnostics import (
        begin_turn,
        get_last_voice_turn_diagnostics,
        note_chunk,
        note_endpoint,
        note_silence,
        note_speech_detected,
    )

    begin_turn()
    note_chunk(energy=0.02, vad_probability=0.9, tts_active=True)
    note_speech_detected()
    note_silence(silence_ms=1400)
    note_endpoint("silence_after_speech")
    diag = get_last_voice_turn_diagnostics()
    assert diag.tts_active_during_capture is True
    assert diag.endpoint_reason == "silence_after_speech"
    assert 1.0 <= diag.silence_duration_s <= 1.8

