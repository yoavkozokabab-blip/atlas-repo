# Top 20 Blockers — Post Sprint 0–3
**Date:** 2026-05-29  
**Basis:** Source-code inspection. Every blocker has exact file:line.  
**Rule:** Ordered by ROI (impact ÷ effort). Do not start Sprint 4 or add features.

---

## B01 — Agent routing is metadata-only; no behavioral effect
**Severity:** HIGH  
**Impact:** Sprint 3's core claim ("12-agent architecture, each domain has a clear owner") produces zero runtime behavioral change. All commands execute identically before and after Sprint 3. Agent health checks run but the agents themselves are never involved in command execution. This inflates Agent Architecture readiness by ~38 percentage points.  
**Root cause:** `ActionRegistry.execute()` (`actions/registry.py:1063`) looks up handlers by intent string. It never consults `agent_for_intent()` or `AgentRegistry`. The two registries have zero connection.  
**Files:** `actions/registry.py:1063`, `agents/intent_routing.py`, `agents/registry.py`  
**Fix:** Not Sprint 4 scope — this is an architectural note, not a bug. Agent routing is metadata for ownership documentation. The registries are intentionally separate. **The readiness score must be adjusted downward to reflect this.** The only fix needed here is honest scoring — do not claim the routing table affects execution.  
**Effort:** 0 (score correction only)

---

## B02 — Watchdog absent in text/voice CLI modes
**Severity:** HIGH  
**Impact:** Thread death monitoring, recovery actions, and heartbeat checks are completely absent when JARVIS runs in `--text` or `--voice` mode (the primary development modes). Only `--tray` mode starts the watchdog. If the voice loop thread or TTS thread dies in CLI mode, it is silently lost.  
**Root cause:** `services/watchdog.py` `WatchdogService` is only instantiated at `ui/tray_app.py:466–469`. `main.py` only reaches this path when `JarvisTrayApp` is created. Text mode (`--text`) and voice mode (`--voice`) never create a tray app.  
**Files:** `ui/tray_app.py:464–469`, `main.py:326–346`, `services/watchdog.py`  
**Fix:** Move watchdog startup into `ensure_jarvis_runtime_bootstrapped()` in `core/runtime_bootstrap.py` (after health monitor, same pattern). Pass `app=None` if watchdog supports headless mode, or create a lightweight watchdog wrapper for non-tray startup.  
**Effort:** 2–3 hours

---

## B03 — Voice/TTS threads not registered with ThreadRegistry
**Severity:** HIGH  
**Impact:** Even when the watchdog runs (tray mode), the two most critical real-time threads — voice loop and TTS — are not registered. The `ThreadRegistry.heartbeat_check()` will not detect their deaths. A hung TTS thread silently blocks voice output; a dead voice loop silently drops commands.  
**Root cause:** S2.3 registered overlay, wakeword, watchdog, and health-monitor threads. Voice loop (`voice/voice_loop.py`) and TTS thread (`voice/tts.py` or `voice/tts_pyttsx3.py`) have no `get_thread_registry().register()` calls.  
**Files:** `voice/voice_loop.py`, `voice/tts.py`, `core/thread_registry.py`  
**Fix:** In `voice/voice_loop.py`, after starting the voice loop thread, call `get_thread_registry().register("jarvis-voice-loop", thread)`. Same in TTS thread start path. Deregister on clean exit.  
**Effort:** 1 hour

---

## B04 — `validate_config()` never aborts startup
**Severity:** HIGH  
**Impact:** S2.5 was implemented as "call validate_config and log." The roadmap required "exit if any missing." A misconfigured `DATA_DIR` (unwritable path) will cause cryptic failures later rather than a clear startup message. An empty `IMPLEMENTED_INTENTS` makes every command silently return `not_implemented`.  
**Root cause:** `runtime_bootstrap.py:58–68` calls `validate_config()` and logs warnings but never calls `run_startup_validation(abort_on_critical=True)` or calls `sys.exit()`.  
**Files:** `core/runtime_bootstrap.py:58–68`, `core/startup_validation.py:139`  
**Fix:** Change `runtime_bootstrap.py:66` to call `run_startup_validation(abort_on_critical=True)` — or simply add `if config_errors: sys.exit(1)` after the `validate_config()` call for DATA_DIR errors only.  
**Effort:** 30 minutes

