# Atlas — Install Verification (Phase 5 / P3)

**Date:** 2026-06-16
**Installer:** `installer/output/Atlas_Setup.exe` — 44,026,121 bytes, built 2026-06-15 20:47
**SHA256:** `b98ca5e5edbdd2aa6a64930211ce867dcb442e0cf1f5a994dabd756491d6cbc6`
**Method:** static audit of `installer/jarvis.iss` + build specs + app self-test. **A real
clean-machine install was NOT performed** (it modifies the host: Program Files, Start Menu,
registry). Items needing a clean machine are marked `NOT_VERIFIED` with runnable steps.

> ⚠️ The SHA256 above is for the **06-15** build, whose exe metadata still reads `1.0.0`
> (the version fix in `jarvis.iss`/`product_info.py` is `0.1.0-beta` but needs a **rebuild**
> to take effect). Re-generate the hash after the next build. See P6 release process.

## Summary

| Area | Status | Notes |
|---|---|---|
| Version consistency (source) | **PASS** | `product_info.py`, `jarvis.iss`, `build_info.json` all `0.1.0-beta` |
| Installer artifact exists + hashed | **PASS** | 44 MB, SHA256 recorded |
| Retrieval + MCP code in build | **PASS** | specs use `collect_submodules("jarvis_desktop")` → freezes `context_pack`, `mcp_server` |
| Accounts service bundled | **PASS** | `dist/Atlas/accounts/AtlasAccounts.exe` present |
| Start Menu shortcut | **PASS** | `[Icons] {group}\Atlas` |
| Uninstall shortcut + entry | **PASS** | `{group}\Uninstall Atlas`, `UninstallDisplayIcon` set |
| Desktop shortcut (opt-in) | **PASS** | `[Tasks] desktopicon` (checkedonce) |
| Post-install launch | **PASS** | `[Run] ... Launch Atlas` (skipifsilent) |
| No-admin install (low friction) | **PASS** | `PrivilegesRequired=lowest` → per-user, no UAC |
| App self-test | **PASS** | `run_atlas.py --self-test` → READY (launcher, dirs, shortcuts, browser) |
| Uninstall data cleanup | **FIXED (rebuild pending)** | path bug corrected in `jarvis.iss`; see below |
| Inno staging freshness | **WARN** | `staging/` (what Inno bundles) is stale 06-04; release flow fragile |
| Publisher URL | **WARN** | `MyAppURL=https://github.com/atlas` is a placeholder/dead link |
| Code signing | **WARN** | installer unsigned → SmartScreen warning (needs cert — user external blocker) |
| Live install→launch→scan→MCP→uninstall | **NOT_VERIFIED** | requires clean machine; steps below |

## FIXED this session

**Uninstall left user data behind (FAIL → fixed).** `[UninstallDelete]` removed
`{userappdata}\.jarvis_desktop` = `%APPDATA%\Roaming\.jarvis_desktop`, but the app's real
data dir (per `jarvis_desktop/data_paths.py`) is `%USERPROFILE%\.jarvis_desktop` (fallback
`%LOCALAPPDATA%\Atlas\desktop_data`). The paths never matched, so uninstall orphaned user
data. Corrected to remove `{%USERPROFILE}\.jarvis_desktop` and `{localappdata}\Atlas`.
**Takes effect on the next installer rebuild.**

## WARN detail

- **Staging staleness / split release flow.** `build_atlas_exe.ps1` produces `dist/Atlas`
  but does **not** populate `staging/` or run Inno; `installer/jarvis.iss` bundles
  `..\staging\*`, and on-disk `staging/Atlas.exe` is **2026-06-04** (stale) while `dist` is
  06-15. A naive Inno rebuild would ship a June-4 build. The release process must refresh
  `staging` from `dist` every time — addressed in `docs/RELEASE_PROCESS.md` (P6).
- **Publisher URL placeholder** shows a dead link in Add/Remove Programs. Set to the real
  site (`https://useatlas.dev`) before public beta.
- **Unsigned installer** triggers SmartScreen "unknown publisher." Known external blocker
  (needs a code-signing certificate). Acceptable for *invited* private beta with a heads-up;
  not for public download.

## NOT_VERIFIED — clean-machine checklist (run on a fresh Windows 10/11 VM)

Run each and mark PASS/FAIL:

1. Install `Atlas_Setup.exe` (no admin prompt expected).
2. Start Menu → Atlas launches; browser opens to the app at `127.0.0.1:8777`.
3. Create an account / sign in (if desktop auth is exercised).
4. Select a repo and **scan**; codebase map renders.
5. **Context pack** generation for a task returns files + reasons.
6. **MCP**: configure Claude Desktop with `Atlas.exe --mcp`; confirm tools list (see P4).
7. Add/Remove Programs shows **Atlas 0.1.0-beta**; uninstall runs clean.
8. After uninstall, confirm `%USERPROFILE%\.jarvis_desktop` and `%LOCALAPPDATA%\Atlas` are
   removed (validates the cleanup fix).

## Verdict

**INSTALLER_CONDITIONAL_GO** — packaging is correct and the artifact is current/ hashed, but
two things must happen before shipping the download: (1) **rebuild** so the version + uninstall
fixes are in the binary and regenerate the SHA256; (2) complete the clean-machine checklist
above. Code signing remains a separate WARN for *public* (vs invited) distribution.
