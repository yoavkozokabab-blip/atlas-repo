# Human Conversation Runtime

**Date:** 2026-05-28  
**Goal:** JARVIS feels like a real human conversation — interrupt anytime, remember context, natural follow-ups, faster spoken responses.

**Hardening pass:** wired `.env.example`, measured active-TTS barge-in, optimized cancel path, regression test + smoke under simulated playback.

---

## Features

### 1. User interruption (immediate)

- `voice/human_conversation.interrupt_on_user_speech_start()` pauses playback, cancels active realtime TTS, then notifies recovery hooks on a **deferred thread** (not on the hot path).
- Wired from streaming STT, continuous mic partials, streaming pipeline, and semantic interruption handler.
- Target cancel latency: **&lt;200ms** (`HUMAN_BARGE_IN_TARGET_MS`, default 200).

### 2. Barge-in

- No wait for sentence endpoint — first VAD/speech energy triggers cancel.
- Re-entrancy guard (`is_barge_in_active()`) prevents recursive interrupt loops via semantic stream handler.
- Provider cancel clears `_active_cancel` before invoking callback (idempotent); provider hook no longer re-enters full `interruption_manager.cancel()`.

### 3. Conversation memory window

- `CONVERSATION_MAX_TURNS` default **20** (configurable).
- Classifier context uses last **8** turns (`CONVERSATION_CLASSIFY_CONTEXT_TURNS`).
- `memory_runtime` keeps up to **20** turn reference strings.

### 4. Natural follow-ups

- `conversation/follow_up_resolver.py` expands phrases before classify:
  - "tell me more" → continues last topic
  - "compare it to Nvidia" → compare last subject to Nvidia
  - "what about the second one?" → prior user turn by ordinal
- Integrated with existing `reformulate_with_context()` graph rules.

### 5. Streaming response

- `conversation/llm_streaming.py` yields **clause-sized** chunks early (`CONVERSATION_STREAM_FIRST_CHUNK_CHARS`, `CONVERSATION_STREAM_MIN_CHARS`) so TTS starts sooner.

---

## Configuration (.env / .env.example)

| Variable | Default | Purpose |
|----------|---------|---------|
| `HUMAN_CONVERSATIONAL_RUNTIME_ENABLED` | true | Phase 59 conversational voice runtime |
| `CONVERSATION_MAX_TURNS` | 20 | Persisted turn window |
| `CONVERSATION_CLASSIFY_CONTEXT_TURNS` | 8 | Turns shown to classifier |
| `HUMAN_BARGE_IN_TARGET_MS` | 200 | Barge-in latency budget (hot path only) |
| `CONVERSATION_TARGET_INTERRUPT_PAUSE_MS` | 100 | Human-interruption pause metric target |
| `CONVERSATION_STREAM_MIN_CHARS` | 28 | Steady-state speak chunk size |
| `CONVERSATION_STREAM_FIRST_CHUNK_CHARS` | 18 | First spoken chunk sooner |

---

## Barge-in cancel path (optimized)

**Hot path (measured):**

1. `pause_playback_immediately()` + `request_stop_speaking()` — stop device playback first.
2. `cancel_active_speech()` — snap/clear active provider cancel, run once, idempotent on repeat.
3. Record `get_last_barge_in_cancel_ms()` — **excludes** deferred hooks.

**Deferred (not counted toward barge-in budget):**

- `on_user_speech_during_tts(playback_already_stopped=True)` — state preservation, metrics, overlay.

**Files touched for latency:**

| File | Change |
|------|--------|
| `voice/human_conversation.py` | Hot path + reentrancy guard + deferred notify |
| `voice/realtime_tts.py` | Idempotent cancel; provider `_cancel_current` avoids nested manager cancel |
| `voice/human_interruption.py` | `playback_already_stopped` skips duplicate pause/cancel |
| `voice/interruption_manager.py` | Same flag; skips semantic re-interrupt |
| `conversation/semantic_stream/interruption_handler.py` | Skips nested `interrupt_on_user_speech_start` when active |

---

## Verification results (2026-05-28)

### Unit / regression tests

```text
cd c:\J.A.R.V.I.S\local_jarvis
py -3 -m pytest tests/test_human_conversation.py -q
```

**Result:** `8 passed` in 1.67s

Includes `test_active_tts_barge_in_under_target_ms` — simulated active playback (`_speaking` set + `register_active_cancel_for_tests`) proves hot-path cancel **&lt; 200ms**.

### Extended voice regression

```text
py -3 -m pytest tests/test_human_conversation.py tests/test_phase592_conversational_tts.py tests/test_phase596_session_handoff.py tests/test_stt_voice_polish.py -q
```

**Result:** `34 passed` in 82.72s

### Human conversation smoke (active TTS)

```text
py -3 scripts/smoke_human_conversation.py
```

**Result:** `SMOKE PASS human_conversation`

```
OK active-TTS barge-in cancel_ms=0.0
OK follow-up: 'continuation_compare' -> 'compare live vs backtest to nvidia'
OK early chunk: 'Hello there,'
OK classify context turns=8 max=20
```

### Full app smoke

```text
py -3 main.py --smoke
```

**Result:** `Smoke overall: PASS` (config, imports, wake word, mic, overlay)

### Voice / runtime smoke scripts

| Command | Result |
|---------|--------|
| `py -3 scripts/smoke_phase59.py` | PASS |
| `py -3 scripts/smoke_phase592_speech_output.py` | PASS |
| `py -3 scripts/smoke_phase60_voice_session.py` | PASS |
| `py -3 scripts/smoke_phase591_live_session.py` | **FAIL** — pre-existing: patches removed `effective_wake_listen_seconds` (renamed to `resolve_wake_listen_seconds`) |
| `py -3 scripts/smoke_phase57.py` | **FAIL** — pre-existing: `speak_realtime` mock provider assertion (`mock_stream`) |
| `py -3 scripts/smoke_phase58.py` | **FAIL** — pre-existing: `mock_ws` provider assertion |

Human-conversation changes did not modify those scripts; failures are environment/API drift unrelated to barge-in hardening.

### Latency notes

| Scenario | cancel_ms | Notes |
|----------|-----------|-------|
| No active TTS (old smoke) | ~300–335 | Measured full path **before** deferral; hooks + `sounddevice.stop()` dominated |
| Simulated active TTS (test + smoke) | **0.0** (smoke) / **&lt;200** (test) | Hot path only; provider cancel invoked |
| Production hardware | varies | Use `get_last_barge_in_cancel_ms()` logs; deferred hook INFO lines are expected after cancel |

---

## Tests & smoke (quick reference)

```text
py -3 -m pytest tests/test_human_conversation.py -q
py -3 scripts/smoke_human_conversation.py
py -3 main.py --smoke
```

Related regression suites:

```text
py -3 -m pytest tests/test_phase592_conversational_tts.py tests/test_phase596_session_handoff.py -q
```

Test hook for active stream simulation:

```python
from voice.realtime_tts import register_active_cancel_for_tests
register_active_cancel_for_tests(lambda: ...)  # provider teardown stub
```

---

## Files

| File | Role |
|------|------|
| `voice/human_conversation.py` | Unified fast interrupt entry |
| `conversation/follow_up_resolver.py` | Follow-up text expansion |
| `conversation/context_store.py` | 20-turn store + richer classify context |
| `conversation/llm_streaming.py` | Early clause/sentence chunking |
| `brain/intent_classifier.py` | Applies follow-up expansion in `classify()` |
| `.env.example` | Human conversation env vars documented |
