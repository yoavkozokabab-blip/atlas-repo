# Runtime Truthfulness Audit

**Date:** 2026-05-29  
**Method:** Every item backed by file:line:code evidence.  
**Scope:** Every place where success is reported without proof, readiness is estimated, health is assumed, or tests can pass without real execution.

---

## Category 1: Hardcoded-True Acceptance Cases

These acceptance test cases return `True` regardless of actual system state.

### T-1 `long_sentence_normalization` — always passes
**File:** `reliability/voice_health.py:98`
```python
run_case("long_sentence_normalization", lambda: (True, "spoken_normalization module available")),
```
**Problem:** The string `"spoken_normalization module available"` is hardcoded. The normalization module is never called. The case passes even if the module is broken.  
**Fix:** Call `spoken_normalization.normalize("Hello, this is a long sentence that tests normalization.")` and assert the result is non-empty.

### T-2 `paragraph_transcription_path` — always passes
**File:** `reliability/voice_health.py:99`
```python
run_case("paragraph_transcription_path", lambda: (True, "streaming buffer policy available")),
```
**Problem:** Same pattern. Never tests the STT buffer.  
**Fix:** Call `is_streaming_stt_enabled_for_session()` and assert it is `True` OR report `False` as a failure.

### T-3 `streaming_policy_readable` — always passes regardless of streaming state
**File:** `reliability/voice_health.py:70–73`
```python
def _streaming_policy() -> tuple[bool, str]:
    from voice.streaming_stt.session_policy import get_streaming_disable_reason, is_streaming_stt_enabled_for_session
    return True, f"enabled={is_streaming_stt_enabled_for_session()} reason={get_streaming_disable_reason() or 'none'}"
```
**Problem:** Returns `True` unconditionally. If streaming is disabled due to repeated errors, `enabled=False` appears in the detail string but the case still `PASS`es.  
**Fix:** `return is_streaming_stt_enabled_for_session(), f"..."`

### T-4 `tts_backend_reported` — always passes regardless of backend state
**File:** `reliability/voice_health.py:75–79`
```python
def _tts_backend() -> tuple[bool, str]:
    from voice.audio_status import get_audio_status
    audio = get_audio_status()
    return True, f"backend={audio.selected_verified_audio_backend or audio.last_provider or 'unverified'}"
```
**Problem:** Returns `True` even when backend is `"unverified"` — meaning no confirmed audio output path exists.  
**Fix:** `ok = bool(audio.selected_verified_audio_backend); return ok, f"backend=..."`

### T-5 `semantic_retrieve` — tautology
**File:** `reliability/memory_health.py:91–93`
```python
def _semantic() -> tuple[bool, str]:
    hits = store.semantic_search(tag, limit=3)
    return len(hits) >= 0, f"semantic_hits={len(hits)}"
```
**Problem:** `len(list) >= 0` is a Python invariant. This case can never fail.  
**Fix:** `return len(hits) > 0, f"semantic_hits={len(hits)}"`

### T-6 `update` — hardcoded True
**File:** `reliability/memory_health.py:95–97`
```python
def _update() -> tuple[bool, str]:
    store.remember(f"phase65 test {tag} updated", category="session", tags=["phase65", remembered_id])
    return True, "updated"
```
**Problem:** Calls `remember()` but ignores its return value. If `remember()` raises, the exception is caught by `run_case` and the case fails — but if it silently returns a bad entry, this case still reports `True`.  
**Fix:** `entry = store.remember(...); return bool(entry and entry.entry_id), entry.entry_id if entry else "no entry"`

### T-7 `forget` — tautology
**File:** `reliability/memory_health.py:99–101`
```python
def _forget() -> tuple[bool, str]:
    n = store.forget(tag)
    return n >= 0, f"hidden={n}"
```
**Problem:** `forget()` returns `int` (count of hidden entries). An integer is always `>= 0`. If the tag was not found, `n=0`, but the case passes.  
**Fix:** `return n > 0, f"hidden={n}"` — the test should verify the entry was actually found and hidden.

