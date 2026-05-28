# Phase 63 — Desktop Operator Runtime Report

## What Is Real

- **Desktop vision runtime** (`desktop/vision_runtime.py`):
  - Active monitor capture (mss + Pillow)
  - Window detection (pygetwindow)
  - OCR extraction (pytesseract via Phase 35 pipeline)
  - Active app detection (foreground window metadata)
  - Screen region selection metadata
  - UI understanding buckets: buttons, menus, text blocks, dialogs, notifications, taskbar hints

- **Desktop control runtime** (`desktop/control_runtime.py`):
  - Mouse move/click (pyautogui, gated)
  - Keyboard typing and hotkeys (pyautogui, gated)
  - Window focus and app launch (existing computer_control + app registry)
  - Safe automation mode (`DESKTOP_OPERATOR_SAFE_MODE`)

- **Desktop state model** (`desktop/state.py`):
  - active app, focused window, open window count
  - recent actions, screen summaries, screenshot path, truth fields

- **Runtime memory** (`desktop/memory.json` via `desktop/memory.py`):
  - active workflow, current task
  - recent screens, UI state transitions

- **Commands wired**:
  - `what is on my screen`
  - `summarize this screen`
  - `click the button that says ...`
  - `type this ...`
  - `switch to chrome`
  - `list open windows`
  - `take screenshot` (enhanced via desktop vision runtime when enabled)
  - `open discord` (existing `open_app` path; desktop `launch_app` supports allowlisted apps)

## What Is Still Simulated / Limited

- OCR quality depends on Tesseract install and screen content.
- Button click targeting uses OCR block centers (no vision model bounding boxes).
- `click the button that says` does not perform pixel-template matching.
- Control actions require `COMPUTER_CONTROL_ENABLED=true`.
- Risky actions return approval-required responses in safe mode (no auto-approval token flow yet).
- Discord/app launch outside allowlist still uses app discovery with existing approval rules.

## Supported Desktop Actions

| Action | Entry |
|--------|--------|
| Describe screen | `what is on my screen` |
| Summarize screen | `summarize this screen` |
| Screenshot | `take screenshot` |
| List windows | `list open windows` |
| Switch Chrome | `switch to chrome` |
| Type text | `type this <text>` |
| Click labeled button | `click the button that says <label>` |
| Open app | `open discord` / `open_app` |

## Vision Limitations

- No UI element detector model (OCR heuristics only).
- Secret-sensitive windows may block capture/OCR (by design).
- Multi-monitor region selection stores coordinates only (no live overlay picker UI).
- Taskbar/app detection is keyword-based, not shell API deep integration.

## Commands Tested

- Smoke: `py scripts/smoke_phase63_desktop_operator.py`
  - capture desktop
  - detect active app
  - take screenshot
  - OCR text
  - list/switch windows
  - safe typing
  - screen description
  - memory persistence

## Failures

- None in smoke when `SCREEN_UNDERSTANDING_ENABLED=true` and `COMPUTER_CONTROL_ENABLED=true`.
- Runtime degrades when Tesseract missing (OCR partial/disabled warnings).

## Next Blockers

- Approval token continuation for gated clicks/typing.
- Higher-accuracy UI element localization (accessibility tree / UI Automation).
- Structured workflow runner chaining desktop steps with rollback.
- Confidence scoring for OCR match before click execution.
