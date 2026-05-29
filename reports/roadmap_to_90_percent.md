# Roadmap to 90% Production Readiness

**Date:** 2026-05-29  
**Replaces:** Previous version in this file (overoptimistic estimates, invented scores)  
**Basis:** `audit_verification.md`, `verified_master_audit.md`, subsystem readiness reports  
**Rule:** Every sprint item maps to a specific file and line. No vague "improve X."

---

## Actual Baseline (Measured, Not Estimated)

| Subsystem | Honest Score | Self-Reported | Gap from 90% |
|-----------|-------------|--------------|-------------|
| Voice (TTS) | 72% | 65% | 18% |
| STT | 65% | (same as voice) | 25% |
| Wake Word | 70% | — | 20% |
| Microphone Recovery | 30% | — | 60% |
| Browser (mock) | 35% | 65% | 55% |
| Desktop | 60% | 50% | 30% |
| Memory | 45% | 55% | 45% |
| Agent Architecture | 55% | — | 35% |
| Validation Framework | 30% | 60% | 60% |
| Recovery Systems | 45% | 58% | 45% |
| Integrations | 12% | 12% | 78% |
| UI / Overlay | 70% | 70% | 20% |
| Coding Agent | 78% | 78% | 12% |
| Task Agent | 78% | 78% | 12% |
| Trading Agent | 65% | — | 25% |
| Health Monitor | 40% | — | 50% |

The self-reported scores were inflated by hardcoded-True acceptance cases. The "Honest Score" column removes those inflated scores.

---

## Sequencing Principle

**Do not build new features until the floor is fixed.**

Sprint 0 (week 1) eliminates the two conditions that make everything else unreliable:
1. Unbounded storage growth that will fill the disk
2. Acceptance framework that reports inflated readiness

After Sprint 0, progress is measurable. Every subsequent sprint has a verifiable before/after readiness delta.

---

## Sprint 0 — Stop the Bleeding (Week 1)

These are not improvements. They are emergency fixes for known active failures.

### S0.1 — Backup retention limit (VF-1) — 30 minutes
**File:** `core/persistent_json.py:28–34`  
**Change:** After `shutil.copy2(...)`, add:
```python
existing = sorted(backup_dir.glob(f"{path.stem}_*.json"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
for old in existing[5:]:
    old.unlink(missing_ok=True)
```
**One-time cleanup:** Delete all but 5 most recent backup files per stem.  
**Verification:** `ls data/backups/ | wc -l` drops from 2,522 to < 110.

### S0.2 — JSONL log rotation (VF-2) — 4 hours
**Files:** `services/observability.py:350–358`, `brain/router.py:447`  
**Change:** Replace `open("a")` with a rotating file handler. Create `core/rotating_jsonl.py`:
```python
from logging.handlers import RotatingFileHandler

class RotatingJSONLWriter:
    def __init__(self, path, max_bytes=10_000_000, backup_count=3): ...
    def write(self, record: dict) -> None: ...
```
Apply to: `observability_events.jsonl` (10 MB × 3), `command_history.jsonl` (5 MB × 5), `command_audit.jsonl` (5 MB × 3), `runtime_traces.jsonl` (5 MB × 3).  
**Verification:** Run `du -sh data/*.jsonl` after 1 week — all files stay under 10 MB.

### S0.3 — Memory vacuum (VF-3) — 2 hours
**File:** `memory/store.py`  
**Change:** Add `vacuum()` method. Call in `PersonalMemoryStore.__init__()` if file is older than 1 hour.
```python
def vacuum(self) -> int:
    data = self._load()
    now = datetime.now(timezone.utc)
    before = len(data["entries"])
    data["entries"] = [
        row for row in data["entries"]
        if not row.get("hidden") and not _is_expired(row, now)
    ]
    self._save(data)
    return before - len(data["entries"])
```
**Verification:** `remember(..., ttl_seconds=1); time.sleep(2); vacuum()` → count decreases by 1.

### S0.4 — Microphone spin fix (VF-4) — 15 minutes
**File:** `voice/voice_loop.py:194–203`  
**Change:** Add backoff variable and sleep:
```python
_mic_error_count = 0
...
except MicrophoneError as exc:
    app.console.print(f"[red]Microphone error:[/] {exc}")
    notify_overlay_error(str(exc))
    finish_and_log()
    delay = min(2.0 ** _mic_error_count, 30.0)
    time.sleep(delay)
    _mic_error_count += 1
    continue
# reset on successful record:
_mic_error_count = 0
```
**Verification:** Unplug USB mic; verify CPU does not spike; verify loop retries at 1s, 2s, 4s intervals.

**Sprint 0 total: ~1 day. Eliminates the three verified P0 bugs. No behavior changes for working features.**

