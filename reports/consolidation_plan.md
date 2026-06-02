# Consolidation Plan

**Date:** 2026-05-29  
**Method:** Every duplicate system identified by reading source files.  
**Rule:** Only consolidate systems that are provably redundant. Do not merge for aesthetic reasons.

---

## C-1: Operator Agent → Browser Agent + Desktop Agent

**Current:** `agents/operator_agent.py` owns both browser and desktop.  
**Problem:** The two domains have nothing in common at the implementation level. Browser touches `browser/`, `websites/`. Desktop touches `vision/`, `computer_control/`, `desktop/`, `apps/`. Combining them in one agent gives each no clear boundary.  
**Action:** Extract `agents/browser_agent.py` and `agents/desktop_agent.py` from `agents/operator_agent.py`. Keep `OperatorAgent` as a compatibility shim for one release, then delete it.  
**Effort:** 1 day. **Risk:** Low (pure rename/split).

---

## C-2: pyttsx3 Implementation — 4 Files Into 1

**Current files, all managing the same library:**

| File | Role |
|------|------|
| `voice/pyttsx3_lifecycle.py` | Engine lifecycle (init/destroy) |
| `voice/pyttsx3_completion.py` | Completion wait logic |
| `voice/engines/pyttsx3_engine.py` | Engine class |
| `voice/providers/pyttsx3_fallback.py` | Fallback provider wrapper |

**Problem:** State for one library split across 4 files. Engine init in `lifecycle.py`, completion in `completion.py`, class in `engines/pyttsx3_engine.py`. This is how you get subtle bugs where two files disagree on whether the engine is initialised.  
**Action:** Merge all four into `voice/engines/pyttsx3_engine.py`. Delete the other three. Update `voice/tts.py` imports.  
**Effort:** 4 hours. **Risk:** Medium (requires tracing all call sites).

---

## C-3: TTS State — 6 Tracking Modules Into 1

**Current files tracking overlapping TTS state:**

| File | What it tracks |
|------|---------------|
| `voice/tts_status.py` | Run count, failure count per provider |
| `voice/tts_watchdog.py` | Speak session timing, timeout |
| `voice/tts_output_policy.py` | Whether TTS is allowed to fire |
| `voice/tts_playback_trace.py` | Backend selection decisions |
| `voice/tts_policy_trace.py` | Policy decision log |
| `voice/voice_debug_store.py` | Debug state dump |

**Problem:** No single file knows the full TTS state. `tts.py` imports from all six. A bug in TTS state means checking six files.  
**Action:** Create `voice/tts_state.py` with a single `TTSState` dataclass. Migrate all state reads/writes into it. Keep the existing module names as thin wrappers for one release (re-export from `tts_state`), then delete them.  
**Effort:** 2 days. **Risk:** Medium.

---

## C-4: Wake Word — 7 Files Into 2

**Current files:**

| File | Role |
|------|------|
| `voice/wake_word.py` | Wake detector (older) |
| `voice/wakeword.py` | Wake detector (newer) |
| `voice/wakeword_loop.py` | Post-wake listening session |
| `voice/wakeword_state.py` | State tracking |
| `voice/wake_diagnostics.py` | Diagnostics |
| `voice/wake_greeting.py` | Greeting on wake |
| `voice/wake_phrases.py` | Phrase list |

**Problem:** `wake_word.py` and `wakeword.py` are two implementations of the same concept. `wakeword_state.py` is a separate module for state that could live in the detector.  
**Action:** Merge `wake_word.py` + `wakeword.py` + `wakeword_state.py` into `voice/wake_word.py` (canonical). Keep `wakeword_loop.py` (it has a clear separate responsibility: post-wake session). Keep `wake_diagnostics.py`. Merge `wake_greeting.py` + `wake_phrases.py` into `voice/wake_greeting.py`.  
**Result:** 7 files → 3 files (`wake_word.py`, `wakeword_loop.py`, `wake_diagnostics.py`).  
**Effort:** 4 hours. **Risk:** Low.

---

## C-5: Memory Stores — Unify Access Through PersonalMemoryStore

**Current stores:**

| File | Content | Access |
|------|---------|--------|
| `data/memory_store.json` | Personal facts, preferences | `memory/store.py` |
| `data/session_memory.json` | Session context | `memory/session_memory.py` |
| `data/semantic_memory.json` | Embeddings | `memory/semantic_runtime.py` |
| `data/memory.json` | Legacy facts | `brain/memory.py` |

**Problem:** `forget("Alice")` removes from `memory_store.json` only. The same entry in `session_memory.json` remains. Semantically, there are four independent databases for one concept: "things JARVIS knows about the user."  
**Action:**  
1. `session_memory.py` writes through `PersonalMemoryStore.remember(category="session")` instead of its own JSON.  
2. `brain/memory.py` (legacy) redirects all writes to `PersonalMemoryStore.add_memory()` (already exists as a shim).  
3. `semantic_runtime.py` remains separate (it stores embeddings, not facts) but `upsert_entry()` is called by `PersonalMemoryStore.remember()` — this is already implemented at `store.py:131–143`.  
4. Delete `data/memory.json` after migration.  
**Effort:** 2 days. **Risk:** Medium (migration must handle existing data).

---

## C-6: Two Competing Acceptance Frameworks

**Current files:**

| File | Framework |
|------|-----------|
| `reliability/hardening_core.py` | Phase 65 framework (`TrackScore`, `run_case`, `AcceptanceCase`) |
| `validation/framework.py` | Phase 66 framework (`CategoryMeasurement`, `ScenarioRecord`) |

