# Desktop + Browser Operator Production Readiness

**Date:** 2026-05-29  
**Evidence:** `browser/runtime.py`, `desktop/`, `vision/`, `computer_control/`, `agents/operator_agent.py`

---

## Section 1: Browser

### What Exists
- `browser/runtime.py` — facade with `provider="mock"` default
- `browser/dom_read.py` — DOM extraction
- `browser/url_parser.py` — URL normalisation and validation
- `browser/task_planner.py` — multi-step planning
- `browser/memory.py` — visited page cache

### What Works
- URL validation: enforces HTTPS, blocks localhost (except configured trading dashboard)
- Mock mode is clearly labeled: `_MOCK_BANNER = "MOCK MODE | NO REAL EXTERNAL ACCESS | SIMULATED OUTPUT ONLY"` (`browser/runtime.py:14`)
- `BrowserRuntimeState.format_debug()` shows mock vs real status
- Replay log written to `data/browser_action_replay.jsonl`

### What Is Broken or Missing

**BR-1: Default provider is `"mock"` — Playwright not installed by default**  
```python
# browser/runtime.py:23
provider: str = "mock"
```
If Playwright is not installed, all browser actions return simulated output. The `_MOCK_BANNER` is present in output but there is no startup warning. A user could issue "summarize this page" and receive fabricated content without realizing it.  
**Fix:** At startup, check if Playwright is importable. If not, set `BROWSER_PROVIDER_NOTE="mock"` and display in startup health. Log clearly: "Browser: mock mode (Playwright not installed)."

**BR-2: DOM extraction is read-only and not real DOM — it is a mock summary**  
`browser/dom_read.py` produces a summary string, not actual DOM parsing. When provider is "mock", the DOM excerpt is simulated.  
**Fix:** When Playwright is available, use `page.content()` to get real HTML; extract meaningful text with `BeautifulSoup`.

**BR-3: `browser_action_replay.jsonl` is append-only with no rotation**  
Already 120 KB. Same problem as observability JSONL. Rotate at 5 MB.

**BR-4: Browser memory exists in two places**  
`browser/memory.py` (in-process cache) and `data/browser_memory.json` (persisted). See Consolidation Plan C-10.

**BR-5: No real web search implementation**  
`browser/runtime.py:search_web()` opens a Google search URL in mock mode. There is no web content extraction. "Search the web for X" returns a mocked URL, not actual search results.  
**Impact:** All research intents that involve web search return fabricated data unless Playwright is installed.

### Actual State
Browser is a well-labeled mock. It does not pretend to be real. The problem is not dishonesty — it is lack of a real implementation.  
**Readiness: 35%** (mock mode is working correctly; real mode requires Playwright installation and DOM extraction implementation)

---

## Section 2: Desktop Control

### What Exists
- `desktop/control_runtime.py` — window focus, minimise, maximise
- `computer_control/` — clipboard, keyboard
- `apps/` — app discovery and launcher

### What Works
- Window control via `win32gui` — real Win32 calls, not mocked
- App launcher reads Start Menu `.lnk` files — real discovery
- Clipboard access gated behind confirmation
- Website launcher enforces HTTPS allowlist
- `desktop/vision_runtime.py` — screen capture using `pyautogui` or `PIL`

### What Is Broken or Missing

**DC-1: `.lnk` target not shown to user before approval**  
When JARVIS proposes to open an app, the user sees the shortcut name, not the resolved executable path. A `.lnk` could point to an unexpected location.  
**Fix:** Before showing confirmation prompt, resolve `.lnk` target via `win32com.shell.shell.ShellLink` and display the target path.

**DC-2: Window focus race condition**  
`focus_window()` calls `SetForegroundWindow()`. On Windows, this can fail if the calling process is not the foreground process. The call silently fails with `win32gui.error`.  
**Current handling:** Caught by outer try/except; returns error string.  
**Improvement:** Retry once with `AllowSetForegroundWindow()` before failing.

**DC-3: `pywin32` not verified at startup**  
If `win32gui` is not installed, desktop control fails at runtime. There is no startup check.  
**Fix:** Add `win32gui` import check to startup health report.

**DC-4: No desktop state persistence**  
`desktop/memory.py` stores recent actions but not current window state. After a JARVIS restart, there is no memory of which windows were open.  
**Assessment:** Low priority — this is a feature gap, not a reliability issue.

