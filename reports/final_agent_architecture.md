# J.A.R.V.I.S Final Agent Architecture

**Date:** 2026-05-29  
**Status:** Design — not yet implemented  
**Author:** Lead Architect  
**Grounded in:** Verified codebase audit (`audit_verification.md`)

---

## Architectural Premise

The current codebase already has a partial agent layer (`agents/`) described in its own header as a **"Phase 70 facade"** — it wraps `ActionRegistry` without replacing it. This design is correct. The final architecture formalises and extends it.

**Core invariant:** Agents do not execute commands directly. Every intent, regardless of which agent owns it, travels through:

```
User input
  → CommandRouter.route()
  → core/security.py (ALLOWED_INTENTS allowlist)
  → core/confirmation.py (gated actions)
  → ActionRegistry.execute()
  → Agent-owned handler
```

Agents are ownership boundaries, not execution bypasses.

---

## Agent Inventory

| # | Agent | Current State | Change |
|---|-------|--------------|--------|
| 1 | Commander Agent | `agents/executive_agent.py` (ExistSs) | Rename + harden |
| 2 | Voice Agent | `agents/conversation_agent.py` (Exists) | Rename + fix mic loop |
| 3 | Browser Agent | Part of `agents/operator_agent.py` | Extract from Operator |
| 4 | Desktop Agent | Part of `agents/operator_agent.py` | Extract from Operator |
| 5 | Memory Agent | `agents/memory_agent.py` (Exists) | Add vacuum + SQLite |
| 6 | Planning Agent | `agents/planning_agent.py` (Exists) | Keep |
| 7 | Coding Agent | `agents/coding_agent.py` (Exists) | Keep |
| 8 | Research Agent | `agents/research_agent.py` (Exists) | Keep |
| 9 | Calendar Agent | Mock in `providers/daily_summary_provider.py` | Build real adapter |
| 10 | Email Agent | Mock in `providers/daily_summary_provider.py` | Build real adapter |
| 11 | Trading Agent | Scattered across `investigation/`, `actions/` | Extract + formalise |
| 12 | Health Monitor Agent | `services/health.py` + `reliability/` | Formalise + centralise |

---

## 1. Commander Agent

**Current module:** `agents/executive_agent.py`

### Responsibilities
- Single entry point for all classified requests
- Selects the owning agent for every intent via `agent_for_intent()`
- Delegates to `ActionRegistry.execute()` — does not execute directly
- Handles meta-intents: `UNKNOWN`, `CLARIFY`, `SHOW_CAPABILITIES`, `SHOW_JARVIS_STATUS`
- Manages confirmation state across agents
- Aggregates multi-agent results for compound commands

### Tools
- `brain/router.py` — full pipeline including security and confirmation
- `brain/intent_classifier.py` — classification
- `agents/intent_routing.py` — agent selection table
- `core/confirmation.py` — gate for destructive intents

### Inputs
- Raw text string (from Voice Agent or console)
- `input_mode`: `"voice"` | `"wakeword"` | `"console"` | `"tray"`
- Optional `transcribed_text` for latency tracking

### Outputs
- `CommandResult(status, summary, data, error, requires_confirmation)`
- Agent attribution metadata (which agent handled the request)

### Permissions
- Read: all agent states, intent registry, session memory
- Write: command history JSONL, audit JSONL, session state
- Cannot: write to memory store directly (must delegate to Memory Agent), execute OS commands

### Communication Protocol
- **Synchronous:** Direct call via `ActionRegistry.execute()` for standard intents
- **Asynchronous:** `BackgroundTaskEngine.submit()` for HEAVY_INTENTS (defined in `runtime/background_tasks.py:34`)
- Returns immediately with task ID for async; result available via `SHOW_RUNNING_TASKS`

### Failure Handling
- Security validation failure → `result_blocked()` with reason
- Classification failure (UNKNOWN) → `result_blocked()` with rephrasing prompt
- Handler exception → `result_failed()` with error logged; never propagates exception to caller
- Confirmation timeout (120s) → auto-cancel, notify user

### Health Check
```
commander_healthy = (
    ActionRegistry loaded (all imports succeeded at startup) AND
    intent_classifier importable AND
    security module returns correct BLOCKED for unknown intents
)
```

---

## 2. Voice Agent

**Current module:** `agents/conversation_agent.py`

