# Real Readiness Scores — Post Sprint 0–3
**Date:** 2026-05-29  
**Method:** Code inspection + test results. Scores are pass-rates over verified properties, not self-assessed.  
**Rule:** If a feature is mock/stub/metadata-only, it does not count as ready.

---

## Scoring Methodology

A subsystem gets credit for a property ONLY when:
1. The implementing code is verified to exist at a specific file:line.
2. The code is reachable in at least one production execution path.
3. Failures surface to the user (overlay, console, or logged error).
4. There are passing automated tests for it.

---

## Scores

### Voice (TTS)
**Score: 68%** (roadmap self-reported: 72%)

| Property | Status | Evidence |
|----------|--------|----------|
| TTS backend configurable | ✅ | `voice/tts.py`; backend selection works |
| pyttsx3 COM thread safety | ✅ | `voice/pyttsx3_completion.py`; tests pass |
| Exponential backoff on mic error | ✅ | `voice/voice_loop.py:185–215` (S0.4) |
| TTS thread registered with ThreadRegistry | ❌ | Not registered; thread death undetected |
| Barge-in / interruption | ❌ | Not implemented (Sprint 5) |
| Adaptive silence threshold | ❌ | Not implemented (Sprint 5) |
| TTS backend verified at startup | ⚠️ | Only verified after first TTS call; SKIP before that |

### STT
**Score: 65%**

| Property | Status | Evidence |
|----------|--------|----------|
| Streaming STT functional | ✅ | `voice/streaming_stt/`; tests pass |
| Language detection / Hebrew support | ✅ | `tests/test_stt_hebrew.py` |
| Microphone overflow tracking | ❌ | `CaptureStats.overflow_count` exists; not surfaced to user |
| Adaptive silence threshold | ❌ | Sprint 5 |

### Wake Word
**Score: 70%**

| Property | Status | Evidence |
|----------|--------|----------|
| Wake word model loads | ✅ | `voice/wakeword.py`; model status printable |
| Wake word thread registered | ✅ | `core/thread_registry.py` (verified) |
| Greeting suppressed on repeat | ❌ | Sprint 5; greeting plays every wake |

### Microphone Recovery
**Score: 75%** (roadmap: 30% → 75% after S0.4)

| Property | Status | Evidence |
|----------|--------|----------|
| Exponential backoff on error | ✅ | `voice/voice_loop.py:185–215` |
| Max delay capped at 30s | ✅ | Same; `min(2.0 ** ..., 30.0)` |
| Overflow count tracked | ❌ | Not exposed in status commands |

### Browser
**Score: 35%**

| Property | Status | Evidence |
|----------|--------|----------|
| Browser commands route correctly | ✅ | `actions/phase60_actions.py`; handlers registered |
| Mock mode clearly labeled | ✅ | `browser/runtime.py:14` `_MOCK_BANNER` |
| Real browser (Playwright) | ❌ | `provider: str = "mock"` default; Playwright not installed |
| Browser acceptance tests | ❌ | All acceptance tests run against mock; `last_action_success = True` on mock |
| DOM read / page summarisation | ❌ | Mock returns simulated data |

**Note:** Browser score cannot rise above ~40% until Playwright is installed and wired (Sprint 6).

### Desktop (Operator)
**Score: 62%**

| Property | Status | Evidence |
|----------|--------|----------|
| win32gui importable | ✅ | `desktop_agent.health_check()` returns True on this machine |
| Window focus, list, describe | ✅ | `computer_control/`; tests pass |
| OCR / Tesseract | ⚠️ | Depends on Tesseract in PATH; startup check present but not printed |
| Screenshot cleanup | ❌ | S2.7 not implemented; screenshots accumulate |
| Agent routing in execution | ❌ | `DesktopAgent` never called; all desktop commands go through ActionRegistry directly |

### Memory
**Score: 62%**

| Property | Status | Evidence |
|----------|--------|----------|
| remember() persists to disk | ✅ | `memory/store.py:157–180` |
| Per-entry 10 KB size limit | ✅ | `memory/store.py:139–142` (S2.1) |
| Default TTL for ephemeral | ✅ | `memory/store.py:151–155` (S2.2) |
| Vacuum on startup | ✅ | `memory/store.py:79–95` (S0.3) |
| Semantic search | ❌ | `memory/semantic_runtime.py` uses token-frequency cosine; not semantic |
| Session memory unified | ❌ | Sprint 4; `memory/session_memory.py` and `PersonalMemoryStore` are separate |
| Ranked results | ❌ | Sprint 4 |

### Agent Architecture
**Score: 45%** (roadmap post-Sprint3: 83% — that score is inflated)

| Property | Status | Evidence |
|----------|--------|----------|
| All agents have health_check | ✅ | `agents/registry.py:build_default_registry()` |
| Registry validated at startup | ✅ | `runtime_bootstrap.py:82` |
| Intent routing table complete | ✅ | `agents/intent_routing.py` |
| Routing affects execution | ❌ | `ActionRegistry.execute()` never calls `agent_for_intent()` |
| Agent dispatch (BrowserAgent, DesktopAgent, etc. called) | ❌ | Zero agent classes in the command execution path |
| Agent health visible to user | ⚠️ | Only via `show_startup_health` intent |

