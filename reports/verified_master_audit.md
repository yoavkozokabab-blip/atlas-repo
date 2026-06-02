# Verified Master Audit

**Date:** 2026-05-29  
**Method:** Every finding verified against actual source files. No speculation.  
**Supersedes:** `master_audit.md` (which contained three incorrect claims)

---

## Corrected Claims (from master_audit.md)

| Incorrect claim | Correction | Evidence |
|----------------|-----------|---------|
| "Action registry silently drops actions with import errors" | Import error crashes startup entirely | `actions/registry.py:1–562` all module-level imports, no try/except |
| "TTS failure is silent to the user" | TTS failure triggers overlay error + console print | `voice/tts.py:673–674` |
| "Microphone disconnect kills voice permanently" | Loop continues; real issue is spin with no backoff | `voice/voice_loop.py:194–203` |

---

## Part 1: Dead Code

### Dead-1: `integrations/telegram_client.py` — 2 lines, no implementation
**File:** `integrations/telegram_client.py`
```python
"""Telegram notifications — optional integration."""
```
The entire file is a docstring. Any import of a function from this module raises `ImportError`.

### Dead-2: `voice/streaming/` directory contains only `mp3_frame.py`
The directory name implies a streaming subsystem. The actual streaming STT is in `voice/streaming_stt/` (a separate directory). `voice/streaming/mp3_frame.py` is a utility that stands alone and is not clearly referenced.

### Dead-3: `pass` statements in action `execute()` bodies
Silent no-ops in live code paths:
- `actions/diagnostics_actions.py:106` — bare `pass` in except block
- `actions/foundation_actions.py:273` — bare `pass` in except block
- `actions/phase60_actions.py:218` — bare `pass` in except block
- `actions/vision_actions.py:89, 178` — bare `pass` in except blocks
- `actions/voice_audio_actions.py:424, 754` — bare `pass` in except blocks

These are executed code paths that silently do nothing on failure. Different from dead code — they are live paths with silent error swallowing.

---

## Part 2: Duplicate Systems

### Dup-1: pyttsx3 logic in 4 files
`voice/pyttsx3_lifecycle.py`, `voice/pyttsx3_completion.py`, `voice/engines/pyttsx3_engine.py`, `voice/providers/pyttsx3_fallback.py`

### Dup-2: TTS state tracked in 6 modules
`tts_status.py`, `tts_watchdog.py`, `tts_output_policy.py`, `tts_playback_trace.py`, `tts_policy_trace.py`, `voice_debug_store.py`

### Dup-3: Wake word in 7 files
`wake_word.py`, `wakeword.py`, `wakeword_loop.py`, `wakeword_state.py`, `wake_diagnostics.py`, `wake_greeting.py`, `wake_phrases.py`

### Dup-4: Two acceptance frameworks
`reliability/hardening_core.py` (Phase 65) and `validation/framework.py` (Phase 66)

### Dup-5: Memory in 4 independent stores
`data/memory_store.json`, `data/session_memory.json`, `data/semantic_memory.json`, `data/memory.json` (legacy)

### Dup-6: OCR in two locations
`vision/ocr.py` and `desktop/ocr_pipeline.py` both wrap Tesseract.

### Dup-7: Browser memory in two locations
`browser/memory.py` (in-process) and `data/browser_memory.json` (persisted)

### Dup-8: Two screen understanding implementations in one file
`vision/screen_understanding.py` contains "v1" and current implementations

---

## Part 3: Duplicate Commands

The intent routing table in `agents/intent_routing.py` maps both `"browser"` and `"open_browser"` to `AgentId.OPERATOR` as prefix rules. This means any intent containing the word "browser" routes to Operator, which could cause unexpected routing for compound intent names.

### Dup-Cmd-1: `AgentId.OPERATOR` owns both browser AND desktop intents
The split into Browser Agent + Desktop Agent (see `final_agent_architecture.md`) will resolve this.

---

## Part 4: Duplicated Memory Paths

| Intent | Goes to | Memory store written |
|--------|---------|---------------------|
| `remember_preference` | `actions/memory_actions.py` | `brain/preferences.py` → `data/preferences.json` |
| `remember_fact` | `actions/memory_actions.py` | `memory/store.py` → `data/memory_store.json` |
| `remember_this` | `actions/knowledge_actions.py` | `memory/store.py` → `data/memory_store.json` |
| Session context | `memory/session_memory.py` | `data/session_memory.json` |

Preferences are in `data/preferences.json`, not in `memory_store.json`. A `forget("Alice")` on a preference does nothing because `forget()` only touches `memory_store.json`.

---

## Part 5: Duplicated Validation Systems

