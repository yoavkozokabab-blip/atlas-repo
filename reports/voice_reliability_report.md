# Voice Reliability Report

- current_score: 100.0%
- target_score: 85.0%
- gap: 0.0%
- pass_rate: 100.0% (5/5 active, 2 skipped)

## Acceptance Results
- [PASS] voice_config_present (0.0 ms) — voice=True wake=True tts=True
- [SKIP] streaming_policy_readable (0.0 ms) — SKIP: streaming not yet initialized (requires live audio session)
- [SKIP] tts_backend_reported (1.09 ms) — SKIP: no TTS backend selected yet (requires at least one TTS call)
- [PASS] interruption_hooks (0.35 ms) — hooks present
- [PASS] stop_listening_intent (0.0 ms) — stop path registered
- [PASS] long_sentence_normalization (0.03 ms) — normalized='J.A.R.V.I.S. show me the latest trading dashboard status ple'
- [PASS] paragraph_transcription_path (0.0 ms) — transcriber_importable=True streaming_enabled=False

## Latency Snapshot
- last_stt_ms: n/a
- last_tts_ms: n/a
- last_e2e_ms: n/a