### Responsibilities
- Owns the entire audio I/O path: microphone capture, STT, TTS, wake word
- Does NOT classify or execute commands — hands transcript to Commander Agent
- Manages engine selection, fallback, and latency measurement
- Owns audio device state and routing

### Tools
- `voice/microphone.py` — capture
- `voice/transcriber.py` — STT pipeline coordinator
- `voice/stt_engines/` — 5 engines (faster-whisper primary)
- `voice/stt_stack/` — 9-component post-processing pipeline
- `voice/tts.py` — TTS orchestrator
- `voice/engines/registry.py` — TTS engine selection (canonical entry point)
- `voice/wakeword.py` + `voice/wakeword_loop.py` — wake detection
- `voice/latency_tracker.py` — end-to-end timing

### Inputs
- Audio stream (from microphone or mock injector)
- TTS text strings (from Commander Agent result summaries)
- Config flags: `TTS_ENABLED`, `VOICE_ENABLED`, `WAKE_WORD_ENABLED`, `TTS_ENGINE`

### Outputs
- Transcribed text → Commander Agent
- Spoken audio → speakers (via TTS engine)
- Latency metrics → Health Monitor Agent
- STT result metadata: `low_confidence`, `language`, `backends_used`

### Permissions
- Read: audio devices, config
- Write: `data/voice_calibration.json`, `data/voice_stack.json`, `data/stt_stack.json`
- Cannot: write to memory store, execute intents, access filesystem beyond voice data files

### Communication Protocol
- **Inbound:** Voice Agent receives TTS text via `TTSService.speak(text)` — synchronous call from Commander
- **Outbound:** Transcribed text delivered via `process_voice_transcript(app, text)` → Commander
- **Heartbeat:** Publishes liveness signal to Health Monitor every 30s

### Failure Handling

| Failure | Detection | Recovery |
|---------|-----------|---------|
| Microphone disconnect | `MicrophoneError` in `record_until_enter()` | **Current bug (VF-4):** loop retries with no sleep. Fix: add `time.sleep(2.0)` with exponential backoff to 30s max |
| STT engine crash | `TranscriptionError` | Fall back to next engine in `stt_engines/registry.py`; log fallback |
| TTS engine failure | `TTSError` from both engines | Show overlay error + console print (already implemented in `tts.py:673`) |
| Wake word model missing | `WakeWordDetector.start()` returns False | Log warning; continue in push-to-talk only mode |
| Streaming STT timeout | `StreamingSttFallbackError` | `disable_streaming_for_session()` then retry with legacy capture |

### Health Check
```
voice_healthy = (
    sounddevice.query_devices() succeeds AND
    at least one STT engine importable AND
    at least one TTS engine importable AND
    microphone loop thread alive (ThreadRegistry check)
)
```

---

## 3. Browser Agent

**Current module:** Part of `agents/operator_agent.py` — extract to `agents/browser_agent.py`

### Responsibilities
- All browser I/O: open URLs, read DOM, summarise pages, search web
- Validates URLs before any browser action (https-only; allowlist enforcement)
- Maintains browser session state
- Replay logging for audit trail

### Tools
- `browser/runtime.py` — session management, URL validation
- `browser/dom_read.py` — DOM extraction
- `browser/task_planner.py` — multi-step browser task planning
- `browser/url_parser.py` — URL normalisation and validation
- `browser/memory.py` — visited page cache

### Inputs
- URL string (validated by `browser/url_parser.py`)
- Search query string
- DOM extraction request

### Outputs
- Page summary text
- DOM excerpt (truncated, no scripts)
- Screenshot path (if headed mode active)
- `BrowserRuntimeState` — provider, session_active, last_action_success

### Permissions
- Read: HTTPS URLs only; no `file://`, no `localhost` except the configured trading dashboard
- Write: `data/browser_action_replay.jsonl`, `data/browser_screenshots/`, `data/browser_memory.json`
- Cannot: fill forms, submit, click links, execute JavaScript, navigate to non-allowlisted localhost ports

### Communication Protocol
- Synchronous for read operations (<5s expected)
- Async (via BackgroundTaskEngine) for multi-step research tasks
- Results returned as structured text; no raw HTML in CommandResult

### Failure Handling
- Playwright not installed → `provider="mock"`, report `_MOCK_BANNER` in output, do not pretend success
- Browser process dies → `browser_process_alive=False` in state; next request restarts session
- URL validation fails → `result_blocked()` with the rejected URL and reason
- DOM extraction timeout (30s) → return partial excerpt with `[TRUNCATED]` marker

