# J.A.R.V.I.S Master Architecture Audit

**Date:** 2026-05-29  
**Auditor:** Principal Engineer (automated audit via Claude Code)  
**Codebase:** `C:\J.A.R.V.I.S\local_jarvis`  
**Scope:** Full system audit — architecture, reliability, security, performance, maintainability

---

## Executive Summary

J.A.R.V.I.S is a Windows desktop assistant comprising ~787 Python files across 40+ subsystem directories. The routing and security model is genuinely well-designed: an intent allowlist, confirmation gates for destructive operations, and fixed subprocess argv prevent the most common agent safety failures.

However, the system has five categories of serious production risk:

1. **Storage growth is unbounded and already critical** — 66 MB of backup files (2,522 files), 6.2 MB event log, 1.8 MB command history, zero retention policy.
2. **Acceptance tests contain hardcoded passes and mock-mode validation** — the voice and integrations acceptance suites inflate readiness scores.
3. **The voice subsystem is over-engineered** — 5 TTS engines, 5 STT engines, 119 files, 51 bare `except` clauses in `tts.py` alone — with unclear fallback guarantees.
4. **Memory TTL is stored but only filtered on read; expired entries are never deleted** — the store grows unbounded.
5. **Integrations are entirely in mock mode** — the integrations acceptance suite *requires* `MOCK_MARKER` to be present to pass, meaning it validates mock behavior, not real connectivity.

Self-reported readiness scores (from `reliability/product_readiness.py`): Voice 65%, Memory 55%, Browser 65%, Desktop 50%, Coding 78%, Integrations 12%, Reliability 58%, Performance 62%.

---

## Table of Contents

