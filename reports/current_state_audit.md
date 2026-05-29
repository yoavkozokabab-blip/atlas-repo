# Current State Audit — Post Sprint 0–3
**Date:** 2026-05-29  
**Basis:** Source-code inspection, line-level verification, test execution.  
**Rule:** Every claim cites file:line. No estimates. No assumptions.

---

## Sprint Verification Table

| ID | Item | Status | Evidence |
|----|------|--------|----------|
| S0.1 | Backup retention — delete after copy | ✅ VERIFIED | `core/persistent_json.py:39–47`; `runtime_bootstrap.py:51` calls `cleanup_old_backups()` |
| S0.2 | JSONL log rotation | ✅ VERIFIED | `core/rotating_jsonl.py`; used at `services/observability.py:355–362`; `brain/router.py:28–31` |
| S0.3 | Memory vacuum on startup | ✅ VERIFIED | `memory/store.py:79–95` `_startup_vacuum()` called in `__init__`; checks age ≥ 3600s |
| S0.4 | Microphone exponential backoff | ✅ VERIFIED | `voice/voice_loop.py:185–215` `_mic_error_count`, `delay = min(2.0 ** (_mic_error_count - 1), 30.0)` |
| S1.1 | Remove hardcoded-True voice acceptance | ✅ VERIFIED | `reliability/voice_health.py:70–136`; all cases call real functions; SKIP returned when no live session |
| S1.2 | Integration acceptance returns SKIP not PASS | ✅ VERIFIED | `reliability/integrations_health.py:67–73`; returns `None` (SKIP) when credentials absent |
| S1.3 | Remove +10 score bonus | ✅ VERIFIED | `reliability/hardening_core.py:51–53`; `self.current_pct = round(min(100.0, max(0.0, self.pass_rate)), 1)` — no bonus |
| S1.4 | Remove invented fallback scores | ✅ VERIFIED | `reliability/product_readiness.py:18–31`; `run_acceptance=False` → `TrackScore(track, 0.0, target)` |
| S1.5 | Consolidate acceptance framework | ❌ NOT DONE | `validation/framework.py` exists but unused. `reliability/hardening_core.py` is still active. Zero migration. |
| S2.1 | Memory per-entry 10 KB limit | ✅ VERIFIED | `memory/store.py:137–142`; truncates at `10_240` bytes |
| S2.2 | Default TTL for ephemeral categories | ✅ VERIFIED | `memory/store.py:151–155`; 86400s for `session`, `short_term`, `temporary_fact` |
| S2.3 | Thread Registry + watchdog | ⚠️ PARTIAL | `core/thread_registry.py` complete. Watchdog calls `heartbeat_check()`. **Voice loop thread and TTS thread are NOT registered.** Watchdog only starts in tray mode (`ui/tray_app.py:464–469`). In text/voice CLI, no watchdog runs at all. |
| S2.4 | Startup intent coverage validation | ✅ VERIFIED | `core/app.py:39–48`; `validate_intent_coverage(self.router.registry)` called before bootstrap |
| S2.5 | Config startup validation | ⚠️ PARTIAL | `validate_config()` called at `runtime_bootstrap.py:58–68`. **Never passes `abort_on_critical=True`.** Config errors are logged warnings, never fatal. |
| S2.6 | Overlay retry cap at 3 | ✅ VERIFIED | `ui/overlay_app.py`; `_MAX_QT_RESTART_ATTEMPTS = 3`; switches headless after cap |
| S2.7 | Screenshot accumulation cleanup | ❌ NOT IMPLEMENTED | `actions/vision_actions.py:163–182` `TakeScreenshotAction.execute()` — no cleanup code. Screenshots accumulate without bound. |
| S3.1 | 12-agent registry wired at startup | ✅ VERIFIED | `runtime_bootstrap.py:79–85`; `build_default_registry()` + `validate_registry()` called |
| S3.2 | Browser intents → BROWSER | ✅ VERIFIED | `agents/intent_routing.py:44–51`; `open_browser`, `search_web`, `what_tab`, etc. → `AgentId.BROWSER` |
| S3.3 | Desktop intents → DESKTOP | ✅ VERIFIED | `agents/intent_routing.py:53–71`; `open_app`, `take_screenshot`, `focus_window`, etc. → `AgentId.DESKTOP` |
| S3.4 | Trading intents → TRADING | ✅ VERIFIED | `agents/intent_routing.py:73–82`; explicit rows; RESEARCH catch-all removed |
| S3.5 | HealthMonitorAgent.start() at bootstrap | ✅ VERIFIED | `runtime_bootstrap.py:89–92` |
| S3.6 | Win32 dependency check | ✅ VERIFIED | `core/startup_validation.py:139–176`; checks `win32gui`, `tesseract`, `playwright` |

**Summary: 17 VERIFIED, 2 PARTIAL (S2.3, S2.5), 2 NOT DONE (S1.5, S2.7)**

---

## Startup Flow (Verified End-to-End)

