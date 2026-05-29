# Sprint 3.1 + 3.2 — Independent Review
**Date:** 2026-05-29
**Reviewer mandate:** Verify, with exact file/line evidence, that the Sprint 3.1/3.2 runtime-wiring fixes are real (not metadata-only). No code modified during this review.
**Method:** Source inspection + targeted test/smoke execution.

---

## Verdict Summary

| # | Claim | Verdict | Primary Evidence |
|---|-------|---------|------------------|
| 1 | Agents truly affect execution | ✅ VERIFIED | `actions/registry.py:1062-1096`, `agents/runtime_wiring.py:99-140` |
| 2 | Watchdog starts in CLI/voice/tray | ✅ VERIFIED | `main.py:243-247`, `ui/tray_app.py:489-501`, `services/watchdog_runtime.py:39-67` |
| 3 | Voice/TTS threads registered in ThreadRegistry | ✅ VERIFIED | `voice/voice_loop.py:185-195,289`, `voice/tts.py:723-727,751-777` |
| 4 | Config validation marks runtime degraded | ✅ VERIFIED | `core/startup_validation.py:300-338`, `core/runtime_state.py:104-118` |
| 5 | Dependency validation runs at startup | ✅ VERIFIED | `core/runtime_bootstrap.py:57-67` → `startup_validation.py:279-282` |
| 6 | No fake health/metadata-only success in these areas | ✅ MOSTLY — 2 honest caveats | see §6 |

**Tests:** `test_sprint32_runtime_reliability.py` (8) + `test_sprint3_agents.py` (24) = **32 passed, 0 failed**.
**Smoke:** `scripts/smoke_phase70_agent_architecture.py` → **SMOKE PASS**.

---

## 1. Agents truly affect execution — VERIFIED

`ActionRegistry.execute()` is no longer a bare intent-string lookup. It now resolves an owning agent, gates unhealthy unsafe execution, and annotates the result.

**`actions/registry.py:1062-1096`:**
- `1063-1068`: imports `resolve_execution_context`, `should_block_unhealthy_execution`, `block_unhealthy_result`, `attach_agent_runtime_metadata`.
- `1070`: `ctx = resolve_execution_context(request)` — runs `agent_for_intent()` + health check **before** the handler.
- `1087-1093`: if `should_block_unhealthy_execution(...)` → returns `block_unhealthy_result(...)` **without invoking the handler**.
- `1095-1096`: handler still dispatched exactly as before, then `attach_agent_runtime_metadata` stamps the result.

**`agents/runtime_wiring.py`:**
- `54-63`: `resolve_execution_context` → `agent_for_intent(request.intent)` (line 56) + `evaluate_agent_health` (58).
- `66-84`: `evaluate_agent_health` runs the real `health_check()` and recurses into `depends_on`.
- `99-109`: `should_block_unhealthy_execution` returns `(True, reason)` for health-gated agents (`_HEALTH_GATED_AGENTS = {BROWSER, DESKTOP, TRADING, CODING}`, line 23-28) when unhealthy and not a diagnostic intent.
- `112-120`: `attach_agent_runtime_metadata` writes `agent_id`, `agent_health`, `routing_source` into `result.data`.
- `123-140`: `block_unhealthy_result` returns `ActionStatus.FAILED` with `blocked_by_agent_health: True`.

**Behavioral proof (not tautological) — `tests/test_sprint3_agents.py`:**
- `test_open_browser_records_browser_agent` (295): `result.data["agent_id"] == "browser"` through real `execute()`.
- `test_unhealthy_browser_blocks_open_browser` (344): unhealthy BROWSER → `status == FAILED`, `blocked_by_agent_health is True` — handler never runs.
- `test_unhealthy_browser_allows_show_browser_health` (358): diagnostic intent `show_browser_health` still SUCCEEDS while BROWSER is unhealthy (gating exemption works).
- Desktop/Trading/Coding equivalents (308, 320, 332) all assert the recorded `agent_id`.

This is the precise gap (B01) from the prior audit, now closed: routing is consulted **inside the execution path**, not as documentation.

---

## 2. Watchdog starts in CLI / voice / tray — VERIFIED

The watchdog is no longer tray-only.