---

## B05 — S2.7: Screenshot cleanup not implemented
**Severity:** MEDIUM  
**Impact:** Every `take_screenshot` command writes a file to `data/desktop_screenshots/` with no deletion. The original VF-1 backup growth bug (2,522 files) was fixed in Sprint 0. Desktop screenshots are the same class of problem, currently uncapped.  
**Root cause:** `TakeScreenshotAction.execute()` (`actions/vision_actions.py:163–182`) has no cleanup logic. The roadmap spec for S2.7 was not implemented.  
**Files:** `actions/vision_actions.py:163–182`  
**Fix:** After a successful screenshot, enumerate `data/desktop_screenshots/` and delete all but the 10 most recent. Identical pattern to `cleanup_old_backups()` in `core/persistent_json.py`.  
**Effort:** 30 minutes

---

## B06 — Smoke script has stale assertion
**Severity:** MEDIUM  
**Impact:** `scripts/smoke_phase70_agent_architecture.py:37` asserts `agent_for_intent(Intent.OPEN_BROWSER) == AgentId.OPERATOR`. This assertion is now wrong: S3.2 changed `OPEN_BROWSER` to route to `AgentId.BROWSER`. Running the smoke script will fail with `AssertionError`. If this script is in CI or a pre-deploy check, it blocks deployment.  
**Root cause:** Smoke script was written before Sprint 3 and not updated after the routing change.  
**Files:** `scripts/smoke_phase70_agent_architecture.py:37`  
**Fix:** Change line 37 to `assert agent_for_intent(Intent.OPEN_BROWSER) == AgentId.BROWSER`. Also update lines 33 (`len(catalog) != 7` — now 11 agents) and the `for name in (...)` loop (add new agent files).  
**Effort:** 15 minutes

---

## B07 — `validate_win32_dependencies()` never runs at startup
**Severity:** MEDIUM  
**Impact:** S3.6 was implemented and wired into `run_startup_validation()`, but `run_startup_validation()` is never called from the startup path (`core/app.py` or `runtime_bootstrap.py`). The win32/Tesseract/Playwright check is only available via the `show_startup_health` intent. A missing Tesseract is invisible until the first OCR command fails.  
**Root cause:** `core/app.py` calls `validate_intent_coverage()` and `validate_config()` directly — it never calls `run_startup_validation()`.  
**Files:** `core/app.py:39–48`, `core/startup_validation.py:139`  
**Fix:** In `core/app.py`, add a call to `validate_win32_dependencies()` (or `run_startup_validation()`) and print the result to the console at startup.  
**Effort:** 30 minutes

---

## B08 — "Semantic search" is bag-of-words token cosine, not semantic
**Severity:** MEDIUM  
**Impact:** Memory search quality is misleadingly named. `memory/semantic_runtime.py` uses token-frequency vectors — the same technology as keyword search, just with cosine distance. Acceptance case T-5 (`_semantic()` in `reliability/memory_health.py`) PASSes on token overlap, not meaning. The Memory readiness score is inflated.  
**Root cause:** `memory/semantic_runtime.py:27–42` `_vec()` function tokenizes on whitespace and counts token frequency. No embedding model is used. The module is named "semantic" but implements keyword matching.  
**Files:** `memory/semantic_runtime.py:27–42`, `reliability/memory_health.py` (T-5 case)  
**Fix (score only):** Rename the acceptance case from `semantic_memory_search` to `keyword_memory_search` so the score reflects reality. **Do not add an embedding model here** — that is Sprint 4+ work.  
**Effort:** 15 minutes

---