---

## Sprint 1 — Fix the Scoreboard (Week 2)

Until acceptance tests are truthful, there is no way to measure progress.

### S1.1 — Remove all hardcoded-True acceptance cases (T-1 through T-9) — 4 hours
**Files:** `reliability/voice_health.py:70–99`, `reliability/memory_health.py:91–115`

Replace every `lambda: (True, ...)` and every tautological check with real behavioral tests. Specific changes are documented in `runtime_truthfulness_audit.md` items T-1 through T-9.

After this change, the voice acceptance score will drop from the inflated figure to an honest number. This is the expected outcome.

### S1.2 — Fix integration acceptance logic (T-10) — 4 hours
**File:** `reliability/integrations_health.py:42–58`  
**Change:** Cases return `None` (SKIP) when no credentials, not PASS.  
**Update:** `hardening_core.py:run_case()` must handle `None` result as SKIP.

### S1.3 — Remove `+10` score bonus (T-13) — 10 minutes
**File:** `reliability/hardening_core.py:43`  
**Change:** `self.current_pct = round(rate, 1)` — remove the `+ (10 if rate >= 90 else 0)`.

### S1.4 — Remove invented fallback scores (T-12) — 10 minutes
**File:** `reliability/product_readiness.py:17–28`  
**Change:** If `run_acceptance=False`, return `TrackScore(track, 0.0, target)` — not an invented number.

### S1.5 — Consolidate acceptance frameworks (C-6) — 1 day
**Files:** All `reliability/*.py` files → migrate to `validation/framework.py`  
**Delete:** `reliability/hardening_core.py`

**Sprint 1 outcome:** Readiness scores are now measured, not invented. Expect scores to decrease. This is correct. A measured 40% is worth more than an invented 65%.**

---

## Sprint 2 — Reliability Baseline (Weeks 3–4)

### S2.1 — Memory store per-entry size limit — 30 minutes
**File:** `memory/store.py:100`  
```python
if len(safe_text.encode()) > 10_240:
    safe_text = safe_text.encode()[:10_240].decode(errors='ignore')
```

### S2.2 — Default TTL for ephemeral categories — 30 minutes
**File:** `memory/store.py:93–96`  
```python
if ttl_seconds is None and cat in {"session", "short_term", "temporary_fact"}:
    ttl_seconds = 86400  # 24 hours default
```

### S2.3 — Formalise Thread Registry — 2 days
**New file:** `core/thread_registry.py`  
Register: voice loop thread, TTS thread, wake loop thread, overlay Qt thread, runtime monitor thread.  
`services/watchdog.py` calls `ThreadRegistry.heartbeat_check()` every 30s.  
On dead thread: log `CRITICAL`; push overlay notification.

### S2.4 — Startup validation: assert all intents have handlers — 4 hours
**File:** `core/app.py` or new `core/startup_validation.py`  
```python
def validate_intent_coverage(registry: ActionRegistry) -> list[str]:
    missing = [i for i in IMPLEMENTED_INTENTS if not registry.has(i)]
    if missing:
        logger.critical("Missing handlers for: %s", missing)
    return missing
```
Fail startup (not silently continue) if any P0 intent has no handler.

### S2.5 — Config startup validation — 3 hours
**New file:** `core/config_validator.py`  
Check required keys exist; print all errors at once; exit if any missing.

### S2.6 — Overlay retry cap — 2 hours
**File:** `ui/overlay_app.py`  
Cap restarts at 3; after 3 failures, disable overlay and continue headless.

### S2.7 — Screenshot accumulation cleanup — 1 hour
**File:** `actions/vision_actions.py` (take_screenshot intent)  
After saving, delete all but the 10 most recent files in `data/desktop_screenshots/`.

**Sprint 2 expected outcome:** System does not silently swallow failures. Thread deaths are detected. Config errors produce useful messages. Readiness scores improve in: Recovery (45%→70%), Runtime (60%→72%).

---

## Sprint 3 — Agent Architecture (Weeks 5–6)

### S3.1 — Formalise 12-agent registry — 2 days
**New file:** `agents/registry.py`  
Register all 12 agents with `health_check`, `intent_prefixes`, `depends_on`.  
Run `validate_registry()` at startup.

### S3.2 — Extract Browser Agent from Operator Agent — 1 day
**New file:** `agents/browser_agent.py`  
**Modify:** `agents/operator_agent.py` → keep as compatibility shim.  
**Modify:** `agents/intent_routing.py` → route browser intents to `AgentId.BROWSER`.

### S3.3 — Extract Desktop Agent from Operator Agent — 1 day
**New file:** `agents/desktop_agent.py`  
Same pattern.

