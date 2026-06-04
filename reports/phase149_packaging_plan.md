# Phase 149B-D - Packaging, Installer, and Failure Recovery Plan

Date: 2026-06-04

Scope: audit and implementation plan only. No Atlas production code was changed
for this phase.

## Executive Summary

The fastest path to a true consumer-style Atlas launch experience is:

1. Package Atlas Desktop as a self-contained Windows executable using
   PyInstaller one-folder mode.
2. Build `Atlas_Setup.exe` with Inno Setup around the PyInstaller output.
3. Make the installed shortcuts launch `Atlas.exe` directly in windowed mode.
4. Keep browser auto-open, diagnostics, support bundle, logs, and local-only
   data paths.
5. Add a top-level failure recovery wrapper in the future implementation phase
   so startup failures open a support page instead of exposing tracebacks.

Recommended beta approach: PyInstaller one-folder, windowed, desktop-only
dependency set.

Not recommended for the first beta: packaging the full monorepo requirements or
using Nuitka as the first pass.

## Current Packaging State

Current installer files exist, but they do not yet create a self-contained
consumer executable:

- `installer_build.ps1` checks for Inno Setup and invokes `installer/jarvis.iss`.
- `installer/jarvis.iss` stages repository files and creates shortcuts.
- `Launch Atlas.bat` and `Launch Atlas.vbs` still depend on a Python runtime
  unless `Atlas.exe` already exists.
- `run_atlas.py` is the current practical desktop entry point.

Current package availability on this machine:

- PyInstaller: not installed.
- Nuitka: not installed.
- `tkinter`: available.
- `yaml` / PyYAML: available.
- `fastapi`: available.
- `uvicorn`: not available.

Atlas Desktop can run without FastAPI/Uvicorn because `jarvis_desktop.server`
has a stdlib `ThreadingHTTPServer` path. That is the right default for a
desktop-only packaged beta.

## Packaging Recommendation

Use PyInstaller first.

Rationale:

- Lowest implementation risk for a Windows desktop beta.
- Mature support for bundling Python runtime, stdlib server, Tkinter, data
  files, and pure-Python packages.
- Supports `--windowed` / `--noconsole`, which directly resolves the visible CMD
  blocker.
- One-folder output is easier to inspect, patch, and diagnose than one-file
  output.
- Works naturally with Inno Setup: install the PyInstaller dist folder and point
  shortcuts at `Atlas.exe`.

Use Nuitka later only if PyInstaller proves unacceptable due to startup speed,
antivirus behavior, or binary size.

Nuitka first-pass risks:

- Longer build setup.
- Likely compiler toolchain requirements.
- Slower iteration while hidden imports and data-file bundling are still being
  discovered.
- Higher risk of spending the beta-blocker phase on build tooling instead of
  launch reliability.

## Proposed Executable Shape

Target:

```text
dist/
  Atlas/
    Atlas.exe
    _internal/
    jarvis_desktop/
    builder_core/
    ...
```

Launch path:

```text
Desktop shortcut
  -> Atlas.exe
    -> startup checks
    -> local desktop server
    -> browser opens automatically
    -> support fallback on failure
```

For beta, prefer one-folder over one-file.

One-folder advantages:

- Faster startup than one-file because no temporary extraction is required.
- Easier support diagnostics because files remain visible in the install tree.
- Lower risk of antivirus delay from self-extracting behavior.
- Cleaner Inno Setup packaging.

One-file can be reconsidered after private beta if the product needs a single
portable executable.

## Future PyInstaller Build Sketch

This is a planning sketch, not a command that was run in Phase 149:

```powershell
py -3 -m PyInstaller --noconfirm --clean --windowed --name Atlas `
  --add-data "jarvis_desktop/static;jarvis_desktop/static" `
  --add-data "jarvis_desktop/demo;jarvis_desktop/demo" `
  --add-data "jarvis_desktop/atlas_knowledge;jarvis_desktop/atlas_knowledge" `
  --add-data "builder_core;builder_core" `
  --hidden-import tkinter `
  --hidden-import yaml `
  run_atlas.py
