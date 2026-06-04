# Phase 143 — One-Click Installer & Support

**Date:** 2026-06-02  
**Goal:** A non-technical developer launches Atlas without reading setup docs or using a terminal.

## Success criteria

| Criterion | Status |
|-----------|--------|
| Double-click **Launch Atlas** (no terminal commands) | ✅ `Launch Atlas.bat` / `Launch Atlas.vbs` / `Atlas.bat` |
| Startup verifies Python, modules, directories | ✅ `install_support.startup_checks()` |
| Friendly diagnostics (version, scan health, environment) | ✅ `support.html` + `GET /api/system/startup-status` |
| Recovery: rebuild, clear cache, reset onboarding, export diagnostics | ✅ API + Support UI buttons |
| One-click `atlas_support_bundle.zip` (no source code) | ✅ `POST /api/system/support-bundle` |

## How to launch (beta user)

### Windows (recommended)

1. Install from **`Atlas_Setup.exe`** (build with `.\installer_build.ps1`), **or** unzip the repo folder.
2. Double-click **`Launch Atlas.bat`** (or **`Launch Atlas.vbs`** for no console window).
3. Browser opens Atlas at `http://127.0.0.1:8777/`.
4. If startup checks fail, Atlas opens **`support.html`** automatically with fix actions.

### Requirements

- **Python 3.10+** with the Windows `py` launcher (install from [python.org](https://www.python.org/downloads/) — check “Add to PATH”).
- No API keys for core scanning.

## Launcher files

| File | Purpose |
|------|---------|
| `Launch Atlas.bat` | Primary one-click launcher |
| `Launch Atlas.vbs` | Silent launcher (no console) |
| `Atlas.bat` | Alias to Launch Atlas |
| `run_atlas.py` | Python entry with preflight + support redirect |
| `run_jarvis_desktop.py` | Legacy entry (still works) |

**Note:** `Atlas.exe` is optional. The installer shortcut targets **`Launch Atlas.bat`**. Ship `Launch Atlas.vbs` for a cleaner double-click experience. A packaged `.exe` can be added later via PyInstaller in `installer_build.ps1`.

## Support page

**URL:** `http://127.0.0.1:8777/support.html` (also linked from the app top bar)

Shows:

- **Environment checks** — Python, Atlas modules, writable data dir, optional FastAPI
- **Atlas version** — `PRODUCT_VERSION` (`phase143-one-click-installer`)
- **Scan health** — modules, edges, graph quality (when a repo is loaded)

**Recovery actions:**

| Button | Action |
|--------|--------|
| Rebuild index | Clears in-memory index + scan cache; rescans last repo or demo |
| Clear cache | Clears `scan_cache` only |
| Reset onboarding | Clears welcome/onboarding localStorage keys |
| Export diagnostics | Copies JSON to clipboard |
| Download support bundle | `atlas_support_bundle_YYYYMMDD_HHMMSS.zip` |

## Support bundle contents (no source code)

- `manifest.json`
- `version.txt`
- `diagnostics.json`
- `environment.json`
- `scan_metadata.json`
- `startup_checks.json`
- `logs/*` — tail of `launcher.log`, `analytics.jsonl`, optional diag log

## API routes (Phase 143)

| Method | Path |
|--------|------|
| GET | `/api/system/startup-status` |
| POST | `/api/system/clear-cache` |
| POST | `/api/system/rebuild-index` |
| POST | `/api/system/support-bundle` |

## Build Windows installer

```powershell
cd local_jarvis
.\installer_build.ps1
```

Output: `installer/output/Atlas_Setup.exe`

Creates Start Menu / Desktop shortcut **Launch Atlas**.

## Readiness score: **8.5 / 10**

**Remaining friction:**

- Python must still be installed once on Windows (not bundled in Phase 143).
- Port 8777 conflicts if another Atlas instance is running.
- Three.js CDN for graph (offline bundle still recommended).

## Tests

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase143_installer_and_support.py -q
```
