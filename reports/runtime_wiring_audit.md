# Runtime Wiring Audit — Post Sprint 0–3
**Date:** 2026-05-29  
**Question:** For every Sprint 0–3 implementation — is it reachable in production execution?

---

## Wiring Status per Item

### S0.1 — Backup cleanup
**Wired:** YES  
`runtime_bootstrap.py:51` → `persistent_json.cleanup_old_backups()`  
Called unconditionally on first bootstrap. Always reachable.

### S0.2 — JSONL rotation
**Wired:** YES (partial)  
`services/observability.py:355–362` uses `RotatingJSONLWriter` via `_get_jsonl_writer()`.  
`brain/router.py:28–31` uses `RotatingJSONLWriter` for command history.  
**Gap:** `command_audit.jsonl` and `runtime_traces.jsonl` — verify each uses the rotating writer vs bare `open("a")`.

### S0.3 — Memory vacuum
**Wired:** YES  
`memory/store.py:77` calls `_startup_vacuum()` in `__init__`. Every instantiation of `PersonalMemoryStore` runs it.

### S0.4 — Mic backoff
**Wired:** YES  
`voice/voice_loop.py:185–215` is in the active voice loop execution path.

### S1.1–S1.4 — Acceptance test truthfulness
**Wired:** YES (but acceptance tests are not run on every startup)  
`run_voice_acceptance()` etc. are called only when a readiness report is explicitly requested (`generate_product_readiness_report` intent or `run_jarvis_health_check` intent). They do NOT run automatically on startup.  
**Impact:** Corrected acceptance tests only produce accurate scores when the user explicitly requests them.

### S1.5 — Framework consolidation
**Wired:** N/A — NOT DONE  
`validation/framework.py` exists. Zero callers. `reliability/hardening_core.py` is the active acceptance framework for all reliability tracks.

### S2.1–S2.2 — Memory size limit + default TTL
**Wired:** YES  
Both checks live inside `PersonalMemoryStore.remember()` (`memory/store.py:130–155`). Called on every `remember()` invocation.

### S2.3 — Thread Registry
**Wired:** PARTIAL  
`core/thread_registry.py` — complete implementation.  
`services/watchdog.py:86` calls `ThreadRegistry.heartbeat_check()`.  
**But watchdog never starts in CLI mode.** Only starts in tray: `ui/tray_app.py:466`.  
**Registered threads (confirmed):** `jarvis-health-monitor`, `jarvis-overlay-queue`, `jarvis-overlay-qt`, `jarvis-wakeword`.  
**NOT registered:** voice loop main thread, TTS thread.  
**Result:** Thread death detection is absent for the two most critical real-time threads.

### S2.4 — Intent coverage validation
**Wired:** YES  
`core/app.py:39–48` — runs before every startup. If a handler is missing, a WARNING is logged but startup continues (does not abort).

### S2.5 — Config validation
**Wired:** PARTIAL  
`runtime_bootstrap.py:58–68` calls `validate_config()`. Errors logged.  
**Never calls `run_startup_validation(abort_on_critical=True)`.** Fatal config errors (unwritable DATA_DIR) produce a warning, not an exit.

### S2.6 — Overlay retry cap
**Wired:** YES  
`ui/overlay_app.py` — cap is enforced whenever the overlay restarts.

### S2.7 — Screenshot cleanup
**Wired:** NO — NOT IMPLEMENTED  
`TakeScreenshotAction.execute()` at `actions/vision_actions.py:163–182` contains no cleanup logic. Screenshots accumulate in `data/desktop_screenshots/` without bound.

### S3.1 — Agent registry at startup
**Wired:** YES (but monitoring only)  
`runtime_bootstrap.py:80–84` builds and validates registry on first bootstrap.  
**Critical:** Registry validation runs health checks, but failures produce warnings only. The registry has **no connection to command execution** (`ActionRegistry.execute()` is fully independent).

### S3.2/S3.3 — Browser/Desktop routing
**Wired:** NO (in execution path)  
`agents/intent_routing.py` has correct routes. But `ActionRegistry.execute()` (`actions/registry.py:1063`) never calls `agent_for_intent()`. Routing table is metadata; it does not affect which code executes.  
**Net effect of S3.2/S3.3:** Zero change to runtime behavior. Same action handlers execute for browser and desktop commands as before.

### S3.4 — Trading routing
**Wired:** NO (in execution path)  
Same as S3.2/S3.3 — routing table metadata only.

### S3.5 — HealthMonitorAgent started
**Wired:** YES  
`runtime_bootstrap.py:89–92` calls `start()`. Daemon thread runs storage checks every 30s. Registered with ThreadRegistry.

### S3.6 — Win32 dependency check
**Wired:** YES (but invisible at startup)  
`run_startup_validation()` calls `validate_win32_dependencies()` and returns results in dict key `"dependencies_missing"`. However:
- `run_startup_validation()` is not called from `core/app.py` or `runtime_bootstrap.py`. It is only called from `actions/operating_layer_actions.py:ShowStartupHealthAction` (the `show_startup_health` intent) and tests.
- `validate_win32_dependencies()` is never called in the startup path — only `validate_config()` and `validate_intent_coverage()` are called at startup.  
**Result:** S3.6 win32 checks are available on-demand but do NOT run automatically at startup.

---

## Execution Path Truth Table

| Command | Action Handler | Agent class involved in execution? |
|---------|---------------|-------------------------------------|
| "open browser" | `OpenBrowserAction` (`actions/phase60_actions.py`) | NO — `BrowserAgent` never called |
| "take screenshot" | `TakeScreenshotAction` (`actions/vision_actions.py`) | NO — `DesktopAgent` never called |
| "run live daily loop" | `RunLiveDailyLoopAction` (`actions/trading_loop.py`) | NO — `TradingAgent` never called |
| "show system health" | `ShowSystemHealthAction` (`actions/phase65_hardening_actions.py`) | NO — `HealthMonitorAgent.run_full_health_check()` not called from here |
| "remember X" | `RememberFactAction` (`actions/memory_actions.py`) | NO — `MemoryAgent.remember()` calls `PersonalMemoryStore` directly |
| Any intent | `ActionRegistry.execute()` → handler.execute() | NO agent class in path for any intent |

---

## Summary: What Is Actually Wired

| Category | Wired | Not Wired / Dead |
|----------|-------|-----------------|
| Storage cleanup (S0.1–S0.3) | ✅ | |
| Mic backoff (S0.4) | ✅ | |
| Acceptance truthfulness (S1.1–S1.4) | ✅ (on-demand) | |
| Framework consolidation (S1.5) | | ❌ not done |
| Memory guard rails (S2.1–S2.2) | ✅ | |
| Thread registry | ✅ partial | voice/TTS threads missing |
| Watchdog | | ❌ absent in CLI/voice modes |
| Intent coverage check (S2.4) | ✅ | |
| Config validation (S2.5) | ✅ logs only | never fatal |
| Overlay cap (S2.6) | ✅ | |
| Screenshot cleanup (S2.7) | | ❌ not implemented |
| Agent registry (S3.1) | ✅ monitoring | not in execution path |
| Browser/Desktop/Trading routing | | ❌ execution path unchanged |
| Health monitor heartbeat (S3.5) | ✅ | |
| Win32 checks (S3.6) | ✅ on-demand | not at startup |