```

The actual implementation should use a checked-in `.spec` file or a dedicated
build script so hidden imports and data files are explicit and repeatable.

## Desktop-Only Dependency Set

Do not package the full repository `requirements.txt`.

The current `requirements.txt` includes voice, STT, TTS, browser automation,
OCR, tray, trading, and other runtime dependencies that are not needed for
Atlas Desktop beta launch. Bundling all of them would make the installer larger,
slower, and more fragile.

Package only the desktop path:

- Python runtime bundled by PyInstaller.
- Standard library modules used by `run_atlas.py`, `jarvis_desktop`, and
  `builder_core`.
- PyYAML, unless Atlas knowledge YAML files are preconverted or removed from the
  runtime path.
- Tkinter / Tcl-Tk, for native folder picker support.
- Any small pure-Python package proven necessary by packaged smoke tests.

Avoid in the beta executable unless a packaged test proves it is required:

- `faster-whisper`
- `sounddevice`
- `onnxruntime`
- `PySide6`
- `playwright`
- `pytesseract`
- `pyautogui`
- `mss`
- trading or voice runtime dependencies

## Data Files to Bundle

Bundle these app assets:

- `jarvis_desktop/static/**`
- `jarvis_desktop/demo/**`
- `jarvis_desktop/atlas_knowledge/**`
- `builder_core/**`
- `docs/ATLAS_QUICKSTART.md`, if still linked from the UI or support flow.
- app icon assets, if present or added in the implementation phase.

Do not bundle:

- `external_repos/**`
- generated benchmark outputs
- user data
- local `.jarvis_builder` folders
- runtime logs
- data directories

Runtime writes must continue to use the app-data path selected by
`jarvis_desktop.data_paths.desktop_data_dir()`.

## Estimated Executable and Installer Size

Measured source payload:

- `jarvis_desktop`: about 5.62 MB.
- `builder_core`: about 4.72 MB.
- combined core desktop source payload: about 10.34 MB.

Estimated PyInstaller beta package:

- one-folder uncompressed install: 70-120 MB.
- compressed installer: 35-70 MB.
- one-file executable, if later used: 50-90 MB, with slower cold start.

Estimated Nuitka package:

- one-folder output: 80-150 MB, depending on compiler and included stdlib.
- compressed installer: likely similar to or larger than PyInstaller for the
  first beta.

These are planning estimates and must be validated by an actual packaged build.

## Estimated Startup Speed

Current Python development path:

- server startup is lightweight after the interpreter is available.
- browser open is currently immediate after server bind.

Estimated packaged startup:

- PyInstaller one-folder cold start: 2-5 seconds.
- PyInstaller one-folder warm start: 1-3 seconds.
- PyInstaller one-file cold start: 5-15 seconds due to extraction.
- Nuitka: likely 1-4 seconds once built, but higher build complexity.

Beta recommendation: optimize reliability before shaving the last startup
second.

## Beta Installer Architecture

Installer target:

```text
Atlas_Setup.exe
```

Install behavior:

- Install Atlas Desktop into a normal Windows application directory.
- Create a Desktop shortcut.
- Create a Start menu shortcut.
- Optionally create a support shortcut that opens Atlas support diagnostics.
- Launch Atlas after install if the user leaves the checkbox enabled.

Recommended install target:

- per-user: `%LOCALAPPDATA%\Programs\Atlas`

Per-user install advantages:

- no admin prompt for private beta.
- avoids Program Files write assumptions.
- aligns with local-first beta distribution.

Shortcut target:

```text
Atlas.exe
```

Shortcuts should not point to:

- `Launch Atlas.bat`
- `Launch Atlas.vbs`
- `py -3 run_atlas.py`
- `python run_atlas.py`

BAT/VBS may remain as developer fallback files, but they should not be the
primary user-facing launch route after packaging.

## Inno Setup Changes Needed Later

Future implementation should update `installer/jarvis.iss` to stage the
PyInstaller output instead of the raw source tree.

Target shape:

```text
Source: "dist\Atlas\*"; DestDir: "{app}"; Flags: recursesubdirs
```

Shortcut shape:

```text
Name: "{autoprograms}\Atlas"; Filename: "{app}\Atlas.exe"
Name: "{autodesktop}\Atlas"; Filename: "{app}\Atlas.exe"
```

The installer should preserve support logs under the Atlas app-data directory,
not under the install directory.

## Failure Recovery Design

User-facing rule:

Atlas startup must never show a Python traceback to a beta user.

Future executable behavior:

1. Start with a top-level exception guard.
2. Initialize launcher logging before importing heavy app modules.
3. Run startup checks.
4. If checks pass, start the local server and open the browser.
5. If checks fail, open support recovery instead of crashing.
6. If the browser cannot open, leave a clear local support URL in logs and, if a
   small native window exists, show it there.

Preferred recovery ladder:

```text
Normal app server starts
  -> open http://127.0.0.1:<port>/

App startup check fails but server can run
  -> open http://127.0.0.1:<port>/support.html

Main app server cannot run
  -> start minimal support-only server on fallback port
  -> open /support.html

No local server can bind
  -> open local static support HTML from app data or install assets
  -> write launcher log and support bundle metadata
```

Support page should show:

- what failed
- whether the app can continue in degraded mode
- data directory path
- log path
- copy diagnostics button
- support bundle button
- practical fix instructions

Tracebacks and raw exceptions should go to logs/support bundles, not the visible
page body unless sanitized.

## Startup Checks to Preserve

Packaged Atlas should preserve the current support readiness checks:

- app-data directory is writable
- support bundle can be generated
- scan history storage is available
- demo repository is available
- configured Atlas paths are valid
- local server can bind to a port
- browser launch is attempted

Additional packaged checks recommended for implementation:

- bundled static assets exist
- bundled demo assets exist
- bundled knowledge assets exist
- `builder_core` imports from the packaged app
- PyYAML availability if YAML assets remain
- Tkinter availability for native Browse
- fallback port path works if `8777` is occupied

## Preserving Diagnostics, Logs, and Support Bundle

Do not write diagnostics into the install directory.

Runtime diagnostics should continue to live under the selected desktop data
directory:

- preferred: user profile desktop data path
- fallback: `%LOCALAPPDATA%\Atlas\desktop_data`
- last-resort fallback: `%TEMP%\atlas_desktop_data`

The packaged launcher should write a launcher-specific log before the main app
server starts. That log should be included in the support bundle.

Recommended log files:

- `launcher.log`
- `startup_checks.json`
- `server.log`
- existing support bundle artifacts

## External Assumptions Removed by Packaging

Packaging should remove these assumptions:

- Python is installed.
- `py.exe` launcher exists.
- `python.exe` is on PATH.
- user can run terminal commands.
- user understands a command prompt.
- closing a terminal is safe.
- pip dependencies are already installed.

Packaging does not remove these assumptions:

- Windows can run unsigned/downloaded apps after SmartScreen warning.
- user has permission to install or run a per-user app.
- browser is installed and registered.
- localhost server binding is allowed.
- antivirus does not quarantine the executable.

## Known Risks

High risk:

- Missing PyInstaller data files causing blank UI or missing demo/knowledge.
- Hidden import misses, especially `yaml` and Tkinter/Tcl-Tk.
- SmartScreen or antivirus friction for an unsigned private beta executable.
- Port `8777` conflicts.
- Browser auto-open blocked or opens wrong browser profile.

Medium risk:

- One-folder install looks less polished if users inspect the directory.
- CDN-hosted graph libraries can make the graph look broken when offline.
- Over-bundling full dependencies creates a very large installer.
- Installer upgrades may leave stale app data if versioning is not explicit.

Low risk:

- Keeping BAT/VBS developer launchers as non-primary fallback files.
- Using stdlib HTTP server for beta instead of optional FastAPI.

## Validation Plan for Future Implementation

Build validation:

- build PyInstaller one-folder output
- install through Inno Setup
- launch from Desktop shortcut
- launch from Start menu shortcut
- confirm no console window appears
- confirm browser opens automatically

Clean-machine validation:

- use a Windows VM or clean user profile without Python on PATH
- run `Atlas_Setup.exe`
- launch Atlas
- confirm the UI appears
- confirm support page works
- confirm support bundle works

Functional smoke validation:

- load Home page
- run sample repository workflow
- run real repository scan
- run Build Plan
- run Investigation
- run Impact
- export prompt/context
- open support page
- copy diagnostics

Failure validation:

- corrupt or remove a bundled static asset
- occupy port `8777`
- make app-data path unwritable where possible
- simulate browser-open failure
- simulate missing knowledge asset
- verify each case opens support recovery instead of exposing traceback

Regression tests to keep running:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase146b_true_beta_blockers.py -q
py -3 -m pytest jarvis_desktop/tests -q
```

Add packaged smoke tests in the implementation phase; do not rely only on source
tests.

## Recommended Implementation Order

1. Add a desktop-only packaging spec/build script.
2. Build `dist/Atlas/Atlas.exe` with PyInstaller one-folder/windowed.
3. Update installer staging to install `dist/Atlas/**`.
4. Point Desktop and Start menu shortcuts at `Atlas.exe`.
5. Add top-level startup failure recovery wrapper.
6. Add launcher log and include it in support bundle.
7. Validate on a Windows environment without Python.
8. Only then consider one-file packaging or Nuitka.

## Final Recommendation

Proceed with PyInstaller one-folder plus Inno Setup for the first private beta.

This is the shortest path from the current developer-style launch chain to:

```text
Download Atlas
Run Atlas_Setup.exe
Double-click Atlas
Browser opens automatically
```

Expected result:

- no Python install
- no terminal commands
- no visible command window
- no CMD process keeping Atlas alive
- support recovery instead of raw tracebacks

Nuitka should remain a fallback optimization path, not the Phase 149 beta
default.
