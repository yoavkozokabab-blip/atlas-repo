# CLEAN-MACHINE INSTALL VALIDATION (Phase 186C)

**Date:** 2026-06-20 · **Execution status: BLOCKED.** A true clean-machine run requires a fresh Windows VM with **no Python, no Node, no repo, no dev state**, plus real Claude Desktop / Cursor / Codex installs and screen capture. This audit environment **is** the dev box — it cannot be that clean machine. I will not present dev-box results as clean-machine evidence.

## What IS verified here (the packaged artifact, not a clean machine)

| Check | Result | Evidence |
|---|---|---|
| Installer exists, current | **PASS** | `packaging/installer/output/Atlas_Setup.exe` (44 MB) + `.sha256`; `build_info.json` build `2026-06-18`, commit `ce5f73805`, `0.1.0-beta`. |
| Packaged binary boots & self-tests | **PASS** | Ran `dist/Atlas/Atlas.exe --self-test` → report `self_test.json`: `ready:true, frozen:true`; checks **executable / directories / shortcuts / browser** all ok; zero critical failures/warnings. (`frozen:true` = the PyInstaller binary, not source.) |
| MCP runtime (in-process) | **PASS** | `scripts/mcp_smoke_test.py` → 12/12 (initialize, tools/list, scan, context pack, find_file, what_breaks, repo_health, no-secret-leak). |
| Installer is **signed** | **FAIL** | `Atlas.iss` has no `SignTool` → SmartScreen "unknown publisher" on a clean machine. |
| Real client (Claude/Cursor/Codex) handshake from installed exe | **BLOCKED** | Smoke test is in-process; no real stdio handshake from `Atlas.exe --mcp` was run. |

## REQUIRED clean-machine test procedure (owner must run, capture to `screenshots/`, `videos/`, `logs/`)

### A. Environment
1. Fresh Windows 11 VM (snapshot it). Confirm `python`/`node` absent.

### B. Install (Tasks §2–3)
2. Download `Atlas_Setup.exe`; **record SmartScreen behavior** (expected: warning, since unsigned).
3. Install (lowest-privilege). Verify Start-menu + desktop shortcuts, app launches.
4. In-app, verify each: **startup**, **repository scan**, **context generation**, **export**, **login** (per 186A — currently local accounts), **billing status** (per 186B — currently stub), **settings**.

### C. Claude Desktop (Tasks §4)
5. Install consumer Claude Desktop. Add Atlas to `claude_desktop_config.json` per `docs/MCP_CLIENT_SETUP.md` (target `Atlas.exe --mcp`).
6. Verify: tools **visible**, tools **callable**, repository analysis returns results. Capture.

### D. Cursor (Tasks §5)
7. Configure Atlas MCP in Cursor. Verify integration, `atlas_export_for_cursor`, a task workflow. Capture.

### E. Codex (Tasks §6)
8. Configure Atlas MCP in Codex. Verify `atlas_export_for_codex`, a task workflow. Capture.

### F. Failure testing (Tasks §7)
9. **Corrupt MCP config** → expect a clear error, not a crash; Atlas itself still runs.
10. **Kill network** → scan/export still work (local); auth/billing degrade gracefully with the support message (`accounts_routes.py:130`).
11. **Corrupt/expire auth token** → expect re-login prompt, no crash.

## PASS / FAIL / BLOCKED

| Task | Status |
|---|---|
| Clean environment | **BLOCKED** (no VM here) |
| Install `Atlas_Setup.exe` on clean machine | **BLOCKED** |
| Verify startup/scan/context/export/login/billing/settings on clean machine | **BLOCKED** (packaged self-test PASS on dev box only) |
| Claude Desktop connect + tools callable | **BLOCKED** |
| Cursor integration | **BLOCKED** |
| Codex integration | **BLOCKED** |
| Failure/recovery testing | **BLOCKED** |
| Packaged binary self-test | **PASS** (dev box) |
| Installer signed | **FAIL** (unsigned → SmartScreen) |

**Verdict:** the packaged product *boots and self-tests clean*, but **"works from the installer on a clean machine, connected to a real agent" is UNPROVEN.** This remains a launch blocker until the procedure above is run and captured.