**`services/watchdog_runtime.py`** (new, Sprint 3.2):
- `39-67`: `ensure_process_watchdog()` — single-process launcher, `with _lock` + `is_watchdog_running()` guard (52) → **idempotent**.
- `29-36`: `attach_tray_to_watchdog()` upgrades an already-running headless watchdog with the tray for recovery.
- `services/watchdog_context.py:10-48`: tray-optional `WatchdogContext` — headless mode runs heartbeat-only (`restart_background_services` returns `[]` when no tray, line 39-44).

**Startup wiring:**
- `main.py:243-247`: `if not safe_mode: ensure_process_watchdog(runtime=runtime)` — placed **after** `JarvisApp` creation (241) and **before** the tray/voice/text mode branch (~326+), so it covers `--text`, `--voice`, and `--tray`. Only `--safe-mode` opts out (by design).
- `ui/tray_app.py:496-501`: tray calls `is_watchdog_running()` → `attach_tray_to_watchdog(self)` if already up, else `ensure_process_watchdog(runtime=..., tray_app=self)`. No double-start.

**Tests:** `test_ensure_process_watchdog_idempotent` (calls twice, asserts single running instance), `test_main_wires_process_watchdog` (asserts `main.py` references `ensure_process_watchdog`). Both pass.

---

## 3. Voice/TTS threads registered in ThreadRegistry — VERIFIED

**Voice loop — `voice/voice_loop.py:185-195`:**
- If running under the dedicated `jarvis-voice` thread → `registry.register("jarvis-voice-loop", current)` (190).
- Otherwise (CLI inline) → `registry.register_fn("jarvis-voice-loop", lambda: app._running and state.running and state.voice_enabled)` (192-195) — a real liveness predicate.
- `289`: `deregister("jarvis-voice-loop")` on loop exit (clean teardown, no false-dead).

**TTS — `voice/tts.py`:**
- `723`: worker thread created `name="jarvis-tts"`.
- `725-727`: `get_thread_registry().update("jarvis-tts", self._worker)` after start.
- `714-717` / `751-777`: `deregister_if_thread("jarvis-tts", worker)` on completion — correctly removes only when the registry still points at that worker (avoids clobbering a newer utterance). This is the right pattern for an ephemeral per-utterance worker.

**Heartbeat detection — `core/thread_registry.py:98-132`:** `heartbeat_check()` dereferences weakrefs (110-113) and evaluates liveness callables (115-122), returning dead names and logging CRITICAL.

**Tests:** `test_thread_registry_detects_dead_voice_and_tts` (registers both, kills them, asserts both reported dead), `test_voice_loop_registers_liveness_fn`, `test_tray_voice_thread_registered`. All pass.

---

## 4. Config validation marks runtime degraded — VERIFIED

**Severity model — `core/startup_validation.py`:**
- `37-54`: `ValidationSeverity` enum (CRITICAL/WARNING/INFO) + `StartupValidationIssue` dataclass.
- `100-162`: `validate_config()` now returns `list[StartupValidationIssue]`; DATA_DIR-unwritable → `CRITICAL` (117-121). Backward-compat string view preserved at `validate_config_messages()` (165-167).
- `300-338`: `apply_startup_validation_to_runtime()` → on any critical/warning calls `runtime.mark_degraded(...)` (312), records `startup_validation` events (315-321), and prints a clear `[JARVIS] Runtime DEGRADED` summary (322-336). Clears degraded when clean (338).

**Runtime support — `core/runtime_state.py:21-22, 104-118`:** `degraded` + `degraded_reasons` fields; `mark_degraded()` / `clear_degraded()`; surfaced in `snapshot()` (153-154).

**No hard-exit:** `run_startup_validation()` only `sys.exit(1)` when `abort_on_critical=True` (286-295); the bootstrap call path (`runtime_bootstrap.py:64`) does **not** pass it → degraded, not fatal. Matches the requirement.

**Tests:** `test_validate_config_returns_severity`, `test_critical_config_marks_runtime_degraded` (DATA_DIR-not-writable case). Both pass.

---

## 5. Dependency validation runs at startup — VERIFIED

**`core/runtime_bootstrap.py:57-67`** (first-bootstrap block): calls `run_startup_validation()` then `apply_startup_validation_to_runtime(runtime, validation, print_summary=True)`.

**`core/startup_validation.py:279-282`:** `run_startup_validation()` always calls `validate_win32_dependencies()` (checks `win32gui`, `tesseract` on PATH, `playwright.sync_api` — lines 196-233) and records `dependencies_missing`.

