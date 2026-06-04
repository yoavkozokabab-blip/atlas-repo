# Phase 149A - Startup Audit

Date: 2026-06-04

Scope: audit-only pass for zero-friction Windows launch. No code was changed.
This phase is not about intelligence, graph quality, semantic routing, billing,
or product UI polish.

## Executive Summary

Atlas is not currently a consumer-style Windows app. It can launch reliably when
Python is installed, but the default launch chain still depends on an external
Python interpreter unless a real `Atlas.exe` exists.

Current Phase 149 blockers:

- C1 - Python missing: still blocks launch because `Launch Atlas.bat` falls back
  to `py -3 run_atlas.py`, then `python run_atlas.py`.
- C2 - CMD window stays open: still true for the BAT path. The BAT window is the
  server lifetime.
- C3 - Closing CMD kills Atlas: still true for the BAT path because the Python
  server process runs attached to that console.

Phase 146B improved app-data fallback and several product blockers. It does not
solve zero-friction installation because no packaged runtime is present.

## Current Launch Chain

Observed files:

- `Launch Atlas.bat`
- `Launch Atlas.vbs`
- `run_atlas.py`
- `run_jarvis_desktop.py`
- `installer_build.ps1`
- `installer/jarvis.iss`
- `jarvis_desktop/install_support.py`
- `jarvis_desktop/data_paths.py`
- `jarvis_desktop/server.py`
- `jarvis_desktop/system_browse.py`

### BAT path

`Launch Atlas.bat` does:

1. `cd /d "%~dp0"`
2. If `Atlas.exe` exists, run `start "" "%~dp0Atlas.exe"` and exit.
3. Otherwise print startup copy in a CMD window.
4. Run `py -3 run_atlas.py %*`.
5. If that fails, run `python run_atlas.py %*`.
6. If that fails, print Python install instructions and `pause`.

Implication: without `Atlas.exe`, a non-technical user must already have Python
and either the Windows `py` launcher or `python` on PATH.

### VBS path

`Launch Atlas.vbs` does:

1. Set current directory to the app folder.
2. If `Atlas.exe` exists, run it with window style `1`.
3. Otherwise run `cmd /c "Launch Atlas.bat"` with window style `0`.

Implication: VBS hides the command window when using the BAT fallback, but it
still depends on Python. If the hidden BAT path fails, the user may not see the
failure instructions. If a packaged `Atlas.exe` is console-subsystem, it may
still show a console unless built as a windowed GUI app.

### Python launcher path

`run_atlas.py` does:

1. Parse flags: `--host`, `--port`, `--no-browser`, `--fastapi`, `--support`.
2. Import `jarvis_desktop.install_support` and `jarvis_desktop.server`.
3. Run `startup_checks()`.
4. Append launcher log.
5. If startup checks fail, set `start_path="/support.html"`.
6. If `--fastapi`, try `uvicorn` and fall back to stdlib on exception.
7. Otherwise run the stdlib server via `server.run(...)`.

### Server path

`jarvis_desktop.server.run()` does:

1. Create `ThreadingHTTPServer((host, port), JarvisHandler)`.
2. Print server URL to stdout.
3. Use `webbrowser.open(url)` unless `--no-browser`.
4. Serve forever until KeyboardInterrupt or process termination.

Implication: the process must stay alive. In the BAT path, closing the console
kills the server. In a packaged GUI/windowed executable, closing a terminal is no
longer relevant.

## Startup Dependency Map

| Dependency | Required today? | Required after packaged exe? | Notes |
|---|---:|---:|---|
| Windows | Yes | Yes | Current installer and launchers are Windows-oriented. |
| Python 3.10+ | Yes, unless `Atlas.exe` exists | Bundled inside exe/dist | `install_support._check_python()` requires 3.10+. Current dev machine is Python 3.13. |
| Windows `py` launcher | Yes for primary BAT fallback | No | BAT first tries `py -3`. |
| `python` on PATH | Fallback | No | BAT tries after `py -3` failure. |
| CMD | Yes for BAT path | No for direct exe | BAT is the default visible developer-tool surface. |
| WScript/VBS | Optional | Optional | VBS can hide BAT but is not the actual runtime. |
| `run_atlas.py` | Yes | Embedded or retained as entry script | Best current entry because it runs support redirect. |
| `jarvis_desktop/` package | Yes | Bundled | Includes static UI, support, server, analytics, usage, billing-ready mock infra. |
| `builder_core/` package | Yes | Bundled | Required by `jarvis_desktop.api` for repo understanding and dependency graph. |
| `jarvis_desktop/static/` | Yes | Bundled as data | Required for UI pages. |
| `jarvis_desktop/demo/` | Yes for first-use path | Bundled as data | Required for sample repository workflow. |
| `jarvis_desktop/atlas_knowledge/` | Yes for Build/Investigation quality | Bundled as data | Includes concepts, packs, taxonomy, indexes/cache. |
| PyYAML | Functionally required for curated YAML concepts | Bundled dependency or converted assets | Loader skips YAML concepts if `yaml` is missing. |
| Tkinter/Tcl/Tk | Required for native Browse | Bundled if preserving Browse | `system_browse.py` imports `tkinter` and `filedialog`. |
| Default browser | Required for auto-open | Required | `webbrowser.open(url)` assumes a registered browser. |
| Localhost port 8777 | Required unless changed | Required unless auto-fallback added later | Port conflict can prevent server creation before UI appears. |
| Writable app-data directory | Required | Required | Phase 146B now falls back from home to `%LOCALAPPDATA%` to temp. |
| File read access to target repo | Required after UI appears | Required | Not a pre-UI launch dependency except demo/support flows. |
| FastAPI | Optional | Do not bundle initially | Only used with `--fastapi`; stdlib server is default. |
| Uvicorn | Optional | Do not bundle initially | Same as FastAPI. |
| Internet/CDN | Not required for server | Still affects graph visual | `index.html` loads graph libs from `unpkg`; UI can open without them but first impression may degrade. |