### Health Check
```
browser_healthy = (
    browser/runtime.py importable AND
    (playwright installed OR provider explicitly set to "mock") AND
    replay JSONL writable
)
```

---

## 4. Desktop Agent

**Current module:** Part of `agents/operator_agent.py` — extract to `agents/desktop_agent.py`

### Responsibilities
- Window management: focus, minimise, maximise, list
- Screen capture and OCR
- Application launching (Start Menu .lnk only, allowlisted)
- Clipboard read/write (all confirmation-gated)
- Desktop automation (type, click — confirmation-gated)

### Tools
- `desktop/control_runtime.py` — window control
- `desktop/vision_runtime.py` — screen capture + OCR
- `vision/ocr.py` — Tesseract OCR
- `vision/screen_capture.py` — screenshot
- `vision/active_window.py` — foreground window detection
- `computer_control/` — clipboard, keyboard
- `apps/` — app discovery and launcher (allowlisted .lnk only)

### Inputs
- Window title or process name
- Screenshot request
- App name (validated against discovered Start Menu shortcuts)
- Clipboard text

### Outputs
- Window handle or error
- Screenshot path + OCR text
- Active window info
- Clipboard state

### Permissions
- Read: screen, window titles, clipboard
- Write: clipboard (confirmation required), focus state
- Execute: open `.lnk` shortcuts only (user must approve; .lnk target shown to user before approval)
- Cannot: run arbitrary executables, access `System32`, compose PowerShell strings, access files outside allowed paths

### Communication Protocol
- Synchronous for all operations
- Confirmation gate enforced by Commander Agent before Desktop Agent receives clipboard/click/type intents

### Failure Handling
- Tesseract not installed → OCR returns empty string with `"ocr_unavailable"` flag; does not block screenshot
- Window not found → `result_failed()` with window title; no retry
- App .lnk resolution fails → `result_blocked()` with path shown
- `pywin32` not available → desktop control degraded; log warning on startup

### Health Check
```
desktop_healthy = (
    win32gui importable AND
    (tesseract available OR OCR_ENABLED=false) AND
    apps discovery found at least one .lnk
)
```

---

## 5. Memory Agent

**Current module:** `agents/memory_agent.py`

### Responsibilities
- Single authoritative store for all facts, preferences, aliases, session context
- Enforces TTL expiry and vacuum
- Provides keyword search and semantic search
- Redacts secrets before storage
- Enforces per-entry size limit
- Project file indexing (read-only)

### Tools
- `memory/store.py` — `PersonalMemoryStore` (canonical store)
- `memory/search.py` — keyword search
- `memory/semantic_runtime.py` — embedding-based search
- `memory/graph.py` — entity relationships
- `memory/repair.py` — schema repair
- `memory/project_indexer.py` — codebase index
- `brain/aliases.py` — alias resolution
- `brain/preferences.py` — preference CRUD

### Inputs
- `remember(text, category, tags, ttl_seconds, sensitive)` — store a fact
- `forget(query)` — soft-delete matching entries
- `search(query, limit)` — keyword search
- `semantic_search(query, limit)` — embedding search
- `vacuum()` — remove expired and hidden entries from disk

### Outputs
- `MemoryEntry` objects
- Search result lists
- Vacuum count (entries removed)

### Permissions
- Read: all categories in personal store, project index
- Write: personal store only, via `PersonalMemoryStore.remember()`
- Cannot: write to session state directly, access other agents' data files, write to project source code

### Memory Access Rules (see also §Memory Access Rules section)
- **Read access:** All agents may call `MemoryAgent.search()` and `MemoryAgent.semantic_search()`
- **Write access:** All agents may call `MemoryAgent.remember()` — routed through MemoryAgent, not direct file writes
- **Delete access:** User-initiated only (`forget` intent) or TTL expiry via `vacuum()`
- **Sensitive entries:** Never returned to TTS output; masked in overlay display

### Failure Handling
- JSON file corrupt → `memory/repair.py` restores from `data/backups/memory_store_*.json` (most recent 5)
- Semantic search model unavailable → fall back to keyword search; log warning; do not return empty results silently
- `vacuum()` fails → log error; do not block startup

### Health Check
```
memory_healthy = (
    memory_store.json readable AND
    PersonalMemoryStore._load() returns dict with "entries" key AND
    expired entries count == 0 (after vacuum at startup)
)
```