**Problem:** Both exist. All `reliability/*.py` files import from `hardening_core`. `validation/` is a newer, more rigorous framework but is not wired to the main acceptance runner.  
**Action:**  
1. Migrate `reliability/voice_health.py`, `memory_health.py`, etc. to `validation/framework.py`.  
2. Delete `reliability/hardening_core.py`.  
3. Update `generate_product_readiness_report()` to use `validation/framework.py` exclusively.  
**Effort:** 1 day. **Risk:** Low (framework API is similar; mainly a re-import).

---

## C-7: Phase-Numbered Action Files → Domain Names

**Current:** 19 files named `phase45_actions.py` through `phase68_alpha_actions.py`.  
**Problem:** `phase45_actions.py` is 755 lines covering trading investigation. `phase68_alpha_actions.py` is 33 lines. There is no way to know what a phase number means without reading the file.  

**Rename map (verified against file contents):**

| Current | Rename to |
|---------|-----------|
| `phase45_actions.py` | `investigation_actions.py` |
| `phase49_actions.py` | `healing_actions.py` |
| `phase50_actions.py` | `operational_status_actions.py` |
| `phase51_actions.py` | `workspace_switch_actions.py` |
| `phase52_actions.py` | `task_control_actions.py` |
| `phase53_actions.py` | `session_resume_actions.py` |
| `phase54_actions.py` | `intelligence_actions.py` |
| `phase55_actions.py` | `root_cause_actions.py` |
| `phase56_actions.py` | `conversation_project_actions.py` |
| `phase57_actions.py` | `realtime_voice_actions.py` |
| `phase58_actions.py` | `streaming_actions.py` |
| `phase59_actions.py` | `conversation_runtime_actions.py` |
| `phase60_actions.py` | `browser_email_calendar_actions.py` |
| `phase62_browser_actions.py` | `browser_search_actions.py` |
| `phase63_desktop_actions.py` | `desktop_vision_actions.py` |
| `phase65_hardening_actions.py` | `health_readiness_actions.py` |
| `phase67_balance_actions.py` | `balance_check_actions.py` |
| `phase68_alpha_actions.py` | `alpha_actions.py` |

**Process:** Rename files, update `actions/registry.py` imports, run startup validation.  
**Effort:** 2 days. **Risk:** Low if startup validation catches any missed import.

---

## C-8: Vision/OCR — Deduplicate Screen Understanding

**Current:**

| File | Role |
|------|------|
| `vision/ocr.py` | Tesseract OCR |
| `vision/screen_ocr.py` | Screen-specific OCR wrapper |
| `vision/screen_understanding.py` | Contains "v1" and "v35" implementations |
| `vision/context_engine.py` | Screen context aggregation |
| `vision/screen_analyzer.py` | Analysis pipeline |
| `vision/screen_system.py` | System-level screen info |
| `desktop/ocr_pipeline.py` | Desktop-specific OCR |

**Problem:** `screen_understanding.py` contains two distinct implementations. `desktop/ocr_pipeline.py` duplicates `vision/ocr.py`.  
**Action:**  
1. Remove the "v1" implementation from `screen_understanding.py`; keep only the current version.  
2. Delete `desktop/ocr_pipeline.py`; have `desktop/` import from `vision/ocr.py`.  
**Effort:** 4 hours. **Risk:** Low.

---

## C-9: Health Check Systems — 3 Into 1

**Current health systems:**

| System | File | What it checks |
|--------|------|---------------|
| `HealthReport` / `run_jarvis_health_check` | `services/health.py` | Startup checks (Tesseract, Ollama, microphone, etc.) |
| `TrackScore` / acceptance runners | `reliability/` | Per-subsystem readiness scores |
| `HealingEngine` | `runtime/healing_engine.py` | Autonomous recovery actions |

**Problem:** Three separate health models produce three separate reports with no shared data model. A developer looking at system health must check three places.  
**Action:**  
1. `services/health.py` becomes the single `HealthReport` data model.  
2. Acceptance runners in `reliability/` produce `HealthCheckItem` entries that are fed into the main `HealthReport`.  
3. `HealingEngine` reads from the `HealthReport` to decide what to recover.  
4. All three are wired through the new `Health Monitor Agent`.  
**Effort:** 2 days. **Risk:** Medium.

---

## C-10: Browser Memory Duplication

**Current:**

| File | What it stores |
|------|---------------|
| `browser/memory.py` | In-process page visit cache |
| `data/browser_memory.json` | Persisted page summaries |
| `data/browser_action_replay.jsonl` | Action replay log |

**Problem:** Page summaries exist both in `browser/memory.py`'s in-process dict and in `data/browser_memory.json`. On startup, the in-process cache is empty; `browser_memory.json` is loaded separately.  
**Action:** `browser/memory.py` becomes a write-through cache over `data/browser_memory.json`. Remove the separate load logic. The replay log (`browser_action_replay.jsonl`) stays separate (it's an audit trail, not a cache).  
**Effort:** 2 hours. **Risk:** Low.

---

## Priority Order

| Priority | Consolidation | Effort | Risk |
|----------|-------------|--------|------|
| P1 | C-5: Memory store unification | 2 days | Medium |
| P1 | C-6: Acceptance framework unification | 1 day | Low |
| P1 | C-1: Operator → Browser + Desktop | 1 day | Low |
| P2 | C-3: TTS state consolidation | 2 days | Medium |
| P2 | C-7: Phase file renaming | 2 days | Low |
| P2 | C-9: Health system unification | 2 days | Medium |
| P3 | C-2: pyttsx3 consolidation | 4 hours | Medium |
| P3 | C-4: Wake word consolidation | 4 hours | Low |
| P3 | C-8: OCR deduplication | 4 hours | Low |
| P3 | C-10: Browser memory | 2 hours | Low |

---

*End of Consolidation Plan — 2026-05-29*
