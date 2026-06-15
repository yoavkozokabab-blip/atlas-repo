# Atlas Installer — Rebuild Report (Ops Phase / Step 5)

**Date:** 2026-06-16
**Result: ⛔ REBUILD BLOCKED — Inno Setup not installed.** Not attempted (no faking).

## Tool check

| Tool | Status |
|---|---|
| Inno Setup compiler (`ISCC.exe`) | **MISSING** — not on PATH, not in `C:\Program Files\Inno Setup 6\` or `…(x86)…` |
| PyInstaller build deps (`.phase152_packaging_lib`) | ✅ present |
| Canonical build script (`packaging/installer/installer_build.ps1`) | ✅ present and verified |
| `git rev-parse HEAD` | `f5b6ce922` |

`installer_build.ps1` runs PyInstaller (would succeed) **and then** compiles `Atlas.iss` with
ISCC (would fail). So the full build cannot complete here.

## ⚠️ Important: the current installer is STALE relative to this session's fixes

| | Value |
|---|---|
| Current artifact | `packaging/installer/output/Atlas_Setup.exe` |
| Built | 2026-06-15 20:47, **commit `2846b2d57`** |
| Size | 44,026,121 bytes |
| SHA256 | `b98ca5e5edbdd2aa6a64930211ce867dcb442e0cf1f5a994dabd756491d6cbc6` |

That build **predates** every fix from this session (HEAD is now `f5b6ce922`). It does **not**
include:
- `run_atlas.py --mcp` launch mode (MCP from the installed app),
- MCP `serverInfo.version` = `0.1.0-beta`, `atlas_what_breaks` `changed_files` alias,
- the **uninstall cleanup fix** in `packaging/installer/Atlas.iss`.

**A rebuild is mandatory before shipping** so these land in the binary. Do not publish the
06-15 installer as the beta build.

## Exact instructions to enable + run the rebuild (for Yoav)

### 1. Install Inno Setup 6 (one-time, free)
- Download from **https://jrsoftware.org/isdl.php** (Inno Setup 6, stable).
- Run the installer, accept defaults. It installs `ISCC.exe` to
  `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.
- (Optional) add that folder to PATH so `ISCC` is callable directly.

### 2. Rebuild (single command, ~6–8 min)
```powershell
cd C:\J.A.R.V.I.S\local_jarvis
.\packaging\installer\installer_build.ps1
```
This regenerates the version defines from `product_info.py` (`0.1.0-beta`), runs the
PyInstaller build (freezes today's `run_atlas.py`, `mcp_server`, `context_pack`), refreshes
`packaging\installer\staging\`, and compiles `Atlas.iss` →
`packaging\installer\output\Atlas_Setup.exe`.

> If `installer_build.ps1` can't find `ISCC.exe`, either add Inno Setup to PATH or edit the
> compile step to point at the full `ISCC.exe` path.

### 3. Post-build verification (expected values)
```powershell
$exe = "packaging\installer\output\Atlas_Setup.exe"
(Get-Item $exe).Length                                   # ~44 MB (44,000,000+ bytes)
(Get-FileHash $exe -Algorithm SHA256).Hash               # NEW hash — record it
(Get-Content packaging\installer\generated_version.iss)  # MyAppVersion "0.1.0-beta", commit = current HEAD
.\packaging\pyinstaller\ ; py -3 run_atlas.py --self-test # READY
py scripts\mcp_smoke_test.py                              # 12/12 green
```
Confirm:
- **Version** = `0.1.0-beta`, commit = current HEAD (not `2846b2d57`).
- **Bundles latest code** — `dist\Atlas\Atlas.exe` rebuilt this run; `accounts\AtlasAccounts.exe` present.
- **Uninstall fix included** — `Atlas.iss` `[UninstallDelete]` targets `{%USERPROFILE}\.jarvis_desktop`.
- **Size** sane (~42–45 MB).
- Regenerate `Atlas_Setup.exe.sha256` (see `docs/RELEASE_PROCESS.md` step 3).

## Verdict: **INSTALLER_REBUILD_REQUIRED (blocked on Inno Setup install — human step)**

No code blockers; the source is ready. Install Inno Setup, run one command, re-verify, then
proceed to the GitHub Release (`docs/GITHUB_RELEASE_CLICK_BY_CLICK.md`).