**Degraded, not fatal — `dependency_issues_from_availability()` (174-193):** missing optional deps become `WARNING` issues → `mark_degraded`, never `sys.exit`. On this machine `playwright` is absent, so startup legitimately reports degraded with a clear printed line.

**Tests:** `test_missing_dependencies_mark_degraded_not_fatal`, `test_run_startup_validation_includes_dependencies_key`, `test_validate_win32_dependencies_*`. All pass.

---

## 6. Fake health / metadata-only success paths in these areas

The core B01 defect (routing was metadata-only) is **eliminated** — execution is genuinely gated (§1 proof). Two honest caveats remain, both **outside the strict 3.1/3.2 surface** but worth recording:

### Caveat A — `agent_id` reaches `result.data` but NOT the structured command log
- `attach_agent_runtime_metadata` writes `agent_id`/`agent_health`/`routing_source` into `result.data` (`runtime_wiring.py:116-120`), which flows to the in-memory result, session store, and conversation store.
- However `brain/router.py:_log_command` (435-462) builds a **fixed-key** entry dict and does not embed `result.data`; `grep agent_id brain/router.py` → **no matches**.
- **Impact:** the B01 requirement "add agent_id to … logs" is met for the result object and runtime stores, but the `command_history.jsonl` line does not carry `agent_id`. Minor observability gap, not a correctness or fake-success issue.

### Caveat B — health gating is a real mechanism but rarely triggers on this host
- `_HEALTH_GATED_AGENTS` health checks all currently return healthy on this machine: `BrowserAgent.health_check` is True whenever the browser module imports (**including mock provider**, `agents/browser_agent.py:68-75`); `DesktopAgent` True because `win32gui` is present; `TradingAgent` True because `TRADING_DASHBOARD_URL` defaults to `http://127.0.0.1:8077` (`config.py:61,81`); `CodingAgent` health is `... or True` (`agents/registry.py:261`).
- **Consequence:** in normal operation gating never blocks; it is proven only via forced-unhealthy tests. This is correct and not fake — but note that a browser command in **mock** mode passes the health gate and returns mock output as SUCCESS. That browser-mock-as-success path (prior audit B11) is **Sprint 6 scope**, not a 3.1/3.2 regression.

No tautological `return True` acceptance cases or metadata-only success were found within the agent-execution, watchdog, thread-registry, config, or dependency areas.

---

## Test & Smoke Evidence (this review)

```
py -m pytest tests/test_sprint32_runtime_reliability.py tests/test_sprint3_agents.py
  → 32 passed in 4.71s

py scripts/smoke_phase70_agent_architecture.py
  → SMOKE PASS phase70_agent_architecture
```

Relevant passing tests by claim:
- §1: test_open_browser_records_browser_agent, test_unhealthy_browser_blocks_open_browser, test_unhealthy_browser_allows_show_browser_health, test_{summarize_this_screen,trading_command,coding_command}_records_*_agent
- §2: test_ensure_process_watchdog_idempotent, test_main_wires_process_watchdog
- §3: test_thread_registry_detects_dead_voice_and_tts, test_voice_loop_registers_liveness_fn, test_tray_voice_thread_registered
- §4: test_validate_config_returns_severity, test_critical_config_marks_runtime_degraded
- §5: test_missing_dependencies_mark_degraded_not_fatal, test_run_startup_validation_includes_dependencies_key

---

## Recommendations (non-blocking, no code changed here)

1. **Close Caveat A:** add `result.data.get("agent_id")` to the `_log_command` entry dict in `brain/router.py` so the agent owner appears in `command_history.jsonl`. ~10 min.
2. **Browser mock honesty (Sprint 6, tracked):** make browser acceptance SKIP when `provider == "mock"` so mock output is not counted as real browser success.
3. Consider caching per-process agent health for a short TTL — `resolve_execution_context` runs a health_check on **every** command (e.g. MEMORY's `store()._load()` does a disk read per command). Functionally correct, minor perf cost.

**Bottom line:** Sprint 3.1 + 3.2 are real, wired, and test-backed. The headline audit defect (agent routing was cosmetic) is genuinely fixed; watchdog, thread registration, config severity, and dependency checks all run in the live startup path. The only residual is a minor logging-completeness gap (Caveat A) and a pre-existing Sprint 6 browser-mock item (Caveat B).
```