---

## 6. Planning Agent

**Current module:** `agents/planning_agent.py`

### Responsibilities
- Multi-step task lifecycle: plan → approve → execute → report
- Background task queue management
- Workspace activation (trading, study, dev)
- Workflow execution (predefined sequences)
- Experiment planning

### Tools
- `task_agent/planner.py` — objective decomposition
- `task_agent/executor.py` — step execution with per-step approval
- `task_agent/safety.py` — READONLY / CONFIRM_REQUIRED / BLOCKED step classification
- `runtime/background_tasks.py` — async task engine (ThreadPoolExecutor)
- `runtime/task_lifecycle.py` — task state machine
- `workflows/` — predefined workflow definitions
- `workspaces/` — workspace configurations

### Inputs
- Objective string (e.g., "audit the trading algorithm")
- Step approval: `yes` / `no`
- Task control: start, stop, cancel, show status

### Outputs
- `TaskPlan` — list of typed steps with safety classification
- `TaskStep` results — per-step findings, patch proposals
- Task status summaries

### Permissions
- READONLY steps: execute without approval
- CONFIRM_REQUIRED steps: require explicit user `yes` before execution
- BLOCKED steps (`delete_file`, `move_money`, `live_execution`, `arbitrary_shell`): permanently rejected, never prompted
- Max steps: `TASK_AGENT_MAX_STEPS` (default 12)
- Max runtime: `TASK_AGENT_MAX_RUNTIME_SECONDS` (default 300)

### Communication Protocol
- Planning Agent delegates READONLY step execution to CodingAgent or ResearchAgent as appropriate
- CONFIRM_REQUIRED steps go back through Commander Agent confirmation gate
- Async tasks report progress via `runtime/result_stream.py`

### Failure Handling
- Step timeout → mark step FAILED; present findings so far; ask user to continue or abort
- Patch apply failure → auto-rollback via `task_agent/patch_apply.py`; report rollback result
- Task cancelled → release any held locks; persist partial findings

### Health Check
```
planning_healthy = (
    task_agent/safety.py importable AND
    TASK_AGENT_MAX_STEPS > 0 AND
    no task in RUNNING state older than TASK_AGENT_MAX_RUNTIME_SECONDS
)
```

---

## 7. Coding Agent

**Current module:** `agents/coding_agent.py`

### Responsibilities
- Code search: function, class, config key, text pattern
- Error explanation from logs
- Failing test discovery
- Patch proposal and review (supervised)
- Patch application (user-approved, with rollback)

### Tools
- `actions/code_search.py` — grep, AST search
- `task_agent/` — supervised patch lifecycle
- `investigation/patch_simulation.py` — diff preview
- `investigation/patch_apply.py` — apply with backup
- `actions/productivity_actions.py` — summarise file, recent changes
- `phase45_investigation.py` — trading algorithm debugging

### Inputs
- Search query (function name, class name, pattern)
- Error text for explanation
- Patch diff (for apply/rollback)
- `CommandRequest` routed from Commander

### Outputs
- Code search results (file:line:snippet)
- Error explanation text
- Unified diff preview
- Apply result (success / rollback reason)

### Permissions
- Read: all `.py` files in `PROJECT_ROOT`
- Write: only via approved patch workflow; target path must pass `task_agent/safety.py:path_write_allowed()`
- Cannot: delete files, modify `.env`, access secrets, execute arbitrary shell

### Failure Handling
- File not found → `result_failed()` with the missing path
- Patch apply error → immediate rollback; report rollback outcome
- `compileall` fails after patch → treat as apply failure, rollback

### Health Check
```
coding_healthy = (
    PROJECT_ROOT accessible AND
    task_agent/safety.py importable AND
    no apply in progress with no corresponding approval
)
```

---

## 8. Research Agent

**Current module:** `agents/research_agent.py`

### Responsibilities
- Trading algorithm investigation (read-only analysis)
- Investigation graph: hypothesis tracking, root cause analysis, verification plans
- Replay analysis: signal lifecycle, backtest comparison
- Blocker trend analysis
- Autonomous nightly investigation scheduling

### Tools
- `investigation/` — full investigation module suite
- `assistant/hypothesis_engine.py` — hypothesis CRUD
- `assistant/root_cause_engine.py` — root cause ranking
- `assistant/intelligence_timeline.py` — timeline of events
- `assistant/investigation_scheduler.py` — nightly scheduling

