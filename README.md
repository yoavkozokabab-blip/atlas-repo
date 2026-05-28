# local_jarvis

A safe, modular personal assistant for Windows. **Phase 13** adds optional **wake word** activation (listening only — never direct execution). Phase 12 computer control, tray, watchdog, and the secured pipeline are unchanged.

**Architecture map:** [README_ARCHITECTURE.md](README_ARCHITECTURE.md) — pipeline, folder layout, safety model, runtime modes.

## Safety model

- No autonomous agent; **LLM does not execute anything**.
- **LLM returns JSON only** (`intent`, `confidence`, `params`) — validated against `IMPLEMENTED_INTENTS`.
- Forbidden LLM keys (`shell`, `command`, `powershell`, …) → blocked / clarification.
- Low confidence or invalid LLM output → clarify or fall back to rules (if enabled).
- **Voice/STT only produces text** → classifier → router → security → registry.
- **TTS is output only** — never affects routing, security, or actions.
- If TTS fails, the command result is unchanged (warning only).
- TTS speaks **summary only** — not `data`, logs, env values, or secrets.
- Default: TTS **disabled** unless `TTS_ENABLED=true` or `--speak`.
- **Memory never stores secrets** — API keys, tokens, passwords blocked.
- **No auto-memory** — only explicit `remember` / `set alias` commands write data.

## Pipeline

```
[Text or Voice→STT] → [Confirm?] → [Alias?] → Classifier → Router → Security → [Confirm] → Registry → Action → Result → [optional TTS] → Log
```

Classifier order when `LLM_CLASSIFIER_ENABLED=true`:

1. High-confidence **rules** → use immediately (no LLM call)
2. Low-confidence → **Ollama** JSON classification
3. Validate allowlist + confidence + forbidden keys
4. On failure → **fallback** to rules or `clarification_needed`

## Requirements

- Windows 10/11
- Python 3.11+
- Microphone (for `--voice`)
- **faster-whisper** (STT), **pyttsx3** (TTS)