## B09 — S1.5: Two acceptance frameworks coexist
**Severity:** MEDIUM  
**Impact:** `validation/framework.py` was created for S1.5 but never populated or used. All active acceptance tests still use `reliability/hardening_core.py`. Developers face two modules that appear to do the same thing. New acceptance cases added to `validation/framework.py` would be dead code.  
**Root cause:** S1.5 was not executed. `reliability/hardening_core.py` was not migrated.  
**Files:** `validation/framework.py`, `reliability/hardening_core.py`, all `reliability/*.py` files  
**Fix:** Either (a) delete `validation/framework.py` and mark S1.5 as deferred to Sprint 4, or (b) complete the migration (Sprint 4 scope). Do not add new code to `validation/framework.py` until it is the active framework.  
**Effort:** 15 minutes to delete; 1 day to migrate

---

## B10 — Telegram client is a 2-line stub
**Severity:** MEDIUM  
**Impact:** `HealthMonitorAgent._heartbeat_loop()` calls `notify_overlay_error()` on critical storage events. But the roadmap specifies Telegram as the delivery channel for critical alerts. The `integrations/telegram_client.py` file contains no implementation. Critical alerts have no off-machine delivery path.  
**Root cause:** S6.3 (Telegram) is Sprint 6 work. But the file exists with no stub warning, making it appear like a real module.  
**Files:** `integrations/telegram_client.py`  
**Fix:** Add a docstring/comment that the file is a stub pending Sprint 6. No code change needed. Score impact: 0 (already at 12%).  
**Effort:** 5 minutes

---

## B11 — Browser mock counted as browser success
**Severity:** HIGH  
**Impact:** Every browser acceptance test runs against `browser/runtime.py` mock provider. `BrowserRuntimeState.last_action_success` is set to `True` by mock operations. Any acceptance case checking `last_action_success` will PASS even though no real browser was opened. Browser readiness is reported as higher than actual.  
**Root cause:** `browser/runtime.py:23` `provider: str = "mock"`. No Playwright installation exists. Mock functions return `_MOCK_BANNER` strings and set `last_action_success = True`.  
**Files:** `browser/runtime.py`, `reliability/` browser acceptance case (if any)  
**Fix:** In browser acceptance cases, add a check: if `state.provider == "mock"`, return `(None, "SKIP: no real browser provider installed")`. Do not count mock success as browser readiness.  
**Effort:** 1 hour

---

## B12 — Health monitor critical alerts silently fail when overlay is disabled
**Severity:** MEDIUM  
**Impact:** `HealthMonitorAgent._heartbeat_loop()` calls `notify_overlay_error()` on critical events. If the overlay is disabled (common in headless/background/test environments), the alert is silently dropped. No fallback delivery path exists (Telegram is a stub; no console output in the heartbeat thread).  
**Root cause:** `agents/health_monitor_agent.py:191–196` calls `notify_overlay_error()` in a `try/except Exception: pass` block. If the overlay is not running, the exception is swallowed.  
**Files:** `agents/health_monitor_agent.py:191–196`  
**Fix:** Add a `logger.critical("Storage alert: %s", msg)` call that always executes, regardless of overlay state. This ensures the alert appears in logs even if no overlay is running.  
**Effort:** 15 minutes

---

## B13 — `executive_agent.capability_catalog()` returns 7, but 11 agents exist
**Severity:** LOW  
**Impact:** `scripts/smoke_phase70_agent_architecture.py:33` asserts `len(catalog) != 7`. The registry now has 11 agents (7 original + BROWSER, DESKTOP, TRADING, HEALTH_MONITOR). If `capability_catalog()` is not updated, the smoke test fails or reports wrong count.  
**Root cause:** `agents/executive_agent.py` `capability_catalog()` was written before Sprint 3 added 4 new agents.  
**Files:** `agents/executive_agent.py` (capability_catalog method), `scripts/smoke_phase70_agent_architecture.py:33`  
**Fix:** Update `capability_catalog()` to include the 4 new agent capabilities. Update smoke assertion from `!= 7` to `!= 11`.  
**Effort:** 30 minutes

---