### Inputs
- Investigation objective
- Symbol, date range for replay
- Hypothesis text for verification

### Outputs
- Investigation findings with severity, evidence, confidence
- Replay timeline and diff
- Hypothesis ranking with confidence scores

### Permissions
- Read: trading logs, live/backtest reports, project source code, data files
- Write: investigation JSON files in `data/` (hypotheses, root_causes, etc.)
- Cannot: execute live trades, modify source code, access production secrets

### Failure Handling
- Trading dashboard unreachable → report `dashboard_health_reachable()=False`; do not continue analysis that requires live data
- Log files missing → report missing paths; do not fabricate findings
- Nightly investigation timeout → write partial findings; set scheduler status to `timed_out`

### Health Check
```
research_healthy = (
    investigation/ importable AND
    data/hypotheses.json readable AND
    no investigation_scheduler in infinite loop state
)
```

---

## 9. Calendar Agent

**Current state:** Mock only. `providers/daily_summary_provider.py` returns hardcoded data with `"MOCK MODE"` marker.

### Responsibilities
- Read upcoming events from calendar (read-only)
- Detect scheduling conflicts
- Summarise today/week schedule
- Provide context to Commander Agent for time-sensitive responses

### Tools
- `providers/gcal_provider.py` — Google Calendar API (to be built; read-only OAuth scope `calendar.readonly`)
- `providers/daily_summary_provider.py` — adapter selection logic (real vs mock)