| System | File | What it validates |
|--------|------|-----------------|
| Intent allowlist | `core/security.py:35` | Intent must be in `ALLOWED_INTENTS` |
| Implementation check | `core/security.py:41` | Intent must be in `IMPLEMENTED_INTENTS` |
| Agent routing | `agents/intent_routing.py` | Intent maps to an agent |
| Task agent safety | `task_agent/safety.py` | Step command key must be allowlisted |
| Path write check | `task_agent/safety.py:path_write_allowed()` | Write target must be under `PROJECT_ROOT` |

These are not redundant — they serve different purposes. However, `ALLOWED_INTENTS` and `IMPLEMENTED_INTENTS` in `config.py` can drift. There is no startup check that verifies every entry in `IMPLEMENTED_INTENTS` has a registered handler in `ActionRegistry`.

---

## Part 6: Duplicated Recovery Systems

| Recovery | Module | Trigger |
|----------|--------|---------|
| TTS engine fallback | `voice/tts.py:_speak_blocking_legacy()` | engine exception |
| TTS async retry | `voice/tts.py:speak_async()._run()` | TTSError |
| Streaming STT disable | `voice/streaming_stt/session_policy.py` | `StreamingSttFallbackError` |
| Overlay restart | `ui/overlay_app.py` | Qt thread not alive |
| HealingEngine | `runtime/healing_engine.py` | health check failure |
| Watchdog restart | `services/watchdog.py` | process health |

These are not redundant — each handles a different failure mode. However, there is no central health model that aggregates them. The Health Monitor Agent addresses this.

---

## Part 7: Unused Modules

### Unused-1: `integrations/openai_client.py` — raises on every call
```python
# integrations/openai_client.py:10–13
def classify_intent(_prompt: str) -> dict:
    raise OpenAIClassifierNotConfiguredError(
        "OpenAI LLM classifier is not implemented. Use LLM_PROVIDER=ollama."
    )
```
This module exists only to raise an error. It can be deleted if OpenAI is not a planned integration.

### Unused-2: `voice/viseme_timeline.py`
Viseme timelines are animation cues for lip-sync. There is no visual avatar in JARVIS that uses them. This module may be dead.

### Unused-3: `voice/emotion_modes.py`
Emotion modes for TTS (cinematic, etc.) are referenced by `voice_stack_actions.py` but the actual emotion-modulated TTS path depends on REALTIME_TTS_EMOTION config. In default mode, this is unused.

---

## Part 8: Fake Success Paths

See `runtime_truthfulness_audit.md` for the complete list. Summary:

| ID | File | Line | Problem |
|----|------|------|---------|
| T-1 | `voice_health.py` | 98 | `lambda: (True, "spoken_normalization module available")` |
| T-2 | `voice_health.py` | 99 | `lambda: (True, "streaming buffer policy available")` |
| T-3 | `voice_health.py` | 73 | `_streaming_policy` hardcoded `True` |
| T-4 | `voice_health.py` | 79 | `_tts_backend` hardcoded `True` |
| T-5 | `memory_health.py` | 93 | `len(hits) >= 0` — always True |
| T-6 | `memory_health.py` | 97 | `return True, "updated"` — hardcoded |
| T-7 | `memory_health.py` | 101 | `n >= 0` — always True |
| T-8 | `memory_health.py` | 105 | `return True, ...` — hardcoded |
| T-9 | `memory_health.py` | 115 | `lambda: (True, ...)` — hardcoded |
| T-10 | `integrations_health.py` | 44 | passes when mock is active |
| T-12 | `product_readiness.py` | 19 | invented scores when `run_acceptance=False` |
| T-13 | `hardening_core.py` | 43 | `+10` bonus inflates score formula |

---

## Part 9: Mocked Implementations Pretending to Be Real

| System | File | Reality |
|--------|------|---------|
| Email integration | `providers/daily_summary_provider.py` | Mock; returns "MOCK MODE" string |
| Calendar integration | `providers/daily_summary_provider.py` | Mock; returns "MOCK MODE" string |
| Telegram notifications | `integrations/telegram_client.py` | Empty file |
| Browser (default) | `browser/runtime.py:23` | `provider="mock"` by default |
| OpenAI LLM classifier | `integrations/openai_client.py` | Raises on every call |

**Assessment:** The mock labeling for email, calendar, and browser is explicit and honest. The problem is that acceptance tests validate the mock as if it were production behavior (T-10).

---

## Part 10: Architecture Inconsistencies

### AI-1: Agent layer is metadata, not execution
The `agents/` directory is documented as "facade" (Phase 70). Agents do not intercept execution — they are used for routing metadata only. Every intent still executes through `ActionRegistry`. This is architecturally correct (see `final_agent_architecture.md`) but is not documented prominently.