## B14 — `run_startup_validation()` result never shown to user
**Severity:** LOW  
**Impact:** `validate_win32_dependencies()` (S3.6) runs on-demand via `show_startup_health` intent but is not shown at startup. Users who don't issue this command never know Tesseract is missing. The win32 check's value is zero if it's invisible.  
**Root cause:** `run_startup_validation()` is not in the startup code path (B07 duplicate root cause).  
**Files:** `core/app.py`, `core/startup_validation.py`  
**Fix:** Same as B07 — call `validate_win32_dependencies()` at startup and print the result to console.  
**Effort:** 30 minutes (combined with B07)

---

## B15 — Memory vacuum only runs when file is > 1 hour old
**Severity:** LOW  
**Impact:** In development, the memory store is written and read frequently. If the file is newer than 1 hour (typical after active use), the startup vacuum never runs, allowing expired entries to accumulate. In production with low activity, the 1-hour threshold is fine. In dev, expired entries persist until manually triggered.  
**Root cause:** `memory/store.py:13` `_VACUUM_MIN_AGE_SECONDS = 3600`. `_startup_vacuum()` at line 86 checks `age_seconds >= _VACUUM_MIN_AGE_SECONDS`.  
**Files:** `memory/store.py:13, 86`  
**Fix (optional):** Lower threshold to 300s (5 min) for dev, or expose a `force_vacuum` flag. Not a production blocker.  
**Effort:** 5 minutes

---

## B16 — TTS acceptance case SKIPs every time (no live TTS call made in tests)
**Severity:** MEDIUM  
**Impact:** `reliability/voice_health.py:86–97` `_tts_backend()` returns SKIP when no TTS call has been made in the current process. In test environments (where no audio hardware exists), TTS is never called, so this case always SKIPs. The TTS backend is never verified by acceptance tests, only by live usage. A broken TTS backend can ship silently.  
**Root cause:** The SKIP condition at `voice_health.py:93–95` is correct for the no-hardware case. But there is no test that exercises TTS in a controlled way.  
**Files:** `reliability/voice_health.py:86–97`, `tests/test_tts.py`  
**Fix:** In the acceptance case, if `TTS_SAFE_MODE` is True or TTS is disabled by config, return SKIP. Otherwise attempt a 0-length TTS call (dry run) and report the backend. This makes the case produce a real result in non-hardware tests.  
**Effort:** 1 hour

---

## B17 — `data/command_audit.jsonl` and `runtime_traces.jsonl` may not use rotating writer
**Severity:** MEDIUM  
**Impact:** S0.2 (JSONL rotation) was verified for `observability_events.jsonl` and `command_history.jsonl`. It is unverified whether `command_audit.jsonl` and `runtime_traces.jsonl` use `RotatingJSONLWriter` or bare `open("a")`. If they use bare open, they will grow without bound.  
**Root cause:** S0.2 verification was incomplete — only two of four JSONL files were confirmed.  
**Files:** Wherever `command_audit.jsonl` and `runtime_traces.jsonl` are written (search: `command_audit`, `runtime_traces`).  
**Fix:** Grep for all `open(...command_audit` and `open(...runtime_traces` calls. Replace bare opens with `RotatingJSONLWriter`.  
**Effort:** 30 minutes to verify + fix if needed

---

## B18 — `session_memory.py` and `PersonalMemoryStore` are two separate memory systems
**Severity:** MEDIUM  
**Impact:** The system has two memory stores. `memory/session_memory.py` stores session-scoped data in its own JSON file. `memory/store.py` `PersonalMemoryStore` handles persistent memory. Entries in session memory are not searchable via `search_memory` intent. Multi-session context is fragmented.  
**Root cause:** Sprint 4 item (S4.1) not yet done.  
**Files:** `memory/session_memory.py`, `memory/store.py`  
**Fix:** Sprint 4 item — route `session_memory` writes through `PersonalMemoryStore.remember(category="session")`.  
**Effort:** 2 days (Sprint 4)

---

## B19 — Desktop screenshot flow has no confirmation gate for file writes
**Severity:** LOW  
**Impact:** `TakeScreenshotAction` writes screen captures to disk without any confirmation. Depending on what's on screen, this could capture sensitive information silently. The confirmation-gated pattern used for clipboard (`CopyTextToClipboardAction`) is not applied here.  
**Root cause:** `actions/vision_actions.py:163–182` — no `confirmation.pending_confirm()` call.  
**Files:** `actions/vision_actions.py:163–182`  
**Fix:** Add confirmation requirement to `TakeScreenshotAction` when `save=True`. (No change needed for the visual preview path.)  
**Effort:** 30 minutes

