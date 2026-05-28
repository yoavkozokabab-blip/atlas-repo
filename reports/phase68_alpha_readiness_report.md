# Phase 68 — Friend & Family Alpha Readiness

Generated for controlled alpha with 3–5 trusted users. No new core product capabilities; installation, safety, onboarding, and logging only.

## What alpha users can do

See [alpha_user_commands.md](alpha_user_commands.md) for the full safe command list. Highlights:

- Screen description and summarization
- Open websites and search the web
- Summarize the current browser page
- Remember and recall short notes
- Daily summary (mock/read-only integrations in default alpha)
- Real voice conversation test (mic + STT + TTS with evidence)
- Stop listening (end voice session)
- `alpha setup check` and `show alpha report`

## What is blocked (ALPHA_MODE, unless DEVELOPER_MODE=true)

- File deletion and destructive memory wipes
- Patch apply and investigation/trading automation
- Kill switch, trading loops, autostart changes
- Sending messages/emails
- Risky phrases (password, purchase, delete, etc.)
- Most trading/investigation notifications (non-critical)

Desktop typing/clicks use safe mode; computer control master switch defaults to **off**.

## Known limitations

- Email/calendar default to **mock** providers unless you configure readonly OAuth/fixtures
- Voice `test real voice conversation` needs a working microphone; TTS uses direct isolated playback path
- Browser requires Playwright + Chromium installed
- OCR may be empty on some windows; accessibility fallback may apply
- Alpha logs are local only under `data/alpha_sessions/`
- Not a hosted/multi-user product; one machine per tester

## Setup instructions

1. Install Python 3.10+ (not Windows Store stub) and run `pip install -r requirements.txt`
2. Install Playwright browser: `playwright install chromium`
3. Copy `.env.example` to `.env` if needed; optional: set `ALPHA_MODE=true`
4. Launch:

```powershell
cd c:\J.A.R.V.I.S\local_jarvis
.\scripts\launch_alpha.ps1
```

Text-only mode: `.\scripts\launch_alpha.ps1 -TextOnly`

5. First command: `alpha setup check` — aim for all **PASS**
6. Share [alpha_user_commands.md](alpha_user_commands.md) with testers

### Recommended env (launcher sets these)

| Variable | Alpha value |
|----------|-------------|
| `ALPHA_MODE` | `true` |
| `DEVELOPER_MODE` | `false` |
| `COMPUTER_CONTROL_ENABLED` | `false` |
| `PATCH_APPLY_ENABLED` | `false` |
| `DESKTOP_OPERATOR_SAFE_MODE` | `true` |
| `ALPHA_SUPPRESS_DEV_NOTIFICATIONS` | `true` |

## Rollback instructions

1. Stop JARVIS (tray exit or Ctrl+C in console)
2. Set `ALPHA_MODE=false` in `.env` or remove the variable
3. Restore prior flags if you changed them (`COMPUTER_CONTROL_ENABLED`, etc.)
4. Optional: archive `data/alpha_sessions/` for review, then delete to clear tester logs
5. Run normal launcher: `.\scripts\start_jarvis.ps1` or `.\jarvis.ps1`

## Validation

```powershell
py -3 scripts\smoke_phase68_alpha_readiness.py
```

## Files added (Phase 68)

| Path | Purpose |
|------|---------|
| `scripts/launch_alpha.ps1` | One-click alpha launcher with preflight checks |
| `alpha/mode.py` | Alpha defaults |
| `alpha/safety.py` | Safety blocks |
| `alpha/session_log.py` | Per-session JSONL logs |
| `alpha/setup_check.py` | First-run checklist |
| `alpha/report.py` | Alpha usage report |
| `actions/phase68_alpha_actions.py` | `alpha setup check`, `show alpha report` |