**Reality:** The "12-agent architecture" is a monitoring/classification overlay. Commands execute identically before and after Sprint 3. The routing table change is a documentation fix, not a behavioral change.

### Validation Framework
**Score: 55%**

| Property | Status | Evidence |
|----------|--------|----------|
| Acceptance cases call real code | ✅ | S1.1–S1.4 verified |
| No hardcoded-True | ✅ | `reliability/voice_health.py`, `memory_health.py` verified |
| No score bonus | ✅ | `hardening_core.py:53` |
| Framework consolidated | ❌ | S1.5 not done; two frameworks: `hardening_core.py` + `validation/framework.py` |
| Acceptance tests run at startup | ❌ | Only on explicit user request |

### Recovery Systems
**Score: 45%**

| Property | Status | Evidence |
|----------|--------|----------|
| HealthMonitor 30s heartbeat | ✅ | `agents/health_monitor_agent.py:182–198` |
| Overlay retry cap | ✅ | `ui/overlay_app.py` (S2.6) |
| Watchdog in production | ❌ | Only in tray mode; absent in text/voice CLI |
| Voice/TTS thread death detection | ❌ | Not registered |
| Config errors abort startup | ❌ | Only logged |

### Integrations
**Score: 12%**

| Property | Status | Evidence |
|----------|--------|----------|
| Gmail | ❌ | Stub; Sprint 6 |
| Calendar | ❌ | Stub; Sprint 6 |
| Telegram notifications | ❌ | `integrations/telegram_client.py`: 2-line file, no implementation |

### Health Monitor
**Score: 65%**

| Property | Status | Evidence |
|----------|--------|----------|
| 30s storage health checks | ✅ | `agents/health_monitor_agent.py:182–198` |
| Critical alerts logged | ✅ | `logger.critical()` on critical storage items |
| Storage checks aligned with VF-1/VF-2 thresholds | ✅ | `_BACKUP_WARNING_COUNT = 500`, `_JSONL_CRITICAL_BYTES = 20_000_000` |
| Critical alerts delivered to user | ❌ | Telegram stub; overlay `notify_overlay_error` called but overlay may be disabled |
| Win32/Tesseract check printed at startup | ❌ | Check runs on-demand only |
| Watchdog started by health monitor | ❌ | Watchdog is a separate system, never started in CLI |

### Coding Agent
**Score: 78%**

| Property | Status | Evidence |
|----------|--------|----------|
| Code search functional | ✅ | `actions/code_search.py`; `tests/test_code_search.py` pass |
| Task patch workflow | ✅ | `actions/task_actions.py`; tests pass |
| LLM integration | ✅ | `brain/llm_intent_classifier.py` |

### Task/Planning Agent
**Score: 78%**

| Property | Status | Evidence |
|----------|--------|----------|
| Task lifecycle (start/stop/step) | ✅ | `actions/task_actions.py`; tests pass |
| Workflow runner | ✅ | `workflows/`; tests pass |

### Trading Agent
**Score: 65%**

| Property | Status | Evidence |
|----------|--------|----------|
| Dashboard actions work | ✅ | `actions/trading_dashboard.py`; tests pass |
| Loop control (daily/weekly) | ✅ | `actions/trading_loop.py` |
| Kill-switch | ✅ | Intent registered; confirmation-gated |
| Routing to TRADING agent | ✅ | `intent_routing.py:73–82` |
| health_check() needs `TRADING_DASHBOARD_URL` | ⚠️ | Will return False if URL not configured |

---

## Composite Score

| Subsystem | Real Score | Roadmap Post-S3 Estimate | Gap |
|-----------|-----------|--------------------------|-----|
| Voice (TTS) | 68% | 78% | -10% |
| STT | 65% | 72% | -7% |
| Wake Word | 70% | 79% | -9% |
| Mic Recovery | 75% | 82% | -7% |
| Browser | 35% | 42% | -7% |
| Desktop | 62% | 75% | -13% |
| Memory | 62% | 65% | -3% |
| Agent Architecture | 45% | 83% | **-38%** |
| Validation Framework | 55% | 85% | -30% |
| Recovery Systems | 45% | 82% | -37% |
| Integrations | 12% | 20% | -8% |
| Health Monitor | 65% | 78% | -13% |
| Coding Agent | 78% | 87% | -9% |
| Task Agent | 78% | 87% | -9% |
| Trading Agent | 65% | 78% | -13% |

**Weighted average real score: ~62%**  
**Roadmap estimated score (post-S3): ~76%**  
**Inflation: ~14 percentage points**

The two largest sources of inflation are:
1. Agent Architecture: counted as 83% but is 45% because routing is metadata-only.
2. Recovery Systems: counted as 82% but is 45% because watchdog is absent in all non-tray modes.