---

## B20 — Agent health_check for OPERATOR always returns True (shim acknowledged)
**Severity:** LOW  
**Impact:** `agents/registry.py:229` registers `AgentId.OPERATOR` with `health_check=lambda: True`. The operator agent is a legacy shim. Its health check always passes regardless of state. This inflates the agent health validation slightly (one guaranteed PASS in the registry validate() output).  
**Root cause:** `registry.py:229`: `health_check=lambda: True,  # shim; browser + desktop each have real checks`.  
**Files:** `agents/registry.py:225–231`  
**Fix:** Remove `AgentId.OPERATOR` from the registry entirely (it has `intent_prefixes=()` — no intents route to it anyway). This is a safe dead-agent removal.  
**Effort:** 15 minutes

---

## Fastest Path to 90% Product Readiness

Ranked by `(readiness_impact) / (effort)`. Items that fix fake/inflated scores OR eliminate real P0 risk first.

### Tier 1: 15 minutes each, immediate impact

1. **Fix stale smoke script (B06)** — prevents CI/smoke failure. `smoke_phase70_agent_architecture.py:37`. 15 min.
2. **Log critical alerts regardless of overlay (B12)** — ensures storage crises surface in all environments. `agents/health_monitor_agent.py:191–196`. 15 min.
3. **Rename "semantic" acceptance case to "keyword" (B08)** — removes score inflation from false naming. `reliability/memory_health.py`. 15 min.

### Tier 2: 30 minutes each, production safety

4. **Make `validate_config()` abort on fatal errors (B04)** — `runtime_bootstrap.py:66`. 30 min.
5. **Implement S2.7 screenshot cleanup (B05)** — `actions/vision_actions.py:163`. 30 min.
6. **Print win32/Tesseract/Playwright check at startup (B07 + B14)** — `core/app.py`. 30 min.
7. **Verify command_audit.jsonl + runtime_traces.jsonl rotation (B17)** — search + fix. 30 min.

### Tier 3: 1–2 hours, significant readiness gain

8. **Start watchdog in all modes, not just tray (B02)** — recovery readiness jumps from 45%→70%. `runtime_bootstrap.py`. 2–3 hrs.
9. **Register voice loop + TTS threads (B03)** — voice thread death detection. `voice/voice_loop.py`, `voice/tts.py`. 1 hr.
10. **Browser mock acceptance fix (B11)** — stops mock results counting as browser pass. 1 hr.

### Tier 4: Sprint 4+ items (do not start before current gaps are closed)

11. **Session memory unification (B18)** — Sprint 4, S4.1. 2 days.
12. **Real semantic search** — Sprint 4+. Requires embedding model.
13. **Telegram notifications (B10)** — Sprint 6, S6.3.
14. **Real browser via Playwright (B11 underlying)** — Sprint 6, S6.4.

### Expected readiness after Tier 1–3 (no new features, ~6–8 dev hours)

| Subsystem | Current | After Tier 1–3 |
|-----------|---------|----------------|
| Recovery Systems | 45% | 72% |
| Agent Architecture (honest) | 45% | 48% (score corrected) |
| Health Monitor | 65% | 78% |
| Memory (score honest) | 62% | 63% |
| Browser (score honest) | 35% | 37% |
| **Weighted avg** | **~62%** | **~68%** |

### To reach 90%:
- Tier 1–3 fixes: +6% composite
- Sprint 4 (memory, TTS consolidation): +6%
- Sprint 5 (voice hardening, barge-in): +8%
- Sprint 6 (real integrations + Playwright browser): +14%

**Honest estimate: 90% is achievable in ~8 weeks if the remaining sprint work is executed without inflation.**  
**Current honest state: ~62% composite, not the ~76% estimated post-Sprint-3.**