## Setup

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
pip install -r requirements.txt
copy .env.example .env
```

### STT (voice input)

| Variable | Default |
|----------|---------|
| `STT_ENGINE` | `faster_whisper` |
| `STT_MODEL` | `base` |
| `STT_LANGUAGE` | `en` (default); `he` only if set explicitly |

### TTS (optional output)

| Variable | Default |
|----------|---------|
| `TTS_ENABLED` | `false` |
| `TTS_ENGINE` | `pyttsx3` |
| `TTS_LANGUAGE` | `he` |
| `TTS_VOICE` | *(empty — auto-select)* |
| `TTS_RATE` | `185` |
| `TTS_VOLUME` | `1.0` |
| `TTS_MAX_CHARS` | `500` |

### LLM classifier (Phase 4, optional)

| Variable | Default |
|----------|---------|
| `LLM_CLASSIFIER_ENABLED` | `false` |
| `LLM_PROVIDER` | `ollama` |
| `LLM_MODEL` | `llama3.1:8b` |
| `LLM_MIN_CONFIDENCE` | `0.75` |
| `LLM_FALLBACK_TO_RULES` | `true` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |

#### Enable Ollama classifier

1. Install [Ollama](https://ollama.com/) and start it.
2. Pull the model:

```powershell
ollama pull llama3.1:8b
```

3. In `.env`:

```ini
LLM_CLASSIFIER_ENABLED=true
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
```

4. Run as usual:

```powershell
python main.py --text
python main.py --voice --speak
```

If Ollama is off, JARVIS falls back to rule-based classification (when `LLM_FALLBACK_TO_RULES=true`).

Logs include `classifier_source`: `rules`, `llm`, `fallback`, or `clarification`.

## Capabilities (Phase 5)

Ask what JARVIS can do — still routed through the normal pipeline:

```text
מה אתה יודע לעשות
show capabilities
איזה פקודות מסחר יש
תסביר סקיל לוגים
תן עזרה על לופ יומי
help run daily loop
```

| Skill | Examples |
|-------|----------|
| **Trading** | dashboard, loops, positions, rejections |
| **Logs** | errors, search logs, summarize, open log |
| **Code search** | find function/class, risk usage, code text |
| **Files** | open project folder |
| **System** | CPU/RAM, disk, network, terminal |
| **Assistant** | capabilities, list skills, explain skill, help |

Skills are **metadata only** — execution always uses `router → security → ActionRegistry`. No second execution path.

## Memory (Phase 6)

### What it stores

| File | Content |
|------|---------|
| `data/memory.json` | Facts and labeled entries |
| `data/preferences.json` | User preferences |
| `data/aliases.json` | Phrase → allowlisted intent |
| `data/backups/` | Timestamped backups before each write |

### What it refuses

- API keys, tokens, passwords, private keys  
- `.env`-style lines, credit card patterns, long base64 blobs  
- Shell/code in alias params  

### Example commands

```text
זכור שאני מעדיף פקודות בעברית
זכור שהפרויקט הראשי שלי הוא C:\FINAL_ALGO_TRADER
זכור שכאשר אני אומר פתח מסחר אני מתכוון לפתוח דאשבורד
תראה מה אתה זוכר
חפש בזיכרון risk
קבע alias: פתח מסחר = open_trading_dashboard
תראה aliases
שכח alias פתח מסחר
```

Aliases still require normal **confirmation** for destructive intents (e.g. daily loop).

### Reset memory

Delete or edit files under `data/` (keep backups if needed), or remove entries via `forget_memory` / `delete_alias`.

## Run

**Tray (Phase 7):**

```powershell
python main.py --tray
python main.py --tray --speak
python main.py --tray --voice --speak
```

Tray menu uses the same `handle_text_command()` pipeline. Notifications show result summaries (secrets redacted). Toggle **Voice** / **Speak** from the tray menu.

**Text:**

```powershell
python main.py
python main.py --text --speak
```

**Voice (console):**

```powershell
python main.py --voice
python main.py --voice --speak
```

**CLI flags:**

| Flag | Effect |
|------|--------|
| `--tray` | System tray background mode |
| `--no-tray` | Explicitly disable tray |
| `--speak` | Enable TTS for this run |
| `--no-speak` | Disable TTS for this run |
| `--voice` | Push-to-talk (with tray: background thread) |
| `--hotkey` | SPACE toggle recording (Windows) |

Without `--speak`, TTS runs only if `TTS_ENABLED=true` in `.env`.

### Phase 13 — Wake word (openWakeWord)

**Disabled by default.** Wake word only starts a **temporary listening session** → STT → `handle_text_command()` → router/security/registry. It never runs commands on its own.

```powershell
pip install openwakeword onnxruntime
```

**.env:**

```ini
WAKE_WORD_ENABLED=false
WAKE_WORD_THRESHOLD=0.6
WAKE_COOLDOWN_SECONDS=4
WAKE_MAX_LISTEN_SECONDS=5
WAKE_EARLY_STOP_ENABLED=true
```

**Run:**

```powershell
python main.py --tray --voice --wakeword --speak
```

**Tray:** Wake Word On/Off, Show Wake Word Status (read-only status).

**Privacy:** No wake audio clips saved; temp WAV deleted after STT; transcripts only in existing command logs.

**Troubleshooting:** microphone permissions; raise `WAKE_WORD_THRESHOLD` if false activations; increase `WAKE_COOLDOWN_SECONDS`; CPU use scales with always-on mic stream.

**Wake model file:** `WAKE_WORD_MODEL=jarvis` resolves to `hey_jarvis*.onnx` under openWakeWord `resources/models/`. If missing, JARVIS will **not** fall back to other models (e.g. alexa). Set `WAKE_WORD_MODEL_PATH` or download:

```powershell
py -3 -c "from openwakeword.utils import download_models; download_models(model_names=['hey_jarvis'])"
py -3 main.py --smoke
```

### Phase 12 — Computer control (foundation)

**Disabled by default:** `COMPUTER_CONTROL_ENABLED=true` to enable.

| Type | Intents |
|------|---------|
| Read-only | `get_focused_app`, `list_windows_detailed`, `get_clipboard_summary` |
| Confirm required | `focus_window`, `copy_text_to_clipboard`, `clear_clipboard`, `minimize_window`, `maximize_window` |

**Not included:** click, type_text, hotkeys, coordinates, pyautogui mouse, browser DOM automation.

Clipboard writes block secrets; reads are redacted and capped (`CLIPBOARD_MAX_CHARS`).

Tray (read-only only): **Focused App**, **Clipboard Summary**.

### Phase 11 — Autostart + watchdog

**Tray launcher script:** `scripts/run_jarvis_tray.ps1` (venv if present → `python main.py --tray --voice --speak`, logs under `reports/jarvis_logs/`).

**Autostart:** Windows Startup shortcut → `run_jarvis_tray.ps1` only. `enable_autostart` / `disable_autostart` require **confirmation**. `show_autostart_status` is read-only.

**Watchdog:** Runs in tray mode every `WATCHDOG_INTERVAL_SECONDS` (default 120). Writes `data/watchdog_status.json`. Notifies on **critical** issues only. **No repairs or restarts.**

| Command | Intent |
|---------|--------|
| תפעיל הפעלה אוטומטית | `enable_autostart` (confirm) |
| תבטל הפעלה אוטומטית | `disable_autostart` (confirm) |
| מצב הפעלה אוטומטית | `show_autostart_status` |
| בדוק את ג'רוויס | `run_jarvis_health_check` |
| מה מצב watchdog | `show_watchdog_status` |

### Phase 10 — Workflows (predefined sequences)

Multi-step workflows are **defined in code only** (no LLM planning). Each step calls the same router path as a normal command.

| Workflow | Steps |
|----------|--------|
| `trading_health_check` | dashboard health → last errors → rejections → diagnostics |
| `screen_error_check` | active window → detect screen errors → analyze screen |
| `code_risk_review` | risk usage → delayed entry → execution events |
| `jarvis_self_check` | system status → skills → memory → diagnostics |

**Commands:**

| Command | Intent |
|---------|--------|
| תראה workflows / list workflows | `list_workflows` |
| תריץ בדיקת מערכת מסחר | `run_workflow` → `trading_health_check` |
| בדוק שגיאות במסך | `run_workflow` → `screen_error_check` |
| run workflow `<name>` | `run_workflow` |
| תסביר workflow מסחר | `explain_workflow` |

**Behavior:** Confirm-required steps **pause** the workflow; failed steps are recorded but later steps still run. Output includes per-step summaries, failed step indexes, and safe next-step suggestions.

### Phase 9 — Diagnostics (read-only)

Cross-source analysis returns structured findings:

- **top issue** — highest-severity correlated problem  
- **evidence** — lines from logs, dashboard, screen, or runtime  
- **severity** — `critical` / `high` / `medium` / `low` / `info`  
- **likely cause** — heuristic explanation (no auto-fix)  
- **suggested next steps** — safe read-only commands only  

**Commands:**

| Command | Intent |
|---------|--------|
| run diagnostics / הרץ אבחון | `run_diagnostics` |
| diagnose dashboard | `diagnose_dashboard` |
| diagnose trading loop | `diagnose_trading_loop` |
| diagnose recent errors | `diagnose_recent_errors` |
| analyze current screen | `analyze_current_screen` |
| explain last failure | `explain_last_failure` |
| suggest next steps | `suggest_next_steps` |

**Rules:** No fixing, no shell generation, no mouse/keyboard/browser automation. All intents use the normal router → security → registry path.

### Phase 8 — Vision (read-only)

**Setup:**

```powershell
pip install -r requirements.txt
# Install Tesseract OCR for Windows if needed; set TESSERACT_CMD in .env if not on PATH
```

**.env:**

```ini
VISION_ENABLED=true
VISION_OCR_ENABLED=true
VISION_SAVE_SCREENSHOTS=false
```

**Example commands (Hebrew / English):**

| Command | Intent |
|---------|--------|
| מה יש במסך | describe_screen |
| קרא את הטקסט במסך | read_screen_text |
| יש שגיאה במסך? | detect_screen_errors |
| איזה חלון פתוח? | get_active_window |
| תראה חלונות פתוחים | list_visible_windows |
| צלם מסך | take_screenshot |

**Limitations:**

- Read-only only — no mouse, keyboard, or click automation
- No browser automation; no external screenshot upload by default
- OCR quality depends on resolution, language packs, and Tesseract
- Screenshots are **not saved by default** (`VISION_SAVE_SCREENSHOTS=false`); secrets in OCR text are redacted when enabled

### Phase 35 — Screen Understanding v1 (read-only)

**Config (`.env`):**

```ini
SCREEN_UNDERSTANDING_ENABLED=true
SCREEN_CAPTURE_MODE=active_window
SCREEN_CAPTURE_SAVE_DEBUG=false
SCREEN_CAPTURE_TEMP_DIR=reports/screen_temp
SCREEN_OCR_ENABLED=true
SCREEN_REDACTION_ENABLED=true
SCREEN_BLOCK_SECRET_WINDOWS=true
```

**Commands:**

| Command | Intent |
|---------|--------|
| describe screen / what is on my screen | `describe_screen` |
| read screen / read what is on screen | `read_screen_text` |
| analyze active window | `analyze_active_window` |
| find on screen &lt;query&gt; / where is &lt;x&gt; on screen | `find_on_screen` |

**Usage flow:**

1. **describe screen** — concise summary of active window + redacted OCR preview (no clicks).
2. **read screen** — full visible text via local OCR, redacted before display.
3. **analyze active window** — window title/process + content summary for the foreground window only.
4. **find on screen settings** — locates text/labels in OCR; returns region hints only; always ends with *No click was performed.*

**Safety:** read-only capture; temp images only under `reports/screen_temp` (auto-deleted unless debug); secret window titles blocked; audit logs omit OCR bodies. Legacy `VISION_*` flags still apply when `SCREEN_UNDERSTANDING_ENABLED=false`.

### Phase 36 - Memory Graph v1 (read-only)

The memory graph is derived from existing safe stores: `data/memory_store.json` and `data/project_index.json`. It does not create a new execution path; commands still flow through classifier -> router -> security -> registry -> action.

**Commands:**

| Command | Intent |
|---------|--------|
| show memory graph | `show_memory_graph` |
| search memory graph router | `search_memory_graph` |
| search knowledge graph dashboard | `search_memory_graph` |

**Usage flow:**

1. `remember this category:project router decisions must preserve security` stores a safe memory entry.
2. `index project` refreshes project summaries.
3. `show memory graph` shows node/edge counts and sample links.
4. `search memory graph router` returns matching memory, file, tag, category, and keyword nodes.

**Safety:** read-only derived graph; redaction is applied before display; no shell, browser, mouse, keyboard, workflow, or trading action is executed by graph commands.

### Phase 37 — Conversational layer v1 (supervised)

**Config:**

```ini
CONVERSATION_ENABLED=true
CONVERSATION_CONTINUATION_ENABLED=true
CONVERSATION_MAX_TURNS=10
```

**Behavior:** After each routed command, JARVIS stores redacted turns in `data/conversation_context.json`, adds deterministic follow-up suggestions, and may append one line: *Would you also like me to …?* The user must still issue a normal command — nothing runs automatically. `show jarvis status` reports conversation settings.

### Phase 37e — Latency polish

**Config:**

```ini
CONVERSATION_FAST_ACK_ENABLED=true
TTS_FAST_SUMMARY_ENABLED=true
ASYNC_PERSISTENCE_ENABLED=false
```

**Behavior:** After intent classification (before execute), voice/overlay may show a short ack such as *Got it — checking…*, *Opening…*, or *Looking at your screen…*. Confirm-required intents ack with *I need confirmation before doing that.* (no execution). TTS may speak the first sentence of the final summary when `TTS_FAST_SUMMARY_ENABLED=true`; the full summary text in the UI is unchanged. Optional async persistence writes audit/session/conversation logs in the background (`ASYNC_PERSISTENCE_ENABLED=true`).

### Phase 7 limitations

- Tray requires an interactive **desktop session** (not headless server).
- Notifications vary by Windows environment (pystray / optional toast); console fallback always works.
- No wake word; no autonomous background task execution.
- Tray does **not** expose confirm-required actions (e.g. live loops, shutdown).
- Voice from tray: enable via menu or start with `--tray --voice` (push-to-talk in a background thread).

## Phase 14 — Visual overlay

Iron Man / JARVIS-style transparent overlay (PySide6): glowing animated circle, status, transcript, result summary. **UI only** — no command execution, no mouse/keyboard/browser control. Commands still go through `handle_text_command()` → router. Text is redacted before display.

**Install:**

```powershell
pip install PySide6
# or: pip install -r requirements.txt
```

**.env:**

```ini
OVERLAY_ENABLED=true
OVERLAY_ALWAYS_ON_TOP=true
OVERLAY_OPACITY=0.88
OVERLAY_AUTO_HIDE_SECONDS=12
OVERLAY_STAY_OPEN_ON_ERROR=true
OVERLAY_STAY_OPEN_ON_SUGGESTIONS=true
OVERLAY_READY_VISIBLE_SECONDS=8
OVERLAY_SHOW_TRANSCRIPT=true
OVERLAY_SHOW_RESULT=true
OVERLAY_THEME=jarvis_blue
```

**Run with overlay:**

```powershell
py -3 main.py --tray --voice --wakeword --speak
```

**Tray menu:** **Overlay: On/Off**, **Show Overlay Test** (UI preview only).

**Flow:** wake detected → listening (pulse) → transcribing → transcript → thinking → result → done/speaking → auto-hide.

Push-to-talk (`--voice`) updates the same overlay when `runtime.overlay_enabled` is true.

## Troubleshooting (startup / tray / wake word)

If the command returns to PowerShell immediately (or you only see `Python` with no tray icon):

1. Edit **`.env`** in `local_jarvis`, not **`.env.example`**.
2. Create your env file:
   ```powershell
   cd C:\J.A.R.V.I.S\local_jarvis
   copy .env.example .env
   ```
3. Run the smoke test (no microphone listening):
   ```powershell
   python main.py --smoke
   ```
4. Start tray with startup diagnostics:
   ```powershell
   python main.py --tray --debug-startup
   ```
   You should see `Tray started. JARVIS is running in background.` and the process should stay running until you exit from the tray menu.
5. Full tray + voice + wake word + TTS:
   ```powershell
   python main.py --tray --voice --wakeword --speak --debug-startup
   ```

**Windows Store Python stub:** If `python` prints only `Python` and exits, JARVIS never started. Use:
```powershell
py -3 main.py --smoke
.\jarvis.ps1 --tray --debug-startup
```

**Safe debug mode (minimal text loop):**
```powershell
py -3 main.py --safe-mode
```

**Logs:** `reports/jarvis_logs/startup_latest.log` and daily `startup_YYYYMMDD.log` (no secrets).

| Symptom | What to try |
|---------|-------------|
| Exits immediately | `--smoke`; fix `.env`; use full Python path |
| No tray icon | `pip install pystray Pillow`; desktop session required |
| Wake word off despite flag | `--wakeword` overrides `WAKE_WORD_ENABLED=false` for that run |
| Wake word errors in console | `pip install openwakeword onnxruntime`; check mic in smoke test |

## Troubleshooting (TTS)

| Issue | What to try |
|-------|-------------|
| No speech heard | Confirm `--speak` or `TTS_ENABLED=true`; check volume |
| `pyttsx3` error | `pip install pyttsx3` |
| Hebrew sounds wrong | Install a Hebrew Windows voice, or set `TTS_LANGUAGE=en` / pick `TTS_VOICE` |
| Garbled/long output | Lower `TTS_MAX_CHARS`; summaries are truncated automatically |
| TTS warning in console | Non-fatal — command still succeeded |

## Recommended English voice mode

Default STT is **English-only** (`STT_LANGUAGE=en`). Hebrew is used only if you explicitly set `STT_LANGUAGE=he`.

**.env:**

```ini
STT_LANGUAGE=en
STT_MODEL=base
STT_ENABLE_NORMALIZATION=true
```

Whisper runs with `language="en"` (forced — no auto-detect in English mode).

**Example spoken commands:**

- Hey Jarvis *(wake word)*
- Show STT status
- Open dashboard / Open the dashboard
- Show dashboard health / Check the dashboard
- Run diagnostics / Run a system check
- Show last errors / Show me the errors
- List workflows
- Check trading / Check my trading system *(trading health workflow)*
- What can you do

Check settings: `show stt status` or `show speech status`

**Optional Hebrew** (explicit only):

```ini
STT_LANGUAGE=he
STT_MODEL=medium
```

## Troubleshooting (voice / STT)

| Issue | What to try |
|-------|-------------|
| No microphone | Windows sound settings; `STT_DEVICE` index |
| Poor English quality | `STT_MODEL=small` or `medium`; `STT_ENABLE_NORMALIZATION=true` |
| Hebrew mode | Set `STT_LANGUAGE=he` explicitly (not auto from locale) |
| Wrong language | Default is `STT_LANGUAGE=en` (forced in Whisper) |
| Debug mic levels | `STT_DEBUG_MIC=true` — RMS/peak in logs |
| Slow STT | `STT_MODEL=base` or `tiny` (lower accuracy) |
| STT config | Command: `show stt status` |

## Tests

```powershell
python -m pytest -q
```

TTS/voice tests use mocks — no microphone or speakers required.

## Roadmap

1. Phase 1 — Text router ✓  
2. Phase 1.5 — Hardening ✓  
3. Phase 2 — Push-to-talk STT ✓  
4. Phase 3 — Optional TTS ✓  
5. Phase 4 — Optional LLM classifier ✓  
6. **Phase 5** — Skill system ✓  
7. **Phase 6** — Memory & aliases ✓  
8. **Phase 7** — Tray app ✓  
9. **Phase 8** — Vision / screen understanding ✓  
10. **Phase 9** — Diagnostics ✓  
11. **Phase 10** — Safe workflow runner ✓  
12. **Phase 11** — Autostart + health watchdog ✓  
13. **Phase 12** — Safe computer control foundation ✓  
14. **Phase 13** — Wake word activation layer ✓  
15. **Phase 14** — Visual overlay (PySide6, wake/voice UI feedback) ✓  
16. **Phase 15** — Safe app launcher (Start Menu allowlist) ✓  
17. **Phase 16** — Safe website launcher (https allowlist, `webbrowser.open` only) ✓  
18. **Phase 19** — Supervised task agent (plan / approve / single-step execute) ✓  
19. **Phase 20** — Task findings + patch proposals + engineering reports ✓  
20. **Phases 21–30** — Patch apply/rollback, trading review, queue, workspaces, guided UI, DOM read, artifacts, health ✓  

## Phase 16 — Safe website launcher

Opens **allowlisted https sites** in the default browser. No Selenium/Playwright, no arbitrary URLs, no DOM control.

| Built-in site | URL |
|---------------|-----|
| chatgpt | https://chatgpt.com |
| tradingview | https://www.tradingview.com |
| youtube | https://www.youtube.com |
| gmail | https://mail.google.com |
| google | https://www.google.com |
| github | https://github.com |
| yohananof | https://www.ybitan.co.il |
| openai | https://platform.openai.com |

**Commands (voice or text):** `open chatgpt`, `open youtube`, `list websites`, `forget website mysite`  
**Hebrew:** `פתח יוטיוב`, `פתח גימייל`, `פתח צאט גיפיטי`  
**Tray:** Open ChatGPT / TradingView / YouTube / Gmail (fixed phrases only)

User-approved sites persist in `data/approved_websites.json`. Non-built-in catalog entries require confirmation before first open.

## Phase 19–20 — Supervised task agent

Multi-step engineering tasks (trading review, dashboard investigation, failure reports) use a **supervised** loop — not an autonomous agent.

**Example flow**

1. `review my trading algorithm` → plan created (not executed)
2. `show task plan` → inspect steps and approvals
3. `approve task plan` → unlock step execution
4. `run task step` → one allowlisted read-only step (search, diagnostics, `pytest`, `compileall`, …)
5. `show task findings` → grouped evidence, severity, suggested checks
6. `propose task patch` → unified diff preview only (does **not** apply)
7. `approve task patch` → marks approved only (still not applied in Phase 20)
8. `show task report` → `reports/task_agent/task_YYYYMMDD_HHMMSS.md`

**Commands:** `start_task`, `show_task_plan`, `approve_task_plan`, `run_task_step`, `stop_task`, `show_task_status`, `show_task_report`, `show_task_findings`, `propose_task_patch`, `show_task_patch`, `approve_task_patch`, `reject_task_patch`

**Safety:** no arbitrary shell; no auto file writes; patch cannot target `.env`/secrets; no live-trading-enabling diffs.

## Phases 21–30 — Operating layer

| Phase | Capability |
|-------|------------|
| 21 | `apply task patch` (after approve + confirm), backup, `rollback task patch`, `show last diff` |
| 22 | `review trading algorithm`, `compare backtest to paper`, `find live backtest mismatch` |
| 23 | `generate backtest paper report` — metrics/divergence markdown |
| 24 | `plan experiments` — grid plan only |
| 25 | `queue task`, `show task queue`, `pause/resume task queue` |
| 26 | `start trading/study/dev workspace` — approved app/site checklist |
| 27 | `suggest ui click` + `confirm ui click` (semantic targets, no pixel click) |
| 28 | `browser dom read` (allowlist; set `BROWSER_DOM_ENABLED=true`) |
| 29 | `build presentation about X`, `create report about X` → `reports/artifacts/` |
| 30 | `show startup health`, `show settings status`; launcher: `scripts/run_jarvis.ps1` |
| 31 | `show jarvis status` — unified read-only status center |
| 32 | `show command audit` — redacted JSONL audit trail (last 20) |
| 33 | `show approvals`, `approve/reject pending action`, `clear approvals` |
| — | Background quiet mode: tray/wake only; `show overlay` / `hide overlay` / `toggle quiet mode` |
| 34 | Personal knowledge: `remember this`, `show memory`, `index project`, `search project knowledge` |
| 35 | Screen understanding v1: `describe screen`, `read screen`, `analyze active window`, `find on screen` |
| 36 | Memory graph v1: `show memory graph`, `search memory graph <query>` |

**Run:** `py -3 -m pytest -q` from `local_jarvis/`

**Not included:** autonomous agents/planning loops, LLM-generated workflows, browser automation, web search, real trading execution, LLM shell/code execution, arbitrary mouse/keyboard automation, wake word direct command execution, background audio storage.
