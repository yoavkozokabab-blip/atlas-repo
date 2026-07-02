# TASK 5 — MCP Proof Script / Checklist

**Date:** 2026-06-20. New script `scripts/mcp_install_proof.py` (does not duplicate `scripts/mcp_smoke_test.py`, which tests the *source* module — this tests the **frozen `Atlas.exe`**).

## Automated proof — `scripts/mcp_install_proof.py`
```
py -3 scripts/mcp_install_proof.py [path\to\Atlas.exe] [path\to\repo]
# default: dist/Atlas/Atlas.exe + external_repos/requests; saves reports/pre_beta_fix/mcp_proof/result.json
```
Verifies, in order: Atlas.exe exists → `--self-test` exit 0 → spawn `Atlas.exe --mcp` over stdio → `initialize` (serverInfo) → `tools/list` → `atlas_health` → `atlas_scan_repo` (demo) → `atlas_repo_summary`.

## Result (run this pass against `dist/Atlas/Atlas.exe`) — **PASSED**
```
[PASS] Atlas.exe exists
[PASS] Atlas.exe --self-test exit 0 (ready)
[PASS] initialize returns serverInfo — atlas-local
[PASS] tools/list returns Atlas tools — 17 tools
[PASS] atlas_health works (no error, no secret leak)
[PASS] atlas_scan_repo works on demo repo — files=125
[PASS] atlas_repo_summary works — name=requests
INSTALL-MCP PROOF PASSED
```
**Significance:** this clears the long-standing unverified risk — the **packaged windowed exe's `--mcp` stdout-rebind works against a real JSON-RPC-over-pipes client.** (Note: the shipped exe exposes 17 tools — it was built before `atlas_root_cause` was added to source; functionally complete. A rebuild would include the 18th.)

## What this does NOT prove
The **real Claude Desktop UI** handshake (Claude spawning the exe and showing tools). The transport + protocol on the frozen binary are now proven; the last mile is the client UI. Yoav runs the manual checklist below.

## Manual checklist (Yoav, after installing the latest Atlas)
1. `Atlas.exe --self-test` → "READY".
2. `py -3 scripts/mcp_install_proof.py "C:\Program Files\Atlas\Atlas.exe"` → INSTALL-MCP PROOF PASSED.
3. `claude_desktop_config.json` contains the `atlas` server (`Atlas.exe --mcp`) — per `docs/MCP_CLIENT_SETUP.md`.
4. Restart Claude Desktop → **atlas** appears in the tools (hammer) menu.
5. In Claude: ask *"What Atlas tools are available?"* and *"Use atlas_health."* → tools listed + health returns.
6. Ask *"Use atlas_scan_repo on C:\path\to\a\repo, then atlas_repo_summary."* → summary returned.
7. Evidence saved under `reports/pre_beta_fix/mcp_proof/` (the script writes `result.json`; add screenshots of the Claude tool calls).
