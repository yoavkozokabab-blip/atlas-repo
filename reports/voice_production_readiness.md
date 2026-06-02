# Voice System Production Readiness

**Date:** 2026-05-29  
**Evidence source:** `voice/` directory, verified readings of `tts.py`, `voice_loop.py`, `microphone.py`, `wakeword_loop.py`, `voice_health.py`

---

## What the Voice System Is

The voice system is the primary I/O layer for J.A.R.V.I.S. It consists of:

1. **Wake word** — passive listener that activates on a trigger phrase
2. **STT (Speech-to-Text)** — converts audio to text using a local model
3. **TTS (Text-to-Speech)** — converts result text to audio
4. **Push-to-talk loop** — alternative to wake word; Enter to start/stop
5. **Streaming STT** — incremental transcription during capture (optional)
6. **Audio routing** — Windows audio device selection

---

## Section 1: Wake Word

### What Works
- `WakeWordDetector` spawns a background thread; on trigger, calls `_start_post_wake_session_thread()`
- Post-wake session runs in its own thread (`jarvis-wake-listen`) — does not block the main wake loop
- Session locking prevents overlapping wake sessions (`acquire_wake_listening_session()`)
- Cooldown enforced after each session (`effective_wake_cooldown_seconds()`)

### What Is Broken or Missing

**W-1: Wake word model dependency not validated at startup**  
`wakeword_loop.py:424`: `_detector.start()` returns `False` if the model is missing. This is logged as a warning and the system continues in push-to-talk only mode. This is acceptable behavior — but there is no startup health check that reports "wake word unavailable" to the user. The user must discover this themselves.  
**Fix:** Add `wake_word_available=False` to startup health report when model is absent.

**W-2: 7 files for one feature**  
`wake_word.py` and `wakeword.py` both exist. See Consolidation Plan C-4.  
**Fix:** Merge to 3 files (one detector, one loop, one diagnostics).

**W-3: False trigger rate not surfaced**  
`wake_diagnostics.py` tracks false triggers but the count is not included in the daily health report.  
**Fix:** Include false trigger rate in `show_voice_health()` output.

### Actual State
Wake word detection works as a feature. The main gap is operational visibility, not functionality.  
**Readiness: 70%**

---

## Section 2: STT (Speech-to-Text)

### What Works
- 5 engines available: faster-whisper (primary), ONNX whisper, Deepgram local, Parakeet, whisper.cpp
- `stt_engines/registry.py` handles engine selection and fallback
- 9-component post-processing stack: confidence fusion, language detect, transcript repair, multipass, etc.
- Streaming STT available via `voice/streaming_stt/`
- Per-session streaming disable on repeated failures

### What Is Broken or Missing

**S-1: Microphone overflow not tracked (`microphone.py:119–123`)**  
When audio overflows, chunks are still appended with no overflow marker. STT receives corrupted audio silently.  
**Impact:** Transcription quality degrades; errors are not attributed to microphone overflow.  
**Fix:** Track `overflow_count` in `CaptureStats`; log if > 0; include in STT result metadata.

**S-2: No end-to-end latency budget**  
`voice/latency_tracker.py` measures latency but does not enforce a budget. There is no alert if STT takes > 3s.  
**Impact:** STT slowdowns are invisible until the user notices the delay.  
**Fix:** Add a latency threshold check in `finish_and_log()`; log warning if total voice round-trip > 4s.

**S-3: 9-component serial pipeline — no profiling**  
The STT stack has 9 serial components (confidence fusion, language detect, transcript repair, intent correction, multipass, partial stream, retry pipeline, voice fingerprint, audio enhance). There is no per-component timing.  
**Impact:** If one component is slow, no diagnostic identifies which one.  
**Fix:** Add `time.perf_counter()` around each component in `stt_stack/stt_controller.py`; log component timing if total > 500ms.

**S-4: `streaming_policy_readable` acceptance test always passes regardless of streaming state** (from T-3 in truthfulness audit)  
**Fix:** See T-3.

### Actual State
STT works for most use cases. The streaming path has per-session disable on failure. Main gaps: silent overflow corruption, no latency enforcement.  
**Readiness: 65%**

