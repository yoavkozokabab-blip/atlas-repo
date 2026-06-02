# Voice Hardening Audit - Voice-Hardening-1

Date: 2026-05-29

## Scope

Audited wakeword, microphone recovery, VAD, endpoint detection, STT, TTS,
interruption handling, and latency using the current runtime code, command
history, observability events, runtime monitor status, and focused pytest
reproduction.

## Metrics

| Metric | Before / baseline | After this fix | Source |
| --- | ---: | ---: | --- |
| Historical voice/wake commands | 899 samples | unchanged | `data/command_history.jsonl` tail 5000 |
| Historical avg command duration | 872.8 ms | unchanged | voice/wake `duration_ms` |
| Historical p95 command duration | 5254 ms | unchanged | voice/wake `duration_ms` |
| Historical non-success rate | 61.3% | unchanged | non-`success` voice/wake statuses |
| Real voice evidence all-green rate | 77.5% | unchanged | 293 `data/voice_evidence/real_voice_*.json` files |
| Real voice partial recovery count | 66 | unchanged | evidence files with partial success plus error |
| Reproduced push-to-talk route failure rate | 100.0% (1/1 failed) | 0.0% (11/11 passed) | targeted pytest |
| Reproduced push-to-talk recovery rate | 0.0% | 100.0% | final transcript reaches router after STT |
| Post-fix push-to-talk avg `voice.total` | n/a; crashed before finish/log | 55.2 ms | `data/observability_events.jsonl`, 11 deterministic events |
| Post-fix push-to-talk p95 `voice.total` | n/a; crashed before finish/log | 182.0 ms | same |

Notes:
- Historical command duration is router/action duration after transcript intake;
  it is useful for trend context but does not isolate real mic capture or STT.
- Post-fix latency is from mocked-audio regression harness events, not live
  microphone timing.
- Runtime monitor snapshot was `overall=ok`, no active operations, no timeouts,
  no recorded recoveries, memory growth 0.2 MB over the configured window.

## Highest-Impact Blocker Fixed

Push-to-talk voice could crash immediately after a successful STT result:

- `voice.voice_loop.run_voice_loop()` called `record_stt_result(stt_result)`
  without the required keyword-only `transcribe_ms`.
- The low-confidence branch called `notify_low_confidence()` without the required
  `app` and `overlay_enabled` arguments.
- Reproduction: `py -3 -m pytest tests\test_voice_pipeline.py::test_voice_loop_hebrew_through_router -q`
  failed with `TypeError: record_stt_result() missing 1 required keyword-only argument: 'transcribe_ms'`.

This is the biggest blocker found because it turns a successful local
transcription into a runtime exception before routing. The fix keeps the same
router/security/registry path: final text still goes through
`process_voice_transcript()` and `app.handle_text_command()`.

## Fix Summary

- Measured STT duration once in `run_voice_loop()`.
- Passed `transcribe_ms`, `empty`, `raw_text`, and `normalized_text` into
  `record_stt_result()`.
- Passed `app`, `overlay_enabled`, and `speak_prompt=False` into
  `notify_low_confidence()`.
- Added focused tests proving diagnostics record before routing and
  low-confidence notification does not prevent the final transcript from routing.

## Audit Findings

Wakeword:
- Detector thread and cooldown gating exist.
- Wake sessions route through the shared voice transcript path.
- Next blocker: when continuous conversation is active,
  `effective_wake_listen_seconds()` can return 45s. The adjacent STT polish
  suite exposes this with `test_effective_wake_listen_default_cap`; not fixed in
  this patch because this task limited implementation to one highest-impact
  blocker.

Microphone recovery:
- Push-to-talk microphone errors use exponential backoff capped at 30s.
- The backoff prevents spin loops, but shutdown during a long backoff is still
  coarse-grained.

VAD and endpoint detection:
- Streaming endpoint detection uses RMS threshold plus trailing silence after
  speech and finalizes once.
- Simple RMS VAD is predictable and local, but noisy environments can still hurt
  endpoint quality.

STT:
- Wake path records STT diagnostics with timing correctly.
- Push-to-talk diagnostics contract was stale and is now fixed.
- No cloud STT was added.

TTS:
- Async worker/watchdog status paths exist.
- Historical command history still shows TTS/playback failures, but this patch
  does not alter TTS behavior.

Interruption handling:
- Streaming STT can barge in when speech starts during TTS.
- This patch does not change interruption policy or execution routing.

Latency:
- Historical p95 for voice/wake command duration is 5254 ms.
- Fixed push-to-talk path now emits finish/log latency again.
- The next high-latency target is the 45s continuous conversation wake-listen
  cap, followed by live TTS backend reliability.

---

# Voice-Hardening-2 — Wake listen window cap

Date: 2026-05-28

## Root cause

`effective_wake_listen_seconds()` in `voice/fast_voice.py` treated
`uses_continuous_conversation()` (config + runtime enabled) as sufficient to
return `CONVERSATION_TURN_MAX_SECONDS` (45s). After `audio_runtime_init` calls
`enable_human_conversational_runtime()`, discrete post-wake capture inherited the
long conversational turn limit even when no human session was active.

## Fix

- `resolve_wake_listen_seconds()` returns `WakeListenResolution` with
  `wake_listen_seconds`, `source`, and `mode` (`stable` | `discrete` |
  `conversational`).
- 45s applies only when `is_session_active()` is true (active human session).
- Discrete/stable wake capture uses `WAKE_MAX_LISTEN_SECONDS` (default 5s).
- Diagnostics logged in `wakeword_loop` and shown in `format_voice_performance_status()`.

## Files changed

| File | Change |
|------|--------|
| `voice/fast_voice.py` | Resolution helper; session-gated 45s |
| `voice/wakeword_loop.py` | Log source/mode at wake listen |
| `voice/performance_status.py` | Wake listen diagnostics line |
| `tests/test_stt_voice_polish.py` | Cap, session, env override tests |

## Before / after latency expectation

| Scenario | Before | After |
|----------|--------|-------|
| Stable/discrete wake capture (no active session) | up to **45s** | **5s** default (`WAKE_MAX_LISTEN_SECONDS`) |
| Active human conversational session | 45s | **45s** (`CONVERSATION_TURN_MAX_SECONDS`) |
| Env `WAKE_MAX_LISTEN_SECONDS=7.5` | ignored when conv enabled | **7.5s** discrete capture |

## Tests

```text
py -3 -m pytest tests/test_stt_voice_polish.py tests/test_voice_pipeline.py tests/test_phase596_session_handoff.py -q
```

Note: `tests/test_phase591_live_session.py` is not present; Phase 59.1 handoff
coverage uses `tests/test_phase596_session_handoff.py` and
`scripts/smoke_phase591_live_session.py`.