### T-8 `duplicate_detection` — hardcoded True
**File:** `reliability/memory_health.py:103–105`
```python
def _dup_detect() -> tuple[bool, str]:
    d = _diagnostics()
    return True, f"duplicates={d['duplicates']}"
```
**Problem:** Always passes. The duplicate count is logged but never checked.  
**Fix:** `return d['duplicates'] == 0, f"duplicates={d['duplicates']}"` — or define an acceptable threshold.

### T-9 `ranking_diagnostics` — hardcoded True
**File:** `reliability/memory_health.py:115`
```python
run_case("ranking_diagnostics", lambda: (True, show_memory_ranking_diagnostics()[:120])),
```
**Problem:** Calls `show_memory_ranking_diagnostics()` for display, ignores its content.  
**Fix:** Parse stale entry count from diagnostics; fail if stale > threshold.

---

## Category 2: Mock Pretending to Be Real

### T-10 Integrations acceptance validates mock mode
**File:** `reliability/integrations_health.py:7, 42–58`
```python
_MOCK_MARKER = "MOCK MODE"

def _inbox() -> tuple[bool, str]:
    body = summarize_my_inbox(20)
    return _MOCK_MARKER in body and "urgent" in body.lower(), "mock read-only"
```
**Problem:** All four integration cases pass specifically when the output contains `"MOCK MODE"`. A real integration would not contain this string and would fail the test. The test validates that the system is in mock mode, not that it is production-ready.  
**Fix:** `if live_credentials_present(): return test_real_api(); else: return None, "SKIP"`. Update `run_case()` to handle `None` as SKIP rather than PASS or FAIL.

### T-11 `browser/runtime.py` defaults to `provider="mock"` with no warning
**File:** `browser/runtime.py:14, 23`
```python
_MOCK_BANNER = "MOCK MODE | NO REAL EXTERNAL ACCESS | SIMULATED OUTPUT ONLY"

@dataclass
class BrowserRuntimeState:
    provider: str = "mock"
```
**Problem:** The browser runtime defaults to mock mode. If Playwright is not installed (which is the common case), all browser actions silently return simulated output. The `_MOCK_BANNER` string is present in output but users may not notice it.  
**What is correct:** The mock banner is present and labeled. This is truthful.  
**What to improve:** Startup health check should explicitly report `browser=mock` in the status display so the user is aware on launch.

---

## Category 3: Estimated Readiness Scores

### T-12 Hardcoded fallback scores
**File:** `reliability/product_readiness.py:17–28`
```python
def collect_all_track_scores(*, run_acceptance: bool = True) -> list[TrackScore]:
    if not run_acceptance:
        return [
            TrackScore("Voice", 65.0, 85.0),
            TrackScore("Memory", 55.0, 85.0),
            TrackScore("Browser", 65.0, 85.0),
            TrackScore("Desktop Operator", 50.0, 80.0),
            TrackScore("Coding Assistant", 78.0, 90.0),
            TrackScore("Integrations", 12.0, 60.0),
            TrackScore("Reliability", 58.0, 85.0),
            TrackScore("Performance", 62.0, 85.0),
        ]
```
**Problem:** If `run_acceptance=False`, the function returns invented numbers. These numbers will appear in any report generated without running acceptance tests. There is no indication in the output that these are estimates, not measurements.  
**Fix:** If `run_acceptance=False`, return scores of `0.0` with `detail="not measured"`. Never return an invented number as a score.

### T-13 `TrackScore.finalize_score()` adds a bonus for passing rate ≥ 90%
**File:** `reliability/hardening_core.py:40–43`
```python
def finalize_score(self) -> None:
    rate = self.pass_rate
    self.current_pct = round(min(100.0, max(0.0, rate * 0.85 + (10 if rate >= 90 else 0))), 1)
```
**Problem:** At 90% pass rate, the score becomes `90 * 0.85 + 10 = 86.5`. At 100% pass rate: `100 * 0.85 + 10 = 95`. The `+10` bonus means a test suite with 4 hardcoded-True cases (as in voice_health.py) can score 86.5% even though 4 of 7 cases never actually test behavior. This is score inflation through formula.  
**Fix:** Remove the `+10` bonus. Use `self.current_pct = round(rate, 1)` — the pass rate is the score.

---

## Category 4: Health Assumed, Not Checked