---

## Section 3: TTS (Text-to-Speech)

### What Works
- `tts.py:TTSService.speak()` has a proper fallback chain: realtime → edge-tts → pyttsx3 subprocess → pyttsx3 direct
- TTS failures DO surface to user: `print(f"[TTS ERROR] {msg}")` + `notify_overlay_error()` (`tts.py:673–674`)
- Secret redaction before speech: `_SECRET_PATTERNS` in `tts.py:25–31`
- Cooldown period after timeout prevents rapid engine reset loops
- `_overlay_tts_warning()` always calls `notify_overlay_error()`

### What Is Broken or Missing

**T-1: pyttsx3 logic split across 4 files**  
`pyttsx3_lifecycle.py`, `pyttsx3_completion.py`, `engines/pyttsx3_engine.py`, `providers/pyttsx3_fallback.py`. State divergence between files is possible.  
**Fix:** Consolidation Plan C-2.

**T-2: TTS state split across 6 tracking modules**  
See Consolidation Plan C-3.

**T-3: No canonical TTS entry point**  
Code calls `tts_edge.py`, `tts_pyttsx3.py`, `tts_subprocess.py` directly in various places.  
**Fix:** All calls must go through `voice/engines/registry.py:EngineRegistry`.

**T-4: `tts_backend_reported` acceptance test always passes regardless of backend state** (T-4 in truthfulness audit)  
**Fix:** See T-4.

**T-5: TTS_ASYNC=True means speak() returns True before audio plays**  
Documented at `tts.py:148`. The return value is ambiguous.  
**Impact:** Callers cannot distinguish "TTS confirmed played" from "TTS queued (may fail)".  
**Fix:** Low priority; the current behavior is documented and failures are reported.

### Actual State
TTS works end-to-end with real error notification. Main gaps are code organization (multiple files for one library) and an ambiguous return value in async mode.  
**Readiness: 72%**

---

## Section 4: Microphone Recovery

### What Is Broken

**M-1: Microphone disconnect causes CPU-spin loop (VF-4 — verified)**  
**File:** `voice/voice_loop.py:194–203`  
```python
except MicrophoneError as exc:
    app.console.print(f"[red]Microphone error:[/] {exc}")
    ...
    finish_and_log()
    continue    # immediate retry — no sleep
```
When the microphone is disconnected, the loop hits `check_microphone_available()` → raises `MicrophoneError` → `continue` → immediately tries again. No `time.sleep()`. This spins at CPU speed until the mic is reconnected or the process is killed.  

**Fix:**
```python
except MicrophoneError as exc:
    app.console.print(f"[red]Microphone error:[/] {exc}")
    notify_overlay_error(str(exc))
    finish_and_log()
    time.sleep(min(2.0 ** mic_error_count, 30.0))  # backoff to 30s max
    mic_error_count += 1
    continue
```

**Impact of current bug:** 100% CPU on one core when mic is disconnected. Floods console. Flood-fills `observability_events.jsonl` (making the storage growth problem worse).

### What Works
- Wake word loop: `MicrophoneError` during wake session causes `return` (ends session); wake detector continues and will retry on next trigger. This is correct.
- `record_for_seconds()`: same pattern — `MicrophoneError` propagates to caller, who returns. Correct.
- Only `run_voice_loop()` has the spin bug.

**Readiness of mic recovery: 30%** (push-to-talk loop has a critical spin bug)

---

## Section 5: Endpoint Detection (Silence Stop)

### What Works
- `_record_stream()` supports `silence_stop=True` mode with configurable threshold, minimum duration, and post-speech buffer
- `_silence_stop_ready()` is a pure function with clear logic
- Wake sessions use `wake_early_stop_enabled()` and `effective_wake_silence_seconds()` for tuning

### What Is Broken or Missing

**E-1: RMS-based silence detection is brittle with background noise**  
`microphone.py:124`: `rms = float(np.sqrt(np.mean(indata.astype(np.float64) ** 2)))`. If background noise keeps RMS above `STT_SILENCE_THRESHOLD`, silence detection never triggers and recording runs to `max_seconds`.  
**Impact:** User must wait for `STT_RECORDING_MAX_SECONDS` every time there is fan noise or HVAC.  
**Fix:** Add adaptive threshold that calibrates to ambient noise on startup (measure 2s of silence, set threshold = ambient_rms * 1.5).