### S3.4 — Formalise Trading Agent — 1 day
**New file:** `agents/trading_agent.py`  
Move trading intents from `AgentId.RESEARCH` to `AgentId.TRADING` in routing table.

### S3.5 — Formalise Health Monitor Agent — 1 day
**New file:** `agents/health_monitor_agent.py`  
Wraps `services/health.py`, adds storage checks from VF-1/VF-2/VF-3.  
30s heartbeat thread registered in ThreadRegistry.

### S3.6 — Win32 startup validation — 1 hour
**File:** `core/startup_validation.py`  
Check `win32gui` importable; check Tesseract in PATH; check Playwright importable.  
Report each as `available=True/False` in startup health display.

**Sprint 3 outcome:** Clean 12-agent architecture. Each domain has a clear owner. Health Monitor runs continuously. Readiness: Agent Architecture (55%→80%), Desktop (60%→72%), Health Monitor (40%→70%).

---

## Sprint 4 — Memory and Code Consolidation (Weeks 7–8)

### S4.1 — Route session memory through PersonalMemoryStore — 2 days
**File:** `memory/session_memory.py`  
Write through `PersonalMemoryStore.remember(category="session")`.  
On startup: migrate existing `data/session_memory.json` entries; then delete the file.

### S4.2 — Consolidate acceptance framework (if not done in S1.5) — 1 day

### S4.3 — Rename phase action files — 2 days
Use rename map from `consolidation_plan.md:C-7`.  
After rename, run startup validation to confirm all intents still registered.

### S4.4 — Consolidate pyttsx3 into one file — 4 hours
See `consolidation_plan.md:C-2`.

### S4.5 — Consolidate TTS state into one module — 2 days
See `consolidation_plan.md:C-3`.

### S4.6 — Semantic search fall back to keyword on failure — 1 hour
**File:** `memory/store.py:239`  
```python
except Exception:
    logger.warning("Semantic search unavailable; falling back to keyword search")
    return self.search_memory(query)[:limit]
```

### S4.7 — Sort memory results by importance × confidence — 30 minutes
**File:** `memory/store.py:list_visible()`  
After building `out`, add: `out.sort(key=lambda e: e.importance * e.confidence, reverse=True)`

**Sprint 4 outcome:** Codebase is significantly simpler. Memory is more useful (ranked results, semantic fallback). Readiness: Memory (45%→72%), Voice TTS (72%→82%), Codebase maintainability significantly improved.

---

## Sprint 5 — Voice Hardening and Barge-In (Weeks 9–10)

### S5.1 — Adaptive silence threshold — 2 days
**File:** `voice/microphone.py`  
On startup, measure 2s of ambient audio; set `STT_SILENCE_THRESHOLD = ambient_rms * 1.5`.  
Expose ambient level in `show_audio_status` output.

### S5.2 — Barge-in in push-to-talk mode — 2 days
**File:** `voice/voice_loop.py`  
During TTS playback, start microphone capture in background.  
If RMS exceeds threshold while TTS is playing, call `barge_in_cancel()` and route audio to STT.  
This requires coordination between TTS thread and mic thread via a shared `stop_tts` event.

### S5.3 — Multi-turn context buffer — 1 day
**File:** `core/app.py` or `brain/router.py`  
Maintain `_last_result: CommandResult | None` in-process (not persisted).  
When STT produces "explain the third one" and `_last_result` contains a numbered list, pass `_last_result.data` as context to the classifier.

### S5.4 — Suppress greeting on repeated wake in one session — 30 minutes
**File:** `voice/wake_greeting.py`  
Track last greeting time. If `time.monotonic() - last_greeting < 300`, skip greeting.

### S5.5 — Microphone overflow tracking — 2 hours
**File:** `voice/microphone.py:119–123`  
Track `overflow_count` in `CaptureStats`. Log warning in `transcribe_audio_detailed()` if `overflow_count > 0`.

**Sprint 5 outcome:** Voice interaction feels natural. Interruption works. Repeated wakes don't play greeting every time. Readiness: Voice overall (55%→78%), Microphone recovery (30%→80%), Barge-in (40%→75%).

---

## Sprint 6 — Integration Completion (Weeks 11–14)

These are the only sprints that add genuinely new functionality. All previous sprints fixed or hardened existing systems.

### S6.1 — Gmail read-only integration — 4 days
**New file:** `providers/gmail_provider.py`  
OAuth scope: `gmail.readonly`.  
Token stored in `data/oauth_tokens/gmail.json`.  
Update `providers/daily_summary_provider.py` to use real provider when token present.  
Update `reliability/integrations_health.py` acceptance: PASS when live, SKIP when no token.