1. [Project Map](#1-project-map)
2. [Subsystem Inventory](#2-subsystem-inventory)
3. [Dependency Graph](#3-dependency-graph)
4. [Duplicate Systems](#4-duplicate-systems)
5. [Dead Code](#5-dead-code)
6. [Mock Implementations](#6-mock-implementations)
7. [Fake Success Paths](#7-fake-success-paths)
8. [Validation Bypass Risks](#8-validation-bypass-risks)
9. [Reliability Risks](#9-reliability-risks)
10. [Scalability Risks](#10-scalability-risks)
11. [Performance Bottlenecks](#11-performance-bottlenecks)
12. [Storage Growth Risks](#12-storage-growth-risks)
13. [Architectural Inconsistencies](#13-architectural-inconsistencies)
14. [Maintainability Risks](#14-maintainability-risks)
15. [Subsystem Evaluations](#15-subsystem-evaluations)
16. [Issue Register](#16-issue-register)

---

## 1. Project Map

```
C:\J.A.R.V.I.S\local_jarvis\
├── core/           Kernel: app, router, security, confirmation, types, config, session
├── brain/          Intent classification, routing, memory, preferences, aliases, LLM bridge
├── actions/        58 modules, 494 action classes (intent handlers)
├── voice/          119 files — TTS, STT, streaming, wake word, audio routing
│   ├── engines/    5 TTS engines: edge, piper, pyttsx3, styletts2, xtts
│   ├── providers/  7 providers: elevenlabs (2), openai realtime (2), piper local, pyttsx3 fallback
│   ├── stt_engines/ 5 STT engines: faster-whisper, onnx-whisper, deepgram, parakeet, whisper.cpp
│   ├── stt_stack/  9 pipeline components: confidence fusion, language detect, transcript repair…
│   └── streaming/  mp3_frame.py (1 file — streaming dir is nearly empty)
├── agents/         9 agent modules (executive, conversation, coding, research, task, …)
├── task_agent/     Supervised task execution: planner, executor, findings, patches, safety
├── memory/         Personal store, session, semantic, project indexer, graph, search
├── browser/        DOM read, URL validation, task planner, memory
├── desktop/        Window management, desktop control
├── computer_control/ Window focus/min/max, clipboard (with confirmation)
├── vision/         Screen capture, OCR, active window detection (read-only)
├── ui/             Tray, PySide6 overlay HUD, console Rich UI
├── services/       Watchdog, runtime monitor, high-performance runtime, autostart
├── reliability/    Acceptance test suites + health report generators (16 files)
├── validation/     Scenario framework, scenario files per subsystem (15 files)
├── integrations/   ollama_client, openai_client (stub), telegram_client (empty)
├── providers/      daily_summary_provider (email/calendar mock)
├── investigation/  Trading algorithm investigation modules
├── skills/         Help system metadata
├── diagnostics/    Cross-system analysis
├── conversation/   Context store, suggestions, response enhancement
├── language/       NLP utilities
├── operating/      OS-level operations
├── operational/    Operational command handling
├── runtime/        Runtime state management
├── workflows/      Predefined workflow sequences
├── workspaces/     Workspace context management
├── apps/           App discovery and launching
├── websites/       Website allowlist and launching
├── scripts/        ~60 smoke test / helper scripts
├── tests/          117 test files, 964 test functions
└── data/           Persistent JSON/JSONL storage (growing unbounded)
```

**Total Python files:** ~787  
**Total test functions:** 964 across 117 test files  
**Total action classes:** 494  
**Total bare `except Exception` clauses:** 1,065  
**TODO/FIXME/HACK markers:** 28

---

## 2. Subsystem Inventory

| Subsystem | Directory | Files | Role |
|-----------|-----------|-------|------|
| Runtime kernel | `core/` | ~15 | App lifecycle, routing, security, types |
| Intent router | `brain/` | ~20 | Classification, dispatch, LLM bridge |
| Action system | `actions/` | 58 | 494 intent handler classes |
| Voice (TTS) | `voice/engines/`, `voice/providers/`, `voice/tts*.py` | ~40 | Text-to-speech with 5 engines |
| Voice (STT) | `voice/stt_engines/`, `voice/stt_stack/`, `voice/transcriber.py` | ~20 | Speech-to-text with 5 engines |
| Voice (misc) | `voice/*.py` (non-engine) | ~60 | Wake word, audio routing, latency, normalization |
| Memory | `memory/` | ~20 | 5 overlapping stores: personal, session, semantic, project index, graph |
| Agent system | `agents/` | 9 | Specialized agents (executive, coding, research, …) |
| Task agent | `task_agent/` | ~10 | Supervised multi-step task execution with safety gates |
| Browser | `browser/` | ~8 | DOM read-only access, URL validation |
| Desktop | `desktop/`, `computer_control/` | ~10 | Window control, clipboard (confirmation-gated) |
| Vision | `vision/` | ~8 | Screen capture, OCR, active window |
| UI / Overlay | `ui/` | ~10 | PySide6 HUD, system tray, console |
| Services | `services/` | ~8 | Watchdog, runtime monitor, autostart |
| Reliability | `reliability/` | 16 | Health checks, acceptance scores |
| Validation | `validation/` | 15 | Scenario runner, per-subsystem scenarios |
| Integrations | `integrations/`, `providers/` | ~8 | Ollama (real), email/calendar (mock), Telegram (empty) |
| Investigation | `investigation/` | ~20 | Trading algorithm debugging and replay |
| Skills | `skills/` | ~5 | Help metadata |
| Coding assistant | `agents/coding_agent.py`, `task_agent/` | ~15 | Code search, patch, compile |

---

## 3. Dependency Graph

### Critical startup chain

```
main.py
  └── core/app.py (JarvisApp)
        ├── brain/router.py (CommandRouter)
        │     ├── brain/intent_classifier.py
        │     ├── core/security.py
        │     ├── core/confirmation.py
        │     └── actions/registry.py (494 action classes loaded at import)
        ├── voice/voice_loop.py
        │     ├── voice/transcriber.py → stt_engines/* (heavy imports at startup)
        │     └── voice/microphone.py
        ├── voice/wakeword.py / wakeword_loop.py
        ├── ui/tray_app.py
        │     └── ui/overlay_app.py (PySide6 Qt thread spawned here)
        ├── services/watchdog.py
        └── services/runtime_monitor.py
```

### Data flow

```
Audio in → voice/microphone.py
         → voice/transcriber.py (STT engine pipeline)
         → brain/router.py (intent classify)
         → core/security.py (allowlist check)
         → core/confirmation.py (if required)
         → actions/registry.py (dispatch to handler)
         → handler.execute()
         → ui/overlay_app.py (display result)
         → voice/tts.py (speak result)
```

### Key cross-cutting dependencies

- `config.py` is imported by virtually every module — it is a single point of failure at startup.
- `core/logger.py` is imported before `config.py` in some modules — import ordering is fragile.
- `actions/registry.py` imports all 58 action modules at startup — any import error in any action silently prevents that action from registering.

---

## 4. Duplicate Systems

| Duplication | Files | Risk |
|-------------|-------|------|
| **TTS engine implementations** | `voice/tts.py` (orchestrator), `voice/tts_edge.py`, `voice/tts_pyttsx3.py`, `voice/tts_subprocess.py`, `voice/tts_backend.py`, `voice/engines/pyttsx3_engine.py`, `voice/providers/pyttsx3_fallback.py` | pyttsx3 logic spread across 3+ files; unclear which is canonical |
| **pyttsx3 lifecycle** | `voice/pyttsx3_lifecycle.py`, `voice/pyttsx3_completion.py`, `voice/engines/pyttsx3_engine.py`, `voice/providers/pyttsx3_fallback.py` | Four files managing the same library; state can diverge |
| **TTS state tracking** | `voice/tts_status.py`, `voice/tts_watchdog.py`, `voice/tts_output_policy.py`, `voice/tts_playback_trace.py`, `voice/tts_policy_trace.py`, `voice/voice_debug_store.py` | Six files tracking overlapping TTS state |
| **Browser memory** | `browser/memory.py`, `data/browser_memory.json`, `data/browser_action_replay.jsonl` | Browser state in two formats in two locations |
| **Session memory vs personal memory** | `memory/store.py` + `data/memory_store.json`, `memory/session_memory.py` + `data/session_memory.json` | Same data (facts about user) duplicated across stores |
| **Vision implementations** | `vision/screen_understanding.py` (contains legacy v1 and v35), plus references to v36 | Two versioned codepaths with unclear selection logic |
| **Streaming STT directory** | `voice/streaming/` has only `mp3_frame.py`; streaming STT is actually in `voice/streaming_stt/` and `voice/streaming_pipeline.py` | Confusing split |
| **Wake word modules** | `voice/wake_word.py`, `voice/wakeword.py`, `voice/wakeword_loop.py`, `voice/wakeword_state.py`, `voice/wake_diagnostics.py`, `voice/wake_greeting.py`, `voice/wake_phrases.py` | 7 files for wake word; responsibilities unclear |

---

## 5. Dead Code

| File | Issue |
|------|-------|
| `integrations/telegram_client.py` | Contains only a docstring — 2 lines total. No implementation, no stub, no future marker. |
| `voice/streaming/` directory | Contains only `mp3_frame.py`; the directory name implies a larger streaming subsystem that doesn't exist here. |
| `actions/phase68_alpha_actions.py` | 33 lines; thin wrapper with minimal logic. Purpose unclear relative to other phase files. |
| `actions/phase45_actions.py` through `phase60_actions.py` | Phase numbering implies historical evolution. No mechanism to identify which phases are still active vs superseded. |
| Multiple `pass` statements in action `execute()` bodies | `actions/foundation_actions.py:273`, `actions/phase60_actions.py:218`, `actions/vision_actions.py:89,178`, `actions/voice_audio_actions.py:424,754` — these represent executed code paths that silently do nothing. |

---

## 6. Mock Implementations

| System | File | Mock Type | Impact |
|--------|------|-----------|--------|
| **Email integration** | `providers/daily_summary_provider.py` | Mock provider returns hardcoded data with `MOCK MODE` marker | Integrations acceptance suite **requires** the MOCK_MARKER to pass; this validates mock behavior, not real connectivity |
| **Calendar integration** | `providers/daily_summary_provider.py` | Same mock provider | No real OAuth or calendar API connected |
| **OpenAI LLM classifier** | `integrations/openai_client.py` | Raises `OpenAIClassifierNotConfiguredError` unconditionally | If anything tries to use OpenAI as LLM_PROVIDER, it hard-fails |
| **Telegram notifications** | `integrations/telegram_client.py` | Empty file (docstring only) | Silently does nothing if imported |

---

## 7. Fake Success Paths

These are acceptance test cases that always return `True` regardless of actual system behavior:

| Location | Code | What it hides |
|----------|------|---------------|
| `reliability/voice_health.py:98` | `run_case("long_sentence_normalization", lambda: (True, "spoken_normalization module available"))` | Does not test normalization; checks only that the module exists as a string in the message |
| `reliability/voice_health.py:99` | `run_case("paragraph_transcription_path", lambda: (True, "streaming buffer policy available"))` | Does not test actual transcription; always passes |
| `reliability/memory_health.py:115` | `run_case("ranking_diagnostics", lambda: (True, show_memory_ranking_diagnostics()[:120]))` | Calls a display function and passes regardless of its output |
| `reliability/integrations_health.py:44` | Passes when `_MOCK_MARKER in body` — i.e., passes *because* the system is in mock mode | Production test validates that mock mode is active; a live integration would fail this test |
| `reliability/product_readiness.py:19-28` | `run_acceptance=False` code path returns hardcoded scores: Voice=65, Memory=55, Browser=65, etc. | If acceptance is skipped, scores are invented, not measured |

---

## 8. Validation Bypass Risks

| Attack Vector | Current Mitigation | Strength | Gap |
|---------------|-------------------|----------|-----|
| **LLM intent injection** | JSON schema validation; forbidden key check; intent must be in IMPLEMENTED_INTENTS | GOOD | LLM JSON is validated but parameter values are passed through |
| **PowerShell composition** | `ALLOWED_POWERSHELL_SCRIPTS` is a hardcoded list of 3 absolute paths; no string composition | GOOD | None found |
| **App .lnk target** | User approval required; app must be in Windows Start Menu | FAIR | Target path of .lnk shown to user as filename, not resolved target — user may not know where it points |
| **Task agent path escape** | `task_agent/safety.py:path_write_allowed()` uses `Path.resolve()` + `relative_to(PROJECT_ROOT)` | GOOD | Symlinks could still redirect if `PROJECT_ROOT` itself contains symlinks |
| **Memory entry size** | No per-entry size limit in `memory/store.py` | WEAK | A single `remember()` call with megabytes of text would be stored without complaint |
| **Confirmation timeout** | Default 120 seconds; user must confirm destructive actions | FAIR | A second voice command during the 120s window could be confused with a confirmation |
| **Rate limiting** | None | MISSING | Rapid command injection (e.g., from microphone loop glitch) could queue many actions |
| **URL allowlist bypass** | `APPROVED_WEBSITES` is a JSON file under `data/` | FAIR | If an attacker can write `data/approved_websites.json`, they can add arbitrary URLs |

---

## 9. Reliability Risks

### R-1: No recovery when microphone disconnects mid-session
- **Severity:** HIGH
- **Impact:** Voice input permanently lost; user must restart the entire application
- **Root cause:** `voice/voice_loop.py` catches `OSError` on microphone reads but does not attempt reconnection; the loop exits
- **Proposed fix:** Implement microphone reconnect loop with exponential backoff; monitor device plug/unplug events via `pyaudio`
- **Effort:** 2 days
- **Priority:** P1

### R-2: TTS failure is silent to the user
- **Severity:** HIGH
- **Impact:** User speaks a command, J.A.R.V.I.S executes it, but the verbal confirmation never plays; user does not know if the command succeeded
- **Root cause:** `voice/tts.py` catches all engine exceptions and logs warnings but does not surface the failure to the UI layer
- **Proposed fix:** On TTS failure, push a text notification to the overlay; fall back to console print if overlay is unavailable
- **Effort:** 1 day
- **Priority:** P1

### R-3: Action registry silently drops actions with import errors
- **Severity:** HIGH
- **Impact:** If any of the 58 action modules fails to import (e.g., missing dependency), that module's intents become silently unregistered — the user sees "unknown intent" with no explanation
- **Root cause:** `actions/registry.py` wraps module imports in try/except; failed imports are logged but not surfaced at startup
- **Proposed fix:** Add a startup validation pass that lists all expected intents and verifies they have registered handlers; fail loudly if any are missing
- **Effort:** 1 day
- **Priority:** P1

### R-4: Qt overlay thread has no maximum recovery attempts
- **Severity:** MEDIUM
- **Impact:** If the overlay crashes repeatedly, the recovery loop restarts it indefinitely, consuming CPU
- **Root cause:** `ui/overlay_app.py` recovery logic has a backoff but no maximum retry count
- **Proposed fix:** Cap retries at 3; after 3 failures, disable overlay and continue in headless mode
- **Effort:** 2 hours
- **Priority:** P2

### R-5: Config.py is a single point of failure
- **Severity:** MEDIUM
- **Impact:** Any syntax error or import failure in `config.py` prevents the entire system from starting
- **Root cause:** `config.py` is imported by virtually every module; startup errors produce deep tracebacks
- **Proposed fix:** Add a `config_validator.py` that loads config in isolation and validates required keys before any subsystem starts; print a clear error if validation fails
- **Effort:** 3 hours
- **Priority:** P2

### R-6: 1,065 bare `except Exception` clauses
- **Severity:** MEDIUM
- **Impact:** Real errors are swallowed silently; debugging is extremely difficult; latent bugs may go undetected for months
- **Root cause:** Defensive coding pattern used throughout; `tts.py` alone has 51 such clauses
- **Proposed fix:** Audit-first pass: add `logger.exception(...)` in all bare except blocks; second pass: narrow exceptions to specific types where possible
- **Effort:** 3 days
- **Priority:** P2

### R-7: Thread proliferation with no lifecycle management
- **Severity:** MEDIUM
- **Impact:** Voice loop thread, TTS async thread, wake word thread, overlay Qt thread, runtime monitor thread — no central registry; a thread crash may go undetected
- **Root cause:** Threads spawned independently across modules without a supervisor
- **Proposed fix:** Create a `ThreadRegistry` in `core/` that tracks all daemon threads, checks liveness on a heartbeat, and alerts on unexpected exits
- **Effort:** 2 days
- **Priority:** P2

---

## 10. Scalability Risks

### S-1: Linear memory search degrades with growth
- **Severity:** MEDIUM
- **Impact:** Memory search iterates all entries on every query; at 10,000 entries (achievable in weeks of continuous use), search latency becomes noticeable
- **Root cause:** `memory/store.py:list_visible()` iterates `data["entries"]` linearly; no index
- **Proposed fix:** Replace JSON flat store with SQLite; add full-text search index
- **Effort:** 3 days
- **Priority:** P2

### S-2: Action registry loads all 494 classes at startup
- **Severity:** LOW
- **Impact:** Startup time increases as more actions are added; memory footprint grows unnecessarily for rarely-used actions
- **Root cause:** `actions/registry.py` imports all modules at import time
- **Proposed fix:** Lazy-load action modules on first dispatch; use importlib
- **Effort:** 1 day
- **Priority:** P3

### S-3: Project index grows with every new file
- **Severity:** LOW
- **Impact:** `data/project_index.json` is 576 KB and growing; deleted files are not pruned from the index
- **Root cause:** `memory/project_indexer.py` appends new file entries but has no pruning for deleted files
- **Proposed fix:** On index rebuild, stat all indexed paths and remove entries for non-existent files
- **Effort:** 2 hours
- **Priority:** P3

---

## 11. Performance Bottlenecks

### P-1: STT pipeline has 9 serial components
- **Severity:** MEDIUM
- **Impact:** Each component (confidence fusion, language detect, transcript repair, multipass, …) adds latency to the speech-to-text path; any slow component blocks voice input
- **Root cause:** `voice/stt_stack/` components are chained serially; no parallelism
- **Proposed fix:** Profile each component; disable any component that contributes <5% accuracy improvement for >20ms latency cost; make optional components feature-flagged
- **Effort:** 2 days
- **Priority:** P2

### P-2: Large JSON files loaded entirely into memory at startup
- **Severity:** MEDIUM
- **Impact:** `data/project_index.json` (576 KB), `data/semantic_memory.json` (335 KB), `data/memory_store.json` loaded on first access; blocking the event loop briefly
- **Root cause:** All JSON stores use `path.read_text()` + `json.loads()` on every access; no caching
- **Proposed fix:** Cache loaded data in-process with a dirty flag; only reload from disk when the file changes (use `mtime` check)
- **Effort:** 1 day
- **Priority:** P2

### P-3: TTS engine selection has no latency SLA
- **Severity:** LOW
- **Impact:** Fallback chain (edge-tts → pyttsx3) could add 100-500ms on every spoken response without the user knowing which engine is active
- **Root cause:** No end-to-end latency budget enforced; measured by `voice/latency_tracker.py` but not enforced
- **Proposed fix:** Add a latency budget check: if the primary engine exceeds 300ms for 3 consecutive calls, log an alert and suggest configuration change
- **Effort:** 4 hours
- **Priority:** P3

### P-4: Overlay HUD repaints on every state update
- **Severity:** LOW
- **Impact:** Full-screen PySide6 paint triggered on every voice event; CPU usage spikes during rapid commands
- **Root cause:** `ui/overlay_app.py` triggers repaint on all queue updates without coalescing
- **Proposed fix:** Coalesce updates: repaint at most once per 33ms (30 fps cap) using a `QTimer`
- **Effort:** 4 hours
- **Priority:** P3

---

## 12. Storage Growth Risks

### G-1: Backup directory is catastrophically over-populated
- **Severity:** CRITICAL**
- **Impact:** `data/backups/` contains **2,522 timestamped files** totaling **66 MB**. At current growth rate, this will exhaust a typical SSD partition within months. Directory listing itself becomes slow above 10,000 files.
- **Root cause:** No retention policy; every action that writes a file creates a timestamped backup with no cleanup
- **Proposed fix:** (1) Immediate: one-time cleanup of all backups older than 7 days. (2) Ongoing: keep only the 5 most recent backups per logical file; delete older ones automatically after every write
- **Effort:** 4 hours
- **Priority:** P0

### G-2: `observability_events.jsonl` grows at ~6 MB/day
- **Severity:** HIGH
- **Impact:** Already 6.2 MB; at current rate this file will reach 2 GB within a year. Loading it into memory at startup will cause multi-second delays.
- **Root cause:** `services/runtime_monitor.py` and related services append an event record on every timeout, memory spike, or lag detection. No rotation configured.
- **Proposed fix:** Implement log rotation: max file size 10 MB, keep 3 rotations; use Python's `logging.handlers.RotatingFileHandler` pattern
- **Effort:** 4 hours
- **Priority:** P0

### G-3: `command_history.jsonl` grows forever
- **Severity:** HIGH
- **Impact:** Already 1.8 MB; every command adds an entry. After a year of daily use (10 commands/day), this reaches ~100 MB.
- **Root cause:** Command logging appends to JSONL with no rotation or retention limit
- **Proposed fix:** Rotate at 5 MB; keep 5 rotations (25 MB total cap). Alternatively, move to SQLite for efficient size-bounded history
- **Effort:** 3 hours
- **Priority:** P0

### G-4: Memory store expired entries never deleted from disk
- **Severity:** MEDIUM
- **Impact:** `memory/store.py:list_visible()` filters expired entries on read, but never deletes them from `data/memory_store.json`. The file grows indefinitely; all expired entries are loaded and parsed on every access.
- **Root cause:** `list_visible()` skips expired entries; no corresponding delete or vacuum step exists
- **Proposed fix:** Add a `vacuum()` method to `PersonalMemoryStore` that removes all expired + hidden entries and rewrites the file; call it on startup and periodically
- **Effort:** 2 hours
- **Priority:** P1

### G-5: `data/runtime_traces.jsonl` (160 KB) and `data/command_audit.jsonl` (268 KB)
- **Severity:** LOW
- **Impact:** Currently small but following the same unbounded pattern as the larger files above
- **Root cause:** Same pattern: append-only JSONL with no rotation
- **Proposed fix:** Apply the same rotation policy as G-2 and G-3
- **Effort:** 1 hour (add to the same rotation implementation)
- **Priority:** P1

---

## 13. Architectural Inconsistencies

### A-1: Phase-numbered action files with no deprecation mechanism
- **Severity:** MEDIUM
- **Impact:** 19 files named `phase45_actions.py` through `phase68_alpha_actions.py`. There is no way to determine which phases are current, superseded, or partially migrated. `phase45_actions.py` alone is 755 lines.
- **Root cause:** Incremental development added phases numerically; no refactor consolidated them
- **Proposed fix:** Rename to domain-based names (`investigation_actions.py`, `browser_control_actions.py`, `trading_loop_actions.py`); consolidate phases that cover the same domain
- **Effort:** 2 days
- **Priority:** P2

### A-2: Five TTS engines with no canonical selection algorithm
- **Severity:** MEDIUM
- **Impact:** The system has `edge_engine.py`, `piper_engine.py`, `pyttsx3_engine.py`, `styletts2_engine.py`, `xtts_engine.py` in `voice/engines/`, plus `tts.py`, `tts_edge.py`, `tts_pyttsx3.py`, `tts_subprocess.py` in the parent directory. It is unclear which file is the authoritative entry point for TTS.
- **Root cause:** Engines were added incrementally without consolidating the selection layer
- **Proposed fix:** Designate `voice/engines/registry.py` as the single entry point; all direct calls to `tts_edge.py`, `tts_pyttsx3.py`, etc. should route through the registry
- **Effort:** 1 day
- **Priority:** P2

### A-3: Memory split across 5 incompatible stores
- **Severity:** MEDIUM
- **Impact:** The same user fact may exist in `memory_store.json` (personal), `session_memory.json`, `semantic_memory.json`, and `data/memory.json` (legacy). No synchronization mechanism. A forget command in one store does not affect others.
- **Root cause:** Each feature (semantic search, session context, personal facts) created its own store without consolidation
- **Proposed fix:** Designate `PersonalMemoryStore` as the canonical store; migrate session and semantic stores to use it as a backend with a read-through cache
- **Effort:** 3 days
- **Priority:** P2

### A-4: Integrations acceptance validates mock mode, not production readiness
- **Severity:** HIGH
- **Impact:** `reliability/integrations_health.py` passes its test cases specifically when `MOCK_MARKER in body`, meaning the test suite verifies that the system is in mock mode. A real integration would cause these tests to fail. This gives a false signal about integration health.
- **Root cause:** Tests were written to verify mock mode was active rather than to test production behavior
- **Proposed fix:** Rewrite acceptance cases to: (a) when live credentials present → test real connectivity; (b) when no credentials → mark as SKIP not PASS
- **Effort:** 1 day
- **Priority:** P1

### A-5: Acceptance framework has two competing implementations
- **Severity:** LOW
- **Impact:** `validation/framework.py` (measured, Phase 66) and `reliability/hardening_core.py` (Phase 65) are separate implementations of the same concept. It is unclear which one produces the authoritative readiness score.
- **Root cause:** Framework was rewritten in Phase 66 without removing Phase 65
- **Proposed fix:** Migrate all `reliability/` acceptance callers to `validation/framework.py`; deprecate `hardening_core.py`
- **Effort:** 1 day
- **Priority:** P3

---

## 14. Maintainability Risks

### M-1: Voice subsystem has 119 files — cognitive overload
- **Severity:** HIGH
- **Impact:** A developer new to the codebase cannot understand the voice subsystem without reading dozens of files. Adding a feature (e.g., new TTS engine) requires understanding the interaction of engines, providers, backends, watchdogs, policies, traces, and status modules.
- **Root cause:** Incremental feature additions without consolidation; each concern got its own file
- **Proposed fix:** Consolidate into 5 logical groups with clear interfaces: `VoiceCapture`, `STTPipeline`, `TTSPipeline`, `WakeWord`, `AudioDevices`. Target: ~30 files
- **Effort:** 5 days
- **Priority:** P2

### M-2: `config.py` has 1,900+ configuration keys with no schema
- **Severity:** HIGH
- **Impact:** There is no validation of config key names at load time. A typo in `.env` silently falls back to a default. No documentation of which keys affect which subsystems.
- **Root cause:** Config grew organically with each feature addition
- **Proposed fix:** Add a `CONFIG_SCHEMA` dict mapping every key to its type, default, and description; validate on startup; generate documentation from schema
- **Effort:** 2 days
- **Priority:** P2

### M-3: 494 action classes across 58 files
- **Severity:** MEDIUM
- **Impact:** The action system is the primary extension point, but finding the right action class requires knowing the file, which requires knowing the phase. Adding a new intent requires knowing where to register it.
- **Root cause:** Actions grew with phases; registry uses dynamic imports
- **Proposed fix:** Add an `ACTION_MAP.md` that lists every intent → action class → file; regenerate on each build from the registry
- **Effort:** 4 hours
- **Priority:** P3

### M-4: Tests validate configs and strings, not behavior
- **Severity:** MEDIUM
- **Impact:** 964 test functions across 117 files, but acceptance tests often check string outputs or config flags rather than end-to-end behavior. Voice tests require a live microphone; most CI environments cannot run them.
- **Root cause:** Testing voice/TTS requires hardware; unit tests were written to avoid hardware dependency but lost behavioral coverage
- **Proposed fix:** Add mockable interfaces for microphone input and audio output; write behavioral tests that inject audio data directly into the STT pipeline
- **Effort:** 3 days
- **Priority:** P2

---

## 15. Subsystem Evaluations

### 15.1 Voice (TTS)
- **Current readiness:** 65% (self-reported)
- **Actual assessment:** 55% — two acceptance test cases are unconditional passes; TTS failure not surfaced to user
- **Strengths:** Multiple fallback engines; secret redaction before speech; async playback
- **Critical gaps:** No notification when TTS fails; 5 engines with unclear selection; pyttsx3 logic split across 4 files
- **Blocking issues:** R-2 (silent TTS failure), A-2 (no canonical TTS entry point)

### 15.2 STT
- **Current readiness:** ~60% (embedded in voice score)
- **Actual assessment:** 60% — streaming works but 9-component serial pipeline is over-complex
- **Strengths:** Multiple engine fallbacks; local processing; streaming support
- **Critical gaps:** No end-to-end latency budget; no automated test with real audio
- **Blocking issues:** P-1 (serial pipeline bottleneck)

### 15.3 Wake Word
- **Current readiness:** ~65%
- **Actual assessment:** 65% — 7 files for one concern is excessive; greeting and state tracking are ad-hoc
- **Strengths:** Configurable phrases; diagnostics available
- **Critical gaps:** No test with actual wake phrase audio; state management split across 3 modules

### 15.4 Browser Automation
- **Current readiness:** 65% (self-reported)
- **Actual assessment:** 70% — conservative read-only design is good; no major gaps
- **Strengths:** Read-only; URL validation; task planner
- **Critical gaps:** Browser memory duplicated in two locations (G-5 class risk)

### 15.5 Desktop Operator
- **Current readiness:** 50% (self-reported)
- **Actual assessment:** 50% — app launcher `.lnk` target not validated; window focus is race-condition-prone
- **Strengths:** Allowlisted apps and websites; confirmation gates
- **Critical gaps:** .lnk target not shown to user before approval; no reconnect on window handle stale

### 15.6 Memory
- **Current readiness:** 55% (self-reported)
- **Actual assessment:** 50% — TTL not enforced on disk; 5 overlapping stores; no vacuum
- **Strengths:** Redaction before storage; category system; importance/confidence metadata
- **Critical gaps:** G-4 (expired entries never deleted), A-3 (5 incompatible stores), S-1 (linear search)

### 15.7 Agent System
- **Current readiness:** ~65%
- **Actual assessment:** 65% — agents are mostly well-defined but depend on the same fragile voice/action stack
- **Strengths:** Specialized agents per domain; executive agent coordinates
- **Critical gaps:** No isolation between agents; a failing agent can corrupt shared state

### 15.8 Skills / Help System
- **Current readiness:** ~70%
- **Actual assessment:** 70% — metadata-driven help is good; coverage may be incomplete
- **Critical gaps:** No automated check that skills metadata matches implemented intents

### 15.9 Validation Framework
- **Current readiness:** ~60%
- **Actual assessment:** 45% — two competing frameworks; fake success paths; mock-validates-mock issue
- **Strengths:** Scenario-based structure; per-category coverage
- **Critical gaps:** A-4 (integration tests validate mock mode), A-5 (two competing frameworks), Section 7 (fake passes)

### 15.10 Recovery Systems
- **Current readiness:** ~58% (self-reported)
- **Actual assessment:** 50% — overlay recovery exists but most failure modes have no recovery path
- **Strengths:** Overlay auto-restart; TTS engine fallback; task agent rollback
- **Critical gaps:** R-1 (no mic reconnect), R-2 (silent TTS failure), R-3 (silent action drop), R-7 (no thread supervisor)

### 15.11 Integrations
- **Current readiness:** 12% (self-reported — accurate)
- **Actual assessment:** 12% — Ollama is functional; everything else is mock or empty
- **Strengths:** Ollama LLM integration is real and gated behind config
- **Critical gaps:** Email, calendar, Telegram are all mock or empty; acceptance tests validate mock mode

### 15.12 UI / Overlay
- **Current readiness:** ~70%
- **Actual assessment:** 70% — good isolation from core; recovery mechanism present
- **Strengths:** Display-only (no command bypass); overlay thread isolated from main
- **Critical gaps:** No repaint coalescing; state duplication across config/overlay_state/runtime_state

### 15.13 Runtime
- **Current readiness:** ~62% (performance, per self-report)
- **Actual assessment:** 60% — runtime monitor is real; high-performance runtime path exists but unclear when activated
- **Critical gaps:** No central thread registry; no clear activation criteria for high-performance mode

### 15.14 Task Agent
- **Current readiness:** ~75%
- **Actual assessment:** 78% — best-designed subsystem; clear safety model; confirmation gates
- **Strengths:** READONLY/CONFIRM_REQUIRED/BLOCKED allowlist; rollback support; fixed subprocess argv
- **Critical gaps:** Symlink edge case in `path_write_allowed()` (low risk); no parallelism in step execution

### 15.15 Coding Assistant
- **Current readiness:** 78% (self-reported)
- **Actual assessment:** 75% — task agent + code search is functional; patch preview is safe
- **Strengths:** Preview-before-apply; `compileall` validation; pytest gated
- **Critical gaps:** No integration test that runs a full patch cycle end-to-end

---

## 16. Issue Register

The following table lists all identified issues sorted by priority.

| ID | Subsystem | Title | Severity | Impact | Root Cause | Proposed Fix | Effort | Priority |
|----|-----------|-------|----------|--------|-----------|--------------|--------|----------|
| G-1 | Storage | Backup directory: 2,522 files, 66 MB, no retention | CRITICAL | Disk exhaustion | No backup cleanup logic | Keep 5 most recent per logical file; run cleanup on startup | 4h | P0 |
| G-2 | Storage | `observability_events.jsonl` unbounded growth | HIGH | Disk exhaustion, slow startup | Append-only with no rotation | RotatingFileHandler: 10 MB × 3 rotations | 4h | P0 |
| G-3 | Storage | `command_history.jsonl` unbounded growth | HIGH | Disk exhaustion | Append-only with no rotation | Rotate at 5 MB × 5 rotations | 3h | P0 |
| R-1 | Voice | No mic reconnect on disconnect | HIGH | Permanent voice loss until restart | Loop exits on OSError | Reconnect loop with exponential backoff | 2d | P1 |
| R-2 | Voice/TTS | TTS failure silent to user | HIGH | User doesn't know commands failed | Exception swallowed; no UI notification | Push text notification to overlay on TTS failure | 1d | P1 |
| R-3 | Actions | Registry silently drops actions with import errors | HIGH | "Unknown intent" with no explanation | Try/except around module imports | Startup validation: assert all expected intents are registered | 1d | P1 |
| G-4 | Memory | Expired entries never deleted from disk | MEDIUM | Memory file grows indefinitely | TTL filtered on read but not deleted | Add `vacuum()` to PersonalMemoryStore; call on startup | 2h | P1 |
| A-4 | Integrations | Acceptance tests validate mock mode, not live | HIGH | False readiness signal | Tests written to verify mock is active | Rewrite: SKIP when no credentials, test real when present | 1d | P1 |
| F-1 | Validation | Fake success: `long_sentence_normalization` always passes | HIGH | Voice readiness score inflated | Hardcoded `lambda: (True, ...)` | Replace with actual normalization round-trip test | 2h | P1 |
| F-2 | Validation | Fake success: `paragraph_transcription_path` always passes | HIGH | Voice readiness score inflated | Hardcoded `lambda: (True, ...)` | Replace with actual STT pipeline invocation test | 2h | P1 |
| R-5 | Core | Config.py is a single point of failure | MEDIUM | Startup failure from any import error | No pre-validation | Add `config_validator.py` that validates keys before subsystem init | 3h | P2 |
| R-6 | Codebase | 1,065 bare `except Exception` clauses | MEDIUM | Silent error swallowing | Defensive coding culture | Audit pass: add `logger.exception()` to all bare excepts | 3d | P2 |
| R-4 | UI | Overlay recovery loop has no retry cap | MEDIUM | CPU drain on persistent overlay crash | No max retry count | Cap at 3 retries; disable and continue headless | 2h | P2 |
| R-7 | Runtime | No central thread registry | MEDIUM | Thread crashes go undetected | Threads spawned independently | Create `ThreadRegistry` in `core/` with liveness heartbeat | 2d | P2 |
| S-1 | Memory | Linear memory search | MEDIUM | Search latency degrades at scale | JSON flat list, no index | Migrate to SQLite with FTS | 3d | P2 |
| P-1 | STT | 9-component serial STT pipeline | MEDIUM | Latency spikes from slow components | All components chained serially | Profile and disable sub-5%-gain components | 2d | P2 |
| P-2 | Storage | Large JSON files reloaded on every access | MEDIUM | Blocking reads on hot paths | No in-process cache | Cache with mtime-based invalidation | 1d | P2 |
| A-1 | Actions | Phase-numbered files without deprecation | MEDIUM | Unmaintainable action catalog | Incremental development pattern | Rename to domain-based; consolidate phases | 2d | P2 |
| A-2 | Voice/TTS | No canonical TTS entry point | MEDIUM | Unclear which engine is authoritative | Engines added without consolidation | Designate `voice/engines/registry.py` as sole entry | 1d | P2 |
| A-3 | Memory | 5 incompatible memory stores | MEDIUM | Forget in one store doesn't affect others | Each feature created its own store | Consolidate under PersonalMemoryStore backend | 3d | P2 |
| M-1 | Voice | 119-file voice subsystem | HIGH | Developer cognitive overload | Incremental additions without consolidation | Refactor into 5 logical groups (~30 files) | 5d | P2 |
| M-2 | Core | 1,900+ config keys, no schema | HIGH | Silent misconfiguration | Config grew organically | Add CONFIG_SCHEMA with type/default/description | 2d | P2 |
| M-4 | Tests | Tests validate strings/configs, not behavior | MEDIUM | Low behavioral coverage | Hardware dependency in voice tests | Mockable audio interfaces for behavioral tests | 3d | P2 |
| V-1 | Security | Memory entry has no size limit | MEDIUM | Single large entry accepted | No validation in `remember()` | Add max 10 KB per entry; reject or truncate larger | 1h | P2 |
| V-2 | Security | `data/approved_websites.json` is user-writable | MEDIUM | Attacker who can write data/ can add URLs | JSON allowlist stored in user-writable directory | Move allowlist to `config/` under source control; make runtime additions require explicit flag | 2h | P2 |
| A-5 | Validation | Two competing acceptance frameworks | LOW | Confusion about authoritative score | Phase 66 rewrote Phase 65 without removing it | Migrate all callers to `validation/framework.py` | 1d | P3 |
| S-2 | Actions | All 494 action classes loaded at startup | LOW | Slow startup; wasted memory | Eager imports in registry | Lazy-load via importlib on first dispatch | 1d | P3 |
| S-3 | Memory | Project index doesn't prune deleted files | LOW | Index grows with deleted files | No stat check on rebuild | Stat all indexed paths; remove stale entries | 2h | P3 |
| P-3 | Voice/TTS | No latency SLA enforcement | LOW | Fallback hidden from user | Latency measured but not enforced | Alert if primary engine exceeds 300ms × 3 consecutive | 4h | P3 |
| P-4 | UI | Overlay repaints on every event | LOW | CPU spike during rapid commands | No update coalescing | 30 fps cap via QTimer | 4h | P3 |
| D-1 | Integrations | `telegram_client.py` is empty | LOW | Dead code confusion | Never implemented | Remove file or add meaningful stub with clear TODO | 30m | P3 |
| D-2 | Actions | `pass` statements in `execute()` bodies | LOW | Silent no-ops | Incomplete action implementations | Document or implement; add warning log | 2h | P3 |
| M-3 | Actions | No generated ACTION_MAP documentation | LOW | Hard to find action handlers | No tooling | Generate `ACTION_MAP.md` from registry | 4h | P3 |

---

*End of Master Audit — 2026-05-29*