**Readiness of endpoint detection: 60%**

---

## Section 6: Interruption / Barge-In

### What Works
- `voice/conversational_runtime.py` has `barge_in_cancel()` and `recover_conversation_timeout()`
- These are checked in `_interruption_hooks()` acceptance case (genuinely verifies callability)
- `cancel_active_speech` intent exists and is mapped

### What Is Broken or Missing

**I-1: Barge-in is not wired in push-to-talk mode**  
In push-to-talk (`run_voice_loop`), TTS plays while the user cannot interrupt it. The barge-in path is only active in the conversational runtime (`voice/conversational_runtime.py`), which requires `HUMAN_CONVERSATIONAL_RUNTIME_ENABLED=true`.  
**Impact:** In default mode, if JARVIS is speaking a long response, the user cannot interrupt.

**I-2: No inter-word pause detection**  
STT waits for silence before routing. If JARVIS is speaking and user begins speaking simultaneously, the microphone captures TTS output mixed with the user's voice, degrading transcription.  
**Fix:** Mute microphone input during TTS playback (acoustic echo cancellation). This requires `pyaudio` stream coordination.

**Readiness of interruption: 40%**

---

## Section 7: Conversation Flow

### What Works
- Wake word → post-wake session → STT → Commander → TTS is a complete round-trip
- Push-to-talk → STT → Commander → TTS is complete
- Session memory records recent transcripts for follow-up resolution

### What Is Missing

**C-1: No multi-turn context in voice mode**  
The voice loop processes one command at a time. If the user says "show me the last 5 errors" and then says "explain the third one", the second command has no access to the numbered list from the first response.  
**Impact:** Voice UX is command-based, not conversational.  
**Fix:** Commander Agent should maintain a `last_result` buffer (in-process, not persisted) accessible by context-resolving classifiers.

**C-2: Greeting plays on every wake word detection**  
`wake_greeting.py` plays a greeting sound on every wake. In a session with many wake triggers, this becomes annoying.  
**Fix:** Play greeting only on first wake in a session (session = no wake in past 5 minutes).

---

## Actual Blocker List (What Prevents Natural Conversation)

Ranked by impact on user experience:

| Rank | Blocker | Severity | Evidence |
|------|---------|---------|---------|
| 1 | Mic disconnect causes CPU spin with no backoff | CRITICAL | `voice_loop.py:203`, VF-4 |
| 2 | Barge-in not wired in push-to-talk mode | HIGH | no wiring in `run_voice_loop` |
| 3 | No adaptive silence threshold — background noise breaks endpoint detection | HIGH | `microphone.py:124` |
| 4 | No multi-turn context — each command is isolated | HIGH | no `last_result` buffer |
| 5 | TTS and mic not coordinated — no echo cancellation | MEDIUM | simultaneous audio paths |
| 6 | Wake word model not reported in startup health | MEDIUM | `wakeword_loop.py:425` |
| 7 | STT component timing not measured | MEDIUM | no per-component profiling |
| 8 | Acceptance tests inflate voice readiness score | MEDIUM | T-1 through T-4 in truthfulness audit |

---

## Actual Readiness

| Component | Assessed | Score |
|-----------|---------|-------|
| Wake word detection | Works; missing startup visibility | 70% |
| STT accuracy | Works; no overflow tracking; no latency budget | 65% |
| TTS output | Works; error notification present; code fragmented | 72% |
| Microphone recovery | Critical CPU-spin bug on disconnect | 30% |
| Endpoint detection | Works; noise-sensitive | 60% |
| Interruption/barge-in | Only in optional conversational mode | 40% |
| Conversation flow | Command-based; no multi-turn | 45% |
| **Overall voice** | | **55%** |

The self-reported 65% in `product_readiness.py` is inflated by the four hardcoded-True acceptance cases.

---

*End of Voice Production Readiness — 2026-05-29*