### Inputs
- Date range
- Calendar query (conflicts, next event, today's schedule)

### Outputs
- Event list with title, time, duration, attendees (no attendee email exposed in TTS)
- Conflict report

### Permissions
- Read: Google Calendar API (OAuth token stored in `data/oauth_tokens/calendar.json`)
- Cannot: create events, modify events, delete events, access attendee details beyond name
- Token scope: `https://www.googleapis.com/auth/calendar.readonly` only

### Communication Protocol
- Synchronous; 5s timeout per API call
- If credentials absent → return `status="not_configured"`, do not pretend success

### Failure Handling
- OAuth token expired → prompt user to re-authorise; do not cache stale token
- API rate limit → return last cached result with `cache_age` field; log rate limit
- No internet → return `status="offline"` with last cache timestamp

### Health Check
```
calendar_healthy = (
    (gcal_provider configured AND token valid) OR
    (provider="mock" AND explicitly configured as mock)
)
Note: "mock" is NOT healthy for production. Health check fails if mock in production mode.
```

---

## 10. Email Agent

**Current state:** Mock only. Same `providers/daily_summary_provider.py` as Calendar, with `"MOCK MODE"`.

### Responsibilities
- Read inbox summary (read-only)
- Surface urgent/flagged emails
- Search inbox by keyword or sender
- Provide email context for daily briefing

### Tools
- `providers/gmail_provider.py` — Gmail API (to be built; read-only OAuth scope `gmail.readonly`)
- `providers/daily_summary_provider.py` — adapter selection

### Inputs
- Count (last N emails)
- Search query (sender, subject keyword)
- Urgency filter

### Outputs
- Email list: sender, subject, date, urgency flag (no body text exposed in TTS beyond summary)
- Unread count

### Permissions
- Read: Gmail API (OAuth token stored in `data/oauth_tokens/gmail.json`)
- Cannot: send email, delete email, move email, read email body beyond 200-character preview
- Token scope: `https://www.googleapis.com/auth/gmail.readonly` only

### Failure Handling
- Same pattern as Calendar Agent: offline → cache; expired token → prompt; no credentials → `status="not_configured"`

### Health Check
```
email_healthy = (
    (gmail_provider configured AND token valid) OR
    (provider="mock" AND explicitly configured as mock)
)
```

---

## 11. Trading Agent

**Current state:** Scattered across `actions/trading_*.py`, `investigation/`, `actions/phase45_actions.py` through `phase60_actions.py`. No formal agent boundary.

### Responsibilities
- Trading loop lifecycle: start, stop, kill-switch
- Dashboard health monitoring
- Live report display and position queries
- Log search and error triage
- Kill-switch enforcement (hard gate — no undo without explicit re-enable)

### Tools
- `actions/trading_dashboard.py` — dashboard health and URL
- `actions/trading_loop.py` — loop start/stop (CONFIRM_REQUIRED)
- `actions/trading_logs.py` — log search, rejection reasons
- `actions/trading_reports.py` — live report, open positions
- `runtime/dashboard_health.py` — periodic health poll

### Inputs
- Loop control commands (start/stop/kill-switch) — all require confirmation
- Dashboard URL (from config, not user input)
- Log query string

### Outputs
- Dashboard health status (reachable / unreachable / response_time_ms)
- Active positions list
- Recent log entries
- Kill-switch state

### Permissions
- Read: trading dashboard API (localhost only, configured URL)
- Execute: `run_live_daily_loop`, `run_live_weekly_loop` — both CONFIRMATION_REQUIRED, logged to audit trail
- Kill-switch: single-intent `enable_kill_switch` requires confirmation; once enabled, only `disable_kill_switch` (also confirmed) reverses it
- Cannot: access brokerage API directly, modify trading algorithm source code, send orders

### Failure Handling
- Dashboard unreachable → `show_dashboard_health()` returns `reachable=False`; all loop actions blocked until reachable
- Loop start rejected (kill-switch active) → `result_blocked()` with kill-switch state explanation
- Log file missing → report missing path; return empty results

### Health Check
```
trading_healthy = (
    trading dashboard URL configured AND
    dashboard reachable (HTTP 200 within 5s) AND
    kill_switch_state readable from data/settings.json
)
```

---

## 12. Health Monitor Agent

**Current state:** `services/health.py` (read-only checks), `reliability/` (acceptance scores), `services/watchdog.py`. No formal agent.

### Responsibilities
- Periodic liveness check of all 11 other agents
- Disk usage monitoring and alerting
- Storage growth detection (backup count, JSONL file sizes)
- Thread registry heartbeat (detect dead threads)
- Runtime monitor coordination
- Surface `critical` / `warning` / `ok` status for each agent

### Tools
- `services/health.py` — `HealthReport`, `HealthCheckItem`
- `services/watchdog.py` — process health
- `services/runtime_monitor.py` — timeout and recovery tracking
- `services/observability.py` — event logging (read mode)
- Direct file stat for storage checks

### Inputs
- 30-second heartbeat timer
- Manual trigger: `show_system_health` intent

### Outputs
- `HealthReport` per agent with `status: ok | warning | critical`
- `data/watchdog_status.json` — persisted last-known health
- Overlay notification on any agent entering `critical` state
- Console alert for storage threshold breaches

### Permissions
- Read: all data files (size checks only), all agent state files, thread registry
- Write: `data/watchdog_status.json` only
- Cannot: restart processes, modify config, execute intents on behalf of other agents

### Health Checks Performed

| Check | Warning threshold | Critical threshold |
|-------|------------------|--------------------|
| `data/backups/` file count | > 500 | > 2,000 |
| `observability_events.jsonl` size | > 5 MB | > 20 MB |
| `command_history.jsonl` size | > 2 MB | > 10 MB |
| Any agent thread dead | — | immediately |
| Dashboard unreachable | 2 consecutive | 5 consecutive |
| Memory store expired entries | > 100 | > 1,000 |
| Disk free space | < 2 GB | < 500 MB |

### Failure Handling
- Health Monitor itself crashes → `services/watchdog.py` detects and restarts (max 3 attempts)
- Agent check throws exception → that agent marked `warning: check_error`; does not block other checks
- Storage check I/O error → log warning; skip that check; do not fail overall health

---

## Agent Router

**Target module:** `agents/router.py` (new, replaces/formalises `agents/intent_routing.py`)

### Design

```python
class AgentRouter:
    """Maps intents to owning agents. Single source of truth."""

    _TABLE: dict[str, AgentId] = {
        # Commander
        "unknown": AgentId.COMMANDER,
        "clarify": AgentId.COMMANDER,
        "show_capabilities": AgentId.COMMANDER,
        "show_jarvis_status": AgentId.COMMANDER,

        # Voice
        "show_voice_*": AgentId.VOICE,
        "test_tts_*": AgentId.VOICE,
        "calibrate_voice": AgentId.VOICE,
        "show_stt_*": AgentId.VOICE,
        "cancel_active_speech": AgentId.VOICE,

        # Browser
        "open_browser": AgentId.BROWSER,
        "open_website": AgentId.BROWSER,
        "search_web*": AgentId.BROWSER,
        "summarize_this_page": AgentId.BROWSER,
        "what_tab_is_active": AgentId.BROWSER,

        # Desktop
        "open_app": AgentId.DESKTOP,
        "focus_window": AgentId.DESKTOP,
        "describe_screen": AgentId.DESKTOP,
        "take_screenshot": AgentId.DESKTOP,
        "type_this": AgentId.DESKTOP,
        "click_button*": AgentId.DESKTOP,

        # Memory
        "remember*": AgentId.MEMORY,
        "forget*": AgentId.MEMORY,
        "search_memory": AgentId.MEMORY,
        "set_preference": AgentId.MEMORY,
        "set_alias": AgentId.MEMORY,

        # Planning
        "start_task": AgentId.PLANNING,
        "run_task_step": AgentId.PLANNING,
        "run_workflow": AgentId.PLANNING,
        "queue_task": AgentId.PLANNING,

        # Coding
        "find_function": AgentId.CODING,
        "find_class": AgentId.CODING,
        "search_code*": AgentId.CODING,
        "apply_task_patch": AgentId.CODING,
        "explain_*_error": AgentId.CODING,

        # Research
        "investigate*": AgentId.RESEARCH,
        "compare_live*": AgentId.RESEARCH,
        "build_investigation*": AgentId.RESEARCH,

        # Calendar
        "summarize_my_calendar": AgentId.CALENDAR,
        "find_calendar_conflicts": AgentId.CALENDAR,

        # Email
        "summarize_my_inbox": AgentId.EMAIL,
        "show_urgent_emails": AgentId.EMAIL,
        "summarize_my_last*_emails": AgentId.EMAIL,

        # Trading
        "run_live_*_loop": AgentId.TRADING,
        "show_dashboard_health": AgentId.TRADING,
        "enable_kill_switch": AgentId.TRADING,
        "disable_kill_switch": AgentId.TRADING,
        "show_open_positions": AgentId.TRADING,

        # Health Monitor
        "show_system_health": AgentId.HEALTH_MONITOR,
        "run_jarvis_health_check": AgentId.HEALTH_MONITOR,
        "show_watchdog_status": AgentId.HEALTH_MONITOR,
    }

    def route(self, intent: str) -> AgentId:
        """Exact match first, then prefix match, then COMMANDER."""
        if intent in self._TABLE:
            return self._TABLE[intent]
        for pattern, agent_id in self._TABLE.items():
            if pattern.endswith("*") and intent.startswith(pattern[:-1]):
                return agent_id
        return AgentId.COMMANDER
```

**Rules:**
1. The routing table is the authoritative definition of agent ownership.
2. Any intent not in the table falls to Commander.
3. Agent routing is metadata only — execution still goes through `ActionRegistry`.
4. The table is loaded once at startup; no dynamic modification at runtime.

---

## Agent Registry

**Target module:** `agents/registry.py` (new)

```python
@dataclass
class AgentRegistration:
    agent_id: AgentId
    agent: object                        # agent instance
    health_check: Callable[[], bool]     # returns True if healthy
    intent_prefixes: tuple[str, ...]     # owned intent prefixes
    depends_on: tuple[AgentId, ...]      # agents this one requires
    max_concurrent_requests: int = 1     # concurrency limit
    timeout_seconds: float = 30.0        # per-request timeout

class AgentRegistry:
    _agents: dict[AgentId, AgentRegistration]

    def register(self, registration: AgentRegistration) -> None: ...
    def get(self, agent_id: AgentId) -> AgentRegistration: ...
    def all_healthy(self) -> dict[AgentId, bool]: ...
    def dependencies_healthy(self, agent_id: AgentId) -> bool: ...
```

**Startup validation (run before first request accepted):**
```python
def validate_registry(registry: AgentRegistry) -> list[str]:
    errors = []
    for agent_id, reg in registry._agents.items():
        try:
            healthy = reg.health_check()
            if not healthy:
                errors.append(f"{agent_id}: health_check() returned False")
        except Exception as exc:
            errors.append(f"{agent_id}: health_check() raised {exc}")
    return errors
```

Startup fails loudly (not silently) if any P0 agent health check fails. P0 agents: Commander, Voice, Memory.

---

## Agent Health System

**Target module:** `agents/health_system.py` (new; wraps existing `services/health.py`)

### Architecture

```
HealthMonitorAgent
  ├── AgentHealthPoller (runs every 30s on daemon thread)
  │     └── calls AgentRegistry.all_healthy()
  ├── StorageWatcher (runs every 5 min)
  │     └── checks file sizes, backup count, disk free
  ├── ThreadRegistryWatcher (runs every 30s)
  │     └── checks all registered threads are alive
  └── HealthReportWriter
        └── writes to data/watchdog_status.json
```

### Health States

```
ok       — all checks pass
warning  — at least one non-critical threshold exceeded
critical — P0 agent dead, disk < 500 MB, or unrecoverable error
```

### Alert Routing

```
critical → overlay error notification + console CRITICAL print
warning  → overlay warning notification (once per hour per issue)
ok       → no notification
```

### Recovery Actions

Health Monitor does NOT trigger recovery autonomously. It reports. Commander Agent or user triggers recovery.

Exception: **Storage auto-cleanup** — if `data/backups/` exceeds 2,000 files, Health Monitor runs `cleanup_old_backups(keep=5)` automatically and logs the action.

---

## Agent Memory Access Rules

```
╔══════════════════════════════════════════════════════════════╗
║                   Memory Access Matrix                       ║
╠══════════════╦═══════╦═══════╦════════════════╦═════════════╣
║ Agent        ║ Read  ║ Write ║ Delete         ║ Semantic    ║
╠══════════════╬═══════╬═══════╬════════════════╬═════════════╣
║ Commander    ║  YES  ║  YES  ║ user-initiated ║  YES        ║
║ Voice        ║  NO   ║  NO   ║ NO             ║  NO         ║
║ Browser      ║  YES  ║  YES  ║ NO             ║  NO         ║
║ Desktop      ║  YES  ║  NO   ║ NO             ║  NO         ║
║ Memory       ║  YES  ║  YES  ║ YES (TTL+user) ║  YES        ║
║ Planning     ║  YES  ║  YES  ║ NO             ║  NO         ║
║ Coding       ║  YES  ║  YES  ║ NO             ║  NO         ║
║ Research     ║  YES  ║  YES  ║ NO             ║  YES        ║
║ Calendar     ║  YES  ║  YES  ║ NO             ║  NO         ║
║ Email        ║  YES  ║  YES  ║ NO             ║  NO         ║
║ Trading      ║  YES  ║  NO   ║ NO             ║  NO         ║
║ Health Mon.  ║  YES  ║  NO   ║ NO             ║  NO         ║
╚══════════════╩═══════╩═══════╩════════════════╩═════════════╝
```

**Rules:**
1. All writes go through `MemoryAgent.remember()` — no agent writes `memory_store.json` directly.
2. Voice Agent has no memory access. Transcripts are not stored unless Commander routes a `remember` intent.
3. Trading Agent reads memory for context but never writes (trading state is in its own data files).
4. Health Monitor reads memory file size only (stat call) — never reads entry content.
5. Sensitive entries (`sensitive=True`) are never returned by search calls to any agent other than Memory Agent.
6. The Memory Agent runs `vacuum()` at startup and every 6 hours to enforce TTL and remove hidden entries.

---

## Inter-Agent Communication Rules

1. **No shared mutable state between agents.** Each agent has its own module-level singletons. Cross-agent communication uses function calls or message passing through Commander.

2. **Agent-to-agent calls are mediated.** Agent A does not import Agent B's internals. Agent A calls a method on Commander, which delegates to Agent B.

3. **Exception: Memory Agent.** All agents may call `MemoryAgent.remember()` and `MemoryAgent.search()` directly, as memory is a shared service. This is the only permitted direct cross-agent import.

4. **Async tasks.** An agent submits a background task via `BackgroundTaskEngine.submit()`. The engine is owned by Commander. Results are published to `runtime/result_stream.py`.

5. **TTS text.** Any agent may produce a `summary` string in its `CommandResult`. Commander passes this to Voice Agent's `TTSService.speak()`. No agent calls TTS directly.

---

## What Is Not In This Architecture

The following are explicitly out of scope:

- **LLM autonomy.** No agent self-generates code and runs it. No agent executes unreviewed plans.
- **Agent-to-agent spawning.** No agent creates new agents at runtime.
- **Shared filesystem.** Agents write to their own data files; no shared append-only log except the audit trail (written by Commander).
- **New capabilities.** This architecture reorganises existing code. It does not add new features.
- **Remote agents.** All agents run in-process on the local machine. No RPC, no REST, no message broker.

---

*End of Final Agent Architecture — 2026-05-29*