### Actual State
Desktop control works for the main use cases (focus, minimise, open app). Main gaps are the `.lnk` target display and `pywin32` startup validation.  
**Readiness: 60%**

---

## Section 3: Vision / OCR

### What Exists
- `vision/screen_capture.py` — PIL/pyautogui screenshot
- `vision/ocr.py` — Tesseract OCR
- `vision/active_window.py` — foreground window info via `win32gui`
- `vision/screen_understanding.py` — legacy v1 and current implementation (v35/v36)
- `desktop/ocr_pipeline.py` — duplicate OCR pipeline

### What Works
- Screen capture works if `PIL` (`Pillow`) is installed
- Tesseract OCR works if Tesseract is installed and in PATH
- `active_window.py` returns correct foreground window info

### What Is Broken or Missing

**V-1: Two OCR pipelines**  
`vision/ocr.py` and `desktop/ocr_pipeline.py` both wrap Tesseract. See Consolidation Plan C-8.

**V-2: `screen_understanding.py` has two implementations**  
"v1" and the current version coexist in the same file. It is unclear which is used.  
**Fix:** Delete v1; keep current; add a comment marking the deprecation date.

**V-3: Tesseract not in PATH produces unhelpful error**  
If Tesseract is not installed, OCR calls raise `TesseractNotFoundError` which propagates up as an unhandled exception in some paths.  
**Fix:** Catch at OCR layer; return `{"text": "", "ocr_available": False}`; log once at startup.

**V-4: Screenshot files accumulate in `data/desktop_screenshots/`**  
No cleanup. Each `take_screenshot` intent saves a PNG file.  
**Fix:** Keep only the 10 most recent; delete others after each capture.

### Actual State
Vision works when dependencies are installed. Main gaps are the two duplicate OCR paths and screenshot accumulation.  
**Readiness: 55%**

---

## Section 4: Automation Safety

### What Works (Confirmed by Code)
- Clipboard write and window focus require confirmation (`CONFIRMATION_REQUIRED_INTENTS` in `config.py`)
- Website launcher enforces HTTPS allowlist (`approved_websites.json`)
- App launcher reads only Start Menu `.lnk` files
- PowerShell blocked except for 3 hardcoded script paths
- No arbitrary shell string composition anywhere

### What Could Be Improved

**AS-1: `data/approved_websites.json` is user-writable**  
The website allowlist lives in `data/` which JARVIS writes to. An attacker with write access to `data/` can add arbitrary URLs.  
**Fix:** Move primary allowlist to `config/approved_websites.json` under source control. User-added sites go to `data/user_approved_websites.json` (clearly labeled as user-controlled).

**AS-2: No rate limiting on confirmation requests**  
If the user says "open app" rapidly 10 times, 10 confirmation prompts queue up. The user could accidentally approve a later one while thinking they're approving the first.  
**Fix:** Reject new confirmation-requiring commands while one is pending.

---

## Section 5: Recovery and Failure Handling

### Browser Recovery
- `BrowserRuntimeState.last_exception` records the last error
- On session failure, next request creates a new session
- Mock mode has no session state to lose

### Desktop Recovery
- Window handle stale → `win32gui.IsWindow()` returns False → error returned to user; no retry
- App launch failure → error returned; no retry

### Missing Recovery

**RC-1: No desktop health check**  
`reliability/desktop_health.py` has `show_desktop_operator_health()` but it only reports config state, not whether Win32 API calls actually work.  
**Fix:** Add a real check: `win32gui.GetDesktopWindow()` should return a non-zero HWND.

---

## Actual Readiness

| Component | State | Score |
|-----------|-------|-------|
| Browser (mock) | Clearly labeled; no real implementation | 35% |
| Browser (real, Playwright) | Works if installed; not validated at startup | 50% |
| Desktop window control | Works; `.lnk` target gap; Win32 startup check missing | 60% |
| Vision / OCR | Works with dependencies; two duplicate pipelines | 55% |
| Automation safety | Strong; one allowlist location gap | 75% |
| Recovery | Minimal; no health check with real probes | 40% |
| **Overall operator** | | **52%** |

---

*End of Operator Production Readiness — 2026-05-29*