### S6.2 — Google Calendar read-only integration — 3 days
**New file:** `providers/gcal_provider.py`  
OAuth scope: `calendar.readonly`.  
Same pattern.

### S6.3 — Telegram notifications — 1 day
**File:** `integrations/telegram_client.py` (currently 2-line stub)  
Implement one-way push notification via Bot API.  
Wire into Health Monitor Agent for `critical` alerts.  
Gate on `TELEGRAM_BOT_TOKEN` config; skip gracefully if not set.

### S6.4 — Playwright browser integration — 3 days
**File:** `browser/runtime.py`  
When Playwright is installed, set `provider="playwright"`.  
Implement `open_url()`, `get_page_text()`, `get_dom_excerpt()` against real pages.  
Keep mock as explicit fallback (not silent default).

**Sprint 6 outcome:** All three integration stubs (email, calendar, Telegram) have real implementations. Browser works against real pages. Readiness: Integrations (12%→80%), Browser (35%→82%).

---

## Projected Readiness After Each Sprint

| Subsystem | Base | Sprint 0 | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 | Sprint 5 | Sprint 6 |
|-----------|------|---------|---------|---------|---------|---------|---------|---------|
| Voice (TTS) | 72% | 72% | 72% | 75% | 78% | 83% | 88% | **90%** |
| STT | 65% | 65% | 67% | 70% | 72% | 75% | 82% | **88%** |
| Wake Word | 70% | 70% | 73% | 76% | 79% | 80% | 87% | **90%** |
| Mic Recovery | 30% | 75% | 75% | 80% | 82% | 82% | **90%** | 90% |
| Browser | 35% | 35% | 35% | 38% | 42% | 45% | 50% | **82%** |
| Desktop | 60% | 60% | 62% | 68% | 75% | 78% | 80% | **85%** |
| Memory | 45% | 52% | 55% | 62% | 65% | 75% | 78% | **82%** |
| Agent Arch | 55% | 55% | 58% | 62% | 83% | 87% | 88% | **90%** |
| Validation | 30% | 30% | 80% | 83% | 85% | 88% | 90% | **92%** |
| Recovery | 45% | 62% | 65% | 78% | 82% | 85% | 88% | **90%** |
| Integrations | 12% | 12% | 15% | 18% | 20% | 22% | 25% | **80%** |
| UI/Overlay | 70% | 70% | 72% | 78% | 80% | 82% | 85% | **90%** |
| Coding Agent | 78% | 80% | 82% | 85% | 87% | 88% | 90% | **92%** |
| Task Agent | 78% | 80% | 82% | 85% | 87% | 88% | 90% | **92%** |
| Trading Agent | 65% | 65% | 68% | 72% | 78% | 80% | 82% | **88%** |
| Health Monitor | 40% | 45% | 50% | 65% | 78% | 82% | 85% | **90%** |

---

## Effort and Risk Summary

| Sprint | Weeks | Effort (dev-days) | Risk | What changes |
|--------|-------|------------------|------|-------------|
| Sprint 0 | 1 | 1 | Very Low | Stop storage growth; fix mic spin; add memory vacuum |
| Sprint 1 | 2 | 2 | Low | Acceptance tests tell the truth; scores drop temporarily |
| Sprint 2 | 3–4 | 6 | Medium | Thread registry; config validation; startup validation |
| Sprint 3 | 5–6 | 8 | Medium | 12-agent architecture; formal health monitor |
| Sprint 4 | 7–8 | 9 | Medium | Memory consolidation; phase file rename; TTS consolidation |
| Sprint 5 | 9–10 | 8 | Medium | Voice hardening; barge-in; multi-turn context |
| Sprint 6 | 11–14 | 11 | High | Real integrations; Playwright browser |
| **Total** | **14 weeks** | **45 dev-days** | | |

---

## What Is Not On This Roadmap

- **New features.** No new intent types, no new capabilities.
- **LLM autonomy.** No self-improving agent loops.
- **New UI.** The overlay is adequate. No new visual components.
- **Remote agents.** Everything stays in-process.
- **Voice cloning.** Not needed for production readiness.
- **Parallel STT engines.** Complexity without proportionate gain.

The roadmap targets 90% on every existing subsystem, not 100% on some and 0% on others.

---

## Definition of Done (90%)

A subsystem reaches 90% when:

1. **No P0 or P1 bugs** are open against it
2. **Acceptance tests are real** — no hardcoded True, no tautologies
3. **Failures surface to the user** — overlay notification, console print, or structured error
4. **Recovery is tested** — at least one failure injection test passes
5. **Resource usage is bounded** — no unbounded file growth, no CPU spin on error
6. **Dependencies are validated at startup** — missing library produces clear error, not runtime crash

---

*End of Roadmap — 2026-05-29*