### AI-2: `ALLOWED_INTENTS` and `IMPLEMENTED_INTENTS` can drift
`config.py:147` and `config.py:643` define two separate frozensets. They are manually maintained. There is no automated check that every entry in `IMPLEMENTED_INTENTS` has a corresponding handler in `ActionRegistry`.

### AI-3: Phase-numbered action files with no phase index
19 files named `phase45_actions.py` through `phase68_alpha_actions.py`. No `PHASES.md` or equivalent explaining what each phase was.

### AI-4: `HealingEngine` and `services/watchdog.py` overlap in responsibility
Both watch for system health and trigger recovery. No clear boundary between them.

---

## Part 11: Runtime Bottlenecks

### RB-1: `atomic_write_json` creates a backup on every write — 45 call sites
Every state write (hypothesis update, session save, notification, etc.) copies the existing file to `data/backups/`. With 45 call sites and multiple writes per command, this is disk I/O on the hot path.  
**Evidence:** `core/persistent_json.py:30–34`

### RB-2: `PersonalMemoryStore._load()` reads entire file on every operation
Every `remember()`, `forget()`, `list_visible()`, and `search()` call reads the full JSON file.  
**Evidence:** `memory/store.py:64–73`

### RB-3: `actions/registry.py` — 558 class imports at module load
All 558 action class imports happen when `registry.py` is first imported. Startup time increases linearly with the number of action classes.  
**Evidence:** `actions/registry.py:1–562`

### RB-4: STT stack has 9 serial components with no profiling
Pipeline latency not measured per-component.  
**Evidence:** `voice/stt_stack/` — 9 module files, no timing in `stt_controller.py`

---

## Part 12: Storage Growth Risks (Verified)

| File/Directory | Current size | Growth mechanism | Rotation |
|---------------|-------------|-----------------|---------|
| `data/backups/` | 66 MB, 2,522 files | `atomic_write_json()` writes backup per write | None |
| `data/observability_events.jsonl` | 6.2 MB, 59,691 lines | `observability.py:355` — `open("a")` append | None |
| `data/command_history.jsonl` | 1.8 MB, 4,019 lines | `router.py:447` — `open("a")` append | None |
| `data/memory_store.json` | Growing | Every `remember()` appends an entry | No vacuum |
| `data/desktop_screenshots/` | Unknown | Every `take_screenshot` intent adds a PNG | None |

---

## Part 13: Memory Growth Risks

| Risk | Source |
|------|--------|
| Expired memory entries never deleted | `store.py:175` skips on read, never deletes |
| Hidden (soft-deleted) entries never deleted | `store.py:160` sets `hidden=True`, never removes |
| Session memory not integrated with TTL | `session_memory.py` independent store, no expiry |
| Semantic memory grows without bound | `data/semantic_memory.json` — no pruning |

---

## Part 14: Observability Gaps

### OG-1: No structured alert routing
Health issues are logged but not routed to a central alert handler. The overlay shows errors but there is no email/SMS/Telegram notification path (Telegram is empty).

### OG-2: Microphone overflow not tracked
`microphone.py:119–123` — audio callback ignores `status != 0`.

### OG-3: Runtime monitor status is a cached file, not a live signal
`data/runtime_monitor_status.json` may reflect a dead monitor.

### OG-4: No per-agent latency tracking
`voice/latency_tracker.py` tracks voice round-trip. No equivalent for memory, browser, desktop.

---

## Part 15: Reliability Gaps

### RG-1: Mic disconnect CPU spin (VF-4, verified, critical)
### RG-2: No backoff on any retry in the voice path except TTS
TTS has a cooldown (`_last_timeout_monotonic`). STT has per-session disable. Mic loop has no backoff.

### RG-3: Thread death not detected
No thread registry; no watchdog for daemon threads.

### RG-4: `config.py` load failure crashes everything
All 787 Python files import from `config.py`. No startup isolation.

### RG-5: `ActionRegistry` import failure crashes startup
558 module-level imports. One broken action module = full crash.

---

## Severity Summary

| Category | Count | Most Severe |
|----------|-------|------------|
| Verified storage growth risks | 5 | P0: backup 66 MB, no retention |
| Fake acceptance passes | 13 | P1: 9 in voice+memory, 1 in integrations |
| Dead code | 3 | P3: telegram_client.py |
| Duplicate systems | 8 | P2: 4 memory stores, 4 pyttsx3 files |
| Mocked pretending real | 3 | P1: integrations acceptance |
| Runtime bottlenecks | 4 | P2: atomic_write_json on hot path |
| Reliability gaps | 5 | P1: mic spin, no thread watchdog |

---

*End of Verified Master Audit — 2026-05-29*