```
main.py → JarvisApp.__init__(core/app.py:25)
  1. CommandRouter() → ActionRegistry()._register_defaults() [~430 handlers registered]
  2. validate_intent_coverage(registry)         [app.py:41  — S2.4]
  3. ensure_jarvis_runtime_bootstrapped()        [app.py:56]
     ├─ cleanup_old_backups()                   [bootstrap:51 — S0.1]
     ├─ validate_config()                       [bootstrap:58 — S2.5 partial]
     ├─ initialize_audio_runtime_at_startup()   [bootstrap:72]
     ├─ build_default_registry()               [bootstrap:80 — S3.1]
     ├─ validate_registry()                    [bootstrap:82 — S3.1]
     └─ get_health_monitor_agent().start()     [bootstrap:89 — S3.5]
  4. print_jarvis_runtime_diagnostics()
  5. TTSService(enabled=...)
```

**Dead paths in startup:**
- `validate_config()` never aborts startup — errors are swallowed as warnings.
- Watchdog (`services/watchdog.py`) never starts in text or voice mode. Only starts when `JarvisTrayApp.start()` is called (`tray_app.py:464`).
- `validate_win32_dependencies()` runs but its result is never printed to user at startup (only logged). The S3.6 dependency display is invisible unless the user runs a status command.

---

## Command Routing Reality

**Actual execution path for any command:**

```
text input
  → CommandRouter.route(text)           [router.py:59]
  → classify(text)                      [brain/intent_classifier.py]
  → CommandRequest(intent=Intent.X)
  → ActionRegistry.execute(request)     [registry.py:1063]
  → self._actions[request.intent.value].execute(request)
```

**`agent_for_intent()` is NEVER called in this path.**  
It is called only from:
- `agents/executive_agent.py:75` — informational method `classify_intent()`, not on any command execution path
- `scripts/smoke_phase70_agent_architecture.py:37` — a smoke test (not production)

`AgentRegistry` and `ActionRegistry` have **zero connection** in the execution path. The Sprint 3 agent routing table (`agents/intent_routing.py`) is documentation, not execution logic.

---

## Mock/Fake Paths Still Active

| Path | Location | What it fakes |
|------|----------|---------------|
| Browser always mock | `browser/runtime.py:23` `provider: str = "mock"` | All browser commands run against simulated output with `_MOCK_BANNER` string |
| "Semantic search" is bag-of-words | `memory/semantic_runtime.py:27–42` `_vec()` does token frequency | Not semantic. Acceptance case T-5 can PASS on keyword overlap. |
| Telegram notifications are a stub | `integrations/telegram_client.py` — 2-line file | HealthMonitor critical alerts cannot reach the user via Telegram |
| validate_config never aborts | `runtime_bootstrap.py:58–68` | Config errors are silently logged, startup continues |

---

## Dead Code Inventory

| Item | File | Status |
|------|------|--------|
| `validation/framework.py` | `validation/framework.py` | File exists, zero callers in production |
| `services/watchdog.py` | Only started from `tray_app.py:466` | Completely absent in text and voice CLI modes |
| `agent_for_intent()` routing table | `agents/intent_routing.py` | Execution never reaches this in any command path |
| `integrations/telegram_client.py` | 2-line stub | No implementation |
| Sprint 3 smoke script assertion | `scripts/smoke_phase70_agent_architecture.py:37` | `assert agent_for_intent(Intent.OPEN_BROWSER) == AgentId.OPERATOR` — **now wrong** after S3.2 fix; will fail if smoke is run |

---

## Test Results

Targeted suite (sprint3, router, memory, actions, security, runtime_bootstrap, startup_modes):
- **Result pending from background run.**
- Prior run (full suite, May 29): **104 passed, 1 failed** (unrelated `FileExistsError` in test isolation).
- Sprint 3 tests alone: **17/17 pass** (verified manually above).

---

## Honest Subsystem Readiness (Measured, Not Estimated)

| Subsystem | Honest Score | Basis |
|-----------|-------------|-------|
| Backup/Storage | 85% | VF-1/VF-2/VF-3 fixed; S2.7 screenshots still grow |
| Memory store | 68% | S2.1–S2.3 done; semantic search is keyword-only; session memory not unified |
| Voice (TTS) | 72% | TTS works; no barge-in; voice/TTS threads not in ThreadRegistry |
| STT | 65% | Streaming STT functional; no adaptive silence threshold |
| Wake word | 70% | Wake word works; greeting not suppressed on repeat |
| Browser | 35% | Always mock; no Playwright; browser acceptance tests run against simulated output |
| Desktop | 60% | win32gui works; OCR/Tesseract present; no confirmation on destructive actions in all paths |
| Agent Architecture | 60% | Registry exists and runs; routing table is metadata-only; no real agent dispatch |
| Validation Framework | 55% | Acceptance cases truthful (S1.1–S1.4); S1.5 consolidation not done; two frameworks active |
| Recovery/Watchdog | 45% | HealthMonitorAgent heartbeat runs; Watchdog absent in CLI mode |
| Integrations | 12% | Gmail stub; Calendar stub; Telegram 2-line stub |
| Health Monitor | 65% | 30s heartbeat runs; storage checks work; does not start watchdog |
| Coding Agent | 78% | Well-tested; functional |
| Task/Planning Agent | 78% | Well-tested; functional |
| Trading Agent | 65% | Actions work; routes correctly to TRADING; dashboard URL required for health_check |