## Python Requirements

Current source requirement:

- Python 3.10+ because code uses modern type syntax such as `Dict[str, Any] | None`
  and startup checks enforce 3.10+.

Current external Python requirement:

- A non-packaged launch needs `py -3` or `python` available.

Current installed package observation:

- `PyInstaller`: not installed.
- `nuitka`: not installed.
- `tkinter`: installed.
- `fastapi`: installed.
- `uvicorn`: not installed.
- `psutil`, `pydantic`, `yaml`, `anthropic`: installed in this development
  environment, but most are not startup requirements for the stdlib server.

The repo-level `requirements.txt` is not appropriate for the desktop launch
path because it includes voice/browser/trading/runtime dependencies such as
`faster-whisper`, `PySide6`, `sounddevice`, `onnxruntime`, `playwright`, and
others that are unrelated to Atlas Desktop startup.

## Startup Failure Modes Before UI Appears

| Failure mode | Current behavior | User-visible problem |
|---|---|---|
| No `Atlas.exe` and no Python | BAT prints install-Python message and pauses | User never reaches browser |
| No `py`, but `python` exists | BAT retries with `python` | Works only if PATH is correct |
| Neither `py` nor `python` works from hidden VBS | Hidden failure path | User may see nothing |
| Python version <3.10 | Startup check fails; support page can open only if server starts | If syntax incompatible, traceback before support |
| Import failure in `jarvis_desktop` or `builder_core` | `startup_checks` can mark dependencies failed if import reaches that far | If import fails before server starts, user sees terminal/hidden failure |
| Missing `jarvis_desktop/static` | Startup check fails and support page opens if server can start | Support page may also be missing if static dir absent |
| Missing demo directory | Startup check fails | First-use sample path broken |
| App-data directory unwritable | Phase 146B falls back to `%LOCALAPPDATA%` or temp | Resolved for many cases; still a diagnostic warning if fallback used |
| Port 8777 already in use | `ThreadingHTTPServer` raises before browser opens | Python traceback or silent failure under VBS |
| Default browser not configured | Server starts, `webbrowser.open` may do nothing | User sees no browser |
| Windows firewall/security policy blocks localhost | Server may start but browser cannot connect | Blank/error browser page |
| Antivirus blocks executable or scripts | App never starts | Common unsigned beta installer risk |
| Packaged app cannot find data files | Server may start but static/demo/knowledge missing | UI/support/demo broken |
| Packaged app cannot include Tcl/Tk | Browse folder fails | Recoverable with paste path, but degraded |
| PyYAML not bundled | Curated YAML knowledge silently skipped | Build/Investigation quality degrades after UI |
| User closes CMD window | Server process terminates | Browser stops working |

## External Assumptions

The current startup path assumes:

- The user is comfortable running a BAT or VBS file.
- Python is installed before Atlas.
- The `py` launcher or `python` is available.
- A console window is acceptable or hidden VBS is used.
- The user does not close the console that owns the server.
- The app directory contains all package folders and static assets.
- Port 8777 is available.
- The system has a default browser.
- Inno Setup is installed on the build machine to create `Atlas_Setup.exe`.
- A packaged `Atlas.exe` will eventually exist, but it does not exist now.

## Current Positive Findings

- `run_atlas.py` is the correct product entry point because it runs startup
  checks and opens support on failure.
- Phase 146B data-dir fallback now returns `startup.ready=true` without an env
  override on this machine:
  - resolved data dir: temp fallback
  - `data_dir_info.fallback=temp`
- `jarvis_desktop/tests/test_phase146b_true_beta_blockers.py` passed:
  - `8 passed in 0.81s`
- The default stdlib server has no required FastAPI/Uvicorn dependency.
- Support bundle generation is implemented inside `install_support.py` and can
  be preserved in a packaged build.

## Audit Conclusion

Atlas is one packaging step away from the desired launch model, not one UI step
away. The current code can be made consumer-style by replacing the Python/BAT
runtime dependency with a windowed packaged executable that:

1. embeds Python and the required packages/assets;
2. uses `run_atlas.py` or equivalent as the entry point;
3. starts the stdlib server without a console;
4. opens the browser automatically;
5. redirects to `support.html` on recoverable startup failures;
6. writes diagnostics/logs under the resolved Atlas data directory.

Until that packaged executable exists, the product remains dependent on Python
and cannot satisfy Phase 149's zero-friction installation goal.
