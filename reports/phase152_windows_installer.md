# Phase 152 — Windows Installer and Self-Contained Atlas.exe

Date: 2026-06-04

Scope: packaging only (PyInstaller one-folder + Inno Setup). No intelligence, billing, benchmarks, or landing changes.

## Summary

Atlas can be built as a windowed **`Atlas.exe`** (no console) and packaged as **`Atlas_Setup.exe`** for Windows beta users. Build succeeded on the development machine:

| Artifact | Path | Size (approx.) |
|---|---|---|
| Application folder | `dist/Atlas/` | ~30 MB |
| Main executable | `dist/Atlas/Atlas.exe` | ~2.9 MB |
| Windows installer | `packaging/installer/output/Atlas_Setup.exe` | ~11.2 MB |
| Legacy copy | `installer/output/Atlas_Setup.exe` | same |

## Build Commands

### One-time build dependencies (dev machine only)

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
py -3 -m pip install --target .phase152_packaging_lib pyinstaller PyYAML
```

Optional: Inno Setup 6 (`ISCC.exe`) on PATH or at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.

### PyInstaller (one-folder, windowed)

```powershell
.\packaging\pyinstaller\build_atlas_exe.ps1 -Clean
```

Wrapper: `.\build_atlas_exe.ps1 -Clean`

### Inno Setup installer

```powershell
.\packaging\installer\installer_build.ps1
```

Wrapper: `.\installer_build.ps1`

Skip re-packaging when `dist/Atlas` already exists:

```powershell
.\packaging\installer\installer_build.ps1 -SkipPackage
```

## Files Included in `dist/Atlas`

- `Atlas.exe` — windowed bootloader (`runw.exe`), entry `packaging/pyinstaller/atlas_entry.py`
- `_internal/` — Python runtime, `jarvis_desktop`, `builder_core`, Tcl/Tk
- Data bundles:
  - `jarvis_desktop/static/**` (includes `support.html`, `index.html`)
  - `jarvis_desktop/demo/**` (small/medium/large sample repos)
  - `jarvis_desktop/atlas_knowledge/**`
  - `docs/ATLAS_QUICKSTART.md`
  - `packaging/installer/build_info.json` (version, build date, commit)

## Files Excluded

- `external_repos/**`
- `benchmarks/**` results
- `reports/**` (except generated `build_info.json`)
- Monorepo `requirements.txt` runtime (voice, trading, playwright, etc.)
- `fastapi`, `uvicorn`, `pytest` (explicit PyInstaller excludes)
- `.git` directories (no repository metadata in bundle)

## Startup Behavior (packaged)

1. `atlas_entry.py` sets cwd to executable directory and installs a global excepthook (logs to `%LOCALAPPDATA%` / `~/.jarvis_desktop` via `data_paths`, no traceback dialog).
2. `run_atlas.py` runs `startup_checks()`; on failure opens `/support.html` without printing to a console.
3. Built-in `ThreadingHTTPServer` starts (no FastAPI required).
4. Default browser opens `http://127.0.0.1:8777/` (or Support on failure).
5. Writable app data via `jarvis_desktop.data_paths` (home → `%LOCALAPPDATA%\Atlas\desktop_data` → temp).

## Installer (Inno Setup)

`packaging/installer/Atlas.iss`:

- Install dir: `{autopf}\Atlas` with `PrivilegesRequired=lowest`
- Start Menu: **Atlas**, **Launch Atlas**, Uninstall
- Desktop shortcut (optional task, default on)
- Post-install: launch `Atlas.exe`
- Version metadata from `generated_version.iss` (product version, build date, commit hash)
- Uninstall removes common local data paths (optional cleanup)

## Validation Results

### Automated (this machine)

```text
8/8 test_phase152_packaging.py (after report + BOM fix)
PyInstaller build: PASS
Inno compile: PASS
dist/Atlas/Atlas.exe: PASS
support.html in bundle: PASS
small_repo demo in bundle: PASS
external_repos absent: PASS
```

### Manual / clean-machine

Full “no Python on PATH” validation requires a VM or secondary Windows profile. On the build host:

- PyInstaller output is self-contained (bundled `python313.dll`).
- Installer stages only `dist/Atlas` contents, not the dev tree.
- Recommended beta QA on a clean VM:
  1. Copy `Atlas_Setup.exe` only
  2. Install → double-click Atlas
  3. Confirm browser opens, Load Sample Repository, Build Plan, Support, Export diagnostics

## Versioning

| Source | Field |
|---|---|
| `jarvis_desktop/api.py` | `PRODUCT_VERSION` → Inno `MyAppVersion` |
| Build script | `build_info.json`: `build_date`, `commit` (git short hash) |
| Installer | `generated_version.iss` regenerated each build |

Current build recorded: see `packaging/installer/build_info.json`.

## Known Limitations

- **First build** requires Python + pip on the *build* machine only; end users do not need Python.
- **Antivirus** may flag new PyInstaller binaries until signed or allowlisted.
- **CDN scripts** (Three.js on Home) still load from unpkg when online — unchanged in this phase.
- **Code signing** not applied; SmartScreen may warn on first run.
- **Clean VM test** not executed in this pass — treat as pre-beta QA gate.
- Legacy root `atlas_desktop_entry.spec` / missing `atlas_desktop_entry.py` superseded by `packaging/pyinstaller/atlas.spec`.

## Next Packaging Risks

- Hidden import drift when new optional imports are added to `jarvis_desktop` / `builder_core`
- Tcl/Tk path issues on some Windows editions (folder picker)
- Large-repo scan memory inside bundled Python
- Installer upgrades (same `AppId`, semver rules)
- Authenticode signing for production release

## Layout Reference

```text
packaging/
  pyinstaller/
    atlas_entry.py
    atlas.spec
    build_atlas_exe.ps1
  installer/
    Atlas.iss
    generated_version.iss
    installer_build.ps1
    build_info.json
    staging/
    output/Atlas_Setup.exe
dist/Atlas/Atlas.exe
```
