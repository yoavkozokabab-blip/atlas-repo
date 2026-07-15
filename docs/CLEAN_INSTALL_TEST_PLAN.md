# Atlas — Clean Install Test Plan

> **This test has NOT been performed by Claude.** It modifies a real machine (Program Files,
> Start Menu, registry) and needs a clean Windows 10/11 environment (ideally a fresh VM or a
> spare machine). Run it once before release and record PASS/FAIL per step.

## Prerequisites
- A clean Windows 10/11 machine or VM (no prior Atlas install).
- The verified installer published to GitHub Releases.
  Current launch asset: `Atlas_Setup.exe`, SHA256
  `AD1687D5585EE36ABC3F8AE6802E046D1661DF2950982E58B18351C91B2FF82F`.
- The website live on Vercel with `ATLAS_INSTALLER_URL` set.

## Steps (mark PASS / FAIL / NOTE)

| # | Step | Expected | Result |
|---|---|---|---|
| 1 | On the VM, open the Vercel site → `/download` → create a free account | account created; redirected back to download | |
| 2 | Click **Download for Windows** | browser downloads `Atlas_Setup.exe` (302 → GitHub asset) | |
| 3 | Verify checksum: `Get-FileHash Atlas_Setup.exe -Algorithm SHA256` | matches the published `.sha256` | |
| 4 | Run `Atlas_Setup.exe` | SmartScreen warns (unsigned) → **More info → Run anyway**; installer opens; **no admin/UAC prompt** (per-user install) | |
| 5 | Complete install (accept defaults; allow desktop icon) | installs to `%LOCALAPPDATA%\Programs\Atlas` (or `{autopf}\Atlas`); Start Menu **Atlas** + **Uninstall Atlas** created | |
| 6 | Launch from Start Menu (or the post-install checkbox) | browser opens to the Atlas UI on a verified local runtime port; if `8777` is occupied, Atlas selects a safe fallback such as `8778`; no error page | |
| 7 | (If desktop auth exists) create account / sign in | succeeds or fails with a clear message (no raw traceback) | |
| 8 | Select a repository and **Scan** | codebase map renders (modules, dependencies) | |
| 9 | Describe a task → **Generate context pack** | returns recommended files + reasons + confidence; **Copy for Claude/Cursor/Codex** works | |
| 10 | **What breaks** for a file | shows impacted files + tests to run | |
| 11 | MCP: wire Claude Desktop to `Atlas.exe --mcp` (see `docs/MCP_REAL_CLIENT_TEST.md`) | tools list shows `atlas_*`; one `tools/call` returns data | |
| 12 | Add/Remove Programs | shows **Atlas 1.0.0** | |
| 13 | Uninstall via Start Menu **Uninstall Atlas** (or Apps & features) | uninstalls cleanly, no errors | |
| 14 | After uninstall, check leftovers | App files and Start Menu/desktop shortcuts are removed. Repository memory in `%USERPROFILE%\.atlas_desktop` is user data and must not be deleted accidentally unless the uninstaller explicitly offers and confirms a data wipe. | |

## Pass criteria for release
- Steps 1–10, 12–14 PASS.
- Step 11 (MCP) must be green for the public launch build.
- If step 14 deletes user repository memory without explicit confirmation, the uninstall behavior is unsafe → rebuild.

## Record results in
`reports/atlas_install_verification.md` (replace the NOT_VERIFIED checklist section with
actual PASS/FAIL once run).
