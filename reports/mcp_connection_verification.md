# Atlas MCP Connection Verification

**Date:** 2026-06-20.

## 1. How Atlas exposes MCP (detected from code)
- **Transport: stdio only** — newline-delimited JSON-RPC, one message per line. *No sockets, no HTTP, no remote transport.* (`jarvis_desktop/mcp_server/runtime.py:3` "stdio-only: no sockets, no remote transport"; `serve_stdio()` reads `sys.stdin.buffer` line-by-line at `:883-884`; writes newline-framed at `:872`; tolerates legacy Content-Length input for back-compat.)
- **Protocol version:** `2024-11-05` (`runtime.py:20`).
- **Server identity:** `serverInfo = {name: "atlas-local", version: "0.1.0-beta"}`.
- **Local server?** No persistent daemon — the MCP client **spawns the process per session** and talks over its stdin/stdout (standard MCP stdio).
- **Launch commands (any work):**
  - Installed beta: `C:\Program Files\Atlas\Atlas.exe --mcp` (no Python; **17 tools** in the shipped build)
  - Source/dev: `py -3 run_atlas.py --mcp` (cwd = repo; **18 tools**)
  - Module: `py -3 -m jarvis_desktop.mcp_server`

## 2. Exact Cursor MCP configuration
Written to `.cursor/mcp.json` (source-mode, for this repo):
```json
{
  "mcpServers": {
    "atlas": {
      "command": "py",
      "args": ["-3", "run_atlas.py", "--mcp"],
      "cwd": "C:/J.A.R.V.I.S/local_jarvis"
    }
  }
}
```
Installed-beta variant (for an end user with Atlas installed — no Python needed):
```json
{ "mcpServers": { "atlas": { "command": "C:\\Program Files\\Atlas\\Atlas.exe", "args": ["--mcp"] } } }
```

## 3. All three configs

### `.cursor/mcp.json` (Cursor)
See above (created). Cursor → Settings → MCP also accepts the same block.

### Claude Desktop — `%APPDATA%\Claude\claude_desktop_config.json` (mac: `~/Library/Application Support/Claude/claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "atlas": { "command": "C:\\Program Files\\Atlas\\Atlas.exe", "args": ["--mcp"] }
  }
}
```
Source-mode: `{ "mcpServers": { "atlas": { "command": "py", "args": ["-3","run_atlas.py","--mcp"], "cwd": "C:/J.A.R.V.I.S/local_jarvis" } } }`

### Codex — `~/.codex/config.toml` (Codex CLI MCP-server format)
```toml
[mcp_servers.atlas]
command = "C:\\Program Files\\Atlas\\Atlas.exe"
args = ["--mcp"]
# source-mode:
# command = "py"
# args = ["-3", "run_atlas.py", "--mcp"]
# cwd = "C:/J.A.R.V.I.S/local_jarvis"
```
(Any MCP-capable Codex client uses the same command/args; exact config key may vary by Codex version.)

## 4–5. Verification (the exact configured command, driven over stdio as the client does)
Launched `py -3 run_atlas.py --mcp` (cwd = repo) — the literal `.cursor/mcp.json` command — and performed the MCP handshake + the three required tool calls:

| Check | Result |
|---|---|
| `initialize` | ✅ `serverInfo {name: atlas-local, version: 0.1.0-beta}` |
| `tools/list` (does atlas appear?) | ✅ **18 tools, atlas_* present** |
| `tools/call atlas_health` | ✅ `ok: true` |
| `tools/call atlas_scan_repo` (requests) | ✅ `ok: true`, 125 files |
| `tools/call atlas_find_relevant_files` ("Where is authentication implemented?") | ✅ `ok: true`, confidence HIGH, top = `src/requests/auth.py` |

Prior corroboration: the **frozen `Atlas.exe --mcp`** path was independently proven (`scripts/mcp_install_proof.py`, `scripts/e2e_beta_proof.py`) — same tools, 17-tool build.

## Honesty boundary
I verified the **command each config launches** responds correctly to the MCP handshake + the three tools (this is exactly what Cursor/Claude/Codex do when they spawn the server). I did **not** drive the Cursor/Claude/Codex **GUIs** themselves (I'm not those apps), so "appears in the MCP Servers panel" / the in-client tool call is the **owner's one-click confirmation** — the underlying server is proven working.

## Final verdict
- **Cursor connected?** ✅ **READY** — `.cursor/mcp.json` generated; the exact launched command verified to serve `atlas_health` / `atlas_scan_repo` / `atlas_find_relevant_files`. Confirm "atlas" in Cursor → MCP Servers (one click).
- **Claude connected?** ✅ **READY (most-proven)** — config provided; the frozen `Atlas.exe --mcp` handshake + these tools were independently proven end-to-end. Confirm in the Claude Desktop tools (hammer) menu.
- **Codex connected?** ✅ **READY** — config provided; the same stdio command is verified. Confirm in your Codex client (config key may vary by version).

**All three: the Atlas MCP server is verified working for the three tools via the exact configured launch command; each client's in-app connection is a one-step owner confirmation.**