### T-14 Voice health check imports but does not verify function behavior
**File:** `reliability/voice_health.py:81–84`
```python
def _interruption_hooks() -> tuple[bool, str]:
    from voice.conversational_runtime import barge_in_cancel, recover_conversation_timeout
    return callable(barge_in_cancel) and callable(recover_conversation_timeout), "hooks present"
```
**Assessment:** This is acceptable. `callable()` is a real check (the import would raise if the module is broken, and `callable()` verifies the object is a function). This is not a fake pass — it is a structural check.

### T-15 `_cfg_ok` passes even with all voice disabled
**File:** `reliability/voice_health.py:66–68`
```python
def _cfg_ok() -> tuple[bool, str]:
    ok = bool(config.VOICE_ENABLED or config.WAKE_WORD_ENABLED or config.TTS_ENABLED)
    return ok, f"voice={config.VOICE_ENABLED} wake={config.WAKE_WORD_ENABLED} tts={config.TTS_ENABLED}"
```
**Assessment:** Correctly designed. If all three are False, `ok=False`. This check is truthful.

### T-16 Runtime monitor status read without verifying the monitor is actually running
**File:** `reliability/system_health.py` (inferred from health architecture)  
**Problem:** `runtime_health_score()` reads `data/runtime_monitor_status.json` — a cached file. If the runtime monitor thread has died, this file shows the last known healthy state, not the current state.  
**Fix:** Add a thread-alive check for the runtime monitor thread before trusting the cached status.

---

## Category 5: Fallback Behavior That Inflates Metrics

### T-17 `speak_async()` returns True before TTS completes
**File:** `voice/tts.py:146–148`
```python
if cfg.TTS_ASYNC:
    self.speak_async(safe)
    return True  # queued; failures recorded via tts_status + console warning
```
**Assessment:** This is an intentional design choice with known tradeoffs. The comment is accurate. TTS failures ARE reported subsequently (lines 671–674). This is not a false success — it is a "queued" success.  
**Improvement:** The `True` return value should be `"queued"` or a distinct `TTS_QUEUED` status so callers can distinguish from confirmed playback. Current state is acceptable but ambiguous.

### T-18 `_record_stream` audio callback swallows non-zero status
**File:** `voice/microphone.py:119–123`
```python
def callback(indata, _frames, _time, status) -> None:
    if status:
        logger.warning("Audio status: %s", status)
    chunks.append(indata.copy())
```
**Problem:** When `status` is non-zero (e.g., `InputOverflow`), the audio chunk is still appended. An `InputOverflow` means audio data was dropped. The STT engine receives a recording with gaps but has no way to know this. Transcription quality degrades silently.  
**Fix:** Track `overflow_count` in `CaptureStats`; expose it to the STT pipeline; log a warning if `overflow_count > 0`.

---

## Summary: What Must Change Before Readiness Scores Are Trustworthy

| ID | File | Change | Priority |
|----|------|--------|---------|
| T-1 | `voice_health.py:98` | Replace lambda with real normalization test | P1 |
| T-2 | `voice_health.py:99` | Replace lambda with real STT buffer check | P1 |
| T-3 | `voice_health.py:71` | Return `is_streaming_stt_enabled_for_session()` not `True` | P1 |
| T-4 | `voice_health.py:78` | Return `bool(verified_backend)` not `True` | P1 |
| T-5 | `memory_health.py:93` | `len(hits) > 0` not `>= 0` | P1 |
| T-6 | `memory_health.py:97` | Check `entry.entry_id` not hardcode `True` | P1 |
| T-7 | `memory_health.py:101` | `n > 0` not `>= 0` | P1 |
| T-8 | `memory_health.py:105` | Check duplicate count == 0 | P2 |
| T-9 | `memory_health.py:115` | Parse stale count from diagnostics | P2 |
| T-10 | `integrations_health.py:44` | SKIP when no credentials; test real when present | P1 |
| T-12 | `product_readiness.py:19` | Return `0.0` not hardcoded scores when `run_acceptance=False` | P1 |
| T-13 | `hardening_core.py:43` | Remove `+10` score inflation bonus | P1 |
| T-16 | `system_health.py` | Verify monitor thread alive before trusting cached status | P2 |
| T-18 | `microphone.py:122` | Track overflow count; expose to STT | P2 |

---

*End of Runtime Truthfulness Audit — 2026-05-29*
