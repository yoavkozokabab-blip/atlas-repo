# Atlas MCP — Real Client Test

Test the Atlas MCP server against actual AI coding clients.

## Detected on this machine (2026-06-16)
- ✅ **Claude Desktop** — config at `%APPDATA%\Claude\claude_desktop_config.json`.
- ✅ **Cursor** — installed.
- ⚠️ **Installed `Atlas.exe`** exists (`%LOCALAPPDATA%\Programs\Atlas\Atlas.exe`) but it's a
  **pre-session build without `--mcp`**. Until you rebuild + reinstall, use **source mode**
  for MCP (it has `--mcp` and is verified).

> Claude was **not** auto-wired into your clients — that edits your app config (which may hold
> other servers' tokens). Apply the configs below yourself.

---

## Recommended command (now): source mode
```
command: py
args:    ["-3", "run_atlas.py", "--mcp"]
cwd:     C:/J.A.R.V.I.S/local_atlas
```
After you rebuild + reinstall Atlas, switch to the installed app:
```
command: C:\Users\<you>\AppData\Local\Programs\Atlas\Atlas.exe
args:    ["--mcp"]
```
(then `cwd` is not needed).

## Claude Desktop
Edit `%APPDATA%\Claude\claude_desktop_config.json` — **merge** into existing `mcpServers`:
```json
{
  "mcpServers": {
    "atlas": {
      "command": "py",
      "args": ["-3", "run_atlas.py", "--mcp"],
      "cwd": "C:/J.A.R.V.I.S/local_atlas"
    }
  }
}
```
Fully quit and reopen Claude Desktop. Click the tools (hammer) icon → "atlas" should list
7 tools.

## Claude Code (CLI)
```bash
claude mcp add atlas -- py -3 run_atlas.py --mcp   # run from C:\J.A.R.V.I.S\local_atlas
```

## Cursor
`.cursor/mcp.json` in your workspace (or Settings → MCP → Add):
```json
{ "mcpServers": { "atlas": { "command": "py", "args": ["-3", "run_atlas.py", "--mcp"], "cwd": "C:/J.A.R.V.I.S/local_atlas" } } }
```

## Codex / generic stdio client
Same command/args as above.

---

## What to test (and what "pass" looks like)

| Step | How | Pass |
|---|---|---|
| Server boots | client connects, no "failed to start" | atlas appears in tools |
| `initialize` | automatic on connect | client shows atlas connected |
| `tools/list` | open the tools menu | 7 tools: scan_repo, get_codebase_map, build_context_pack, what_breaks, plan_change, find_file, repo_health |
| `atlas_scan_repo` | "Ask Atlas to scan C:\path\to\repo" | returns module/dependency counts |
| `atlas_build_context_pack` | "Ask Atlas what files matter for implementing Stripe checkout" | recommended files + reasons + confidence |
| `atlas_what_breaks` | "Ask Atlas what breaks if I change src/auth/session.ts" | impacted files + tests |

## Pre-verified (no client needed)
The protocol is already verified directly over stdio (initialize, notifications, tools/list,
tools/call scan/context-pack/what-breaks, error handling) and the 12-check smoke test passes —
see `reports/mcp_client_compatibility.md`. The real-client test confirms the *handshake +
spawn* inside Claude Desktop / Cursor specifically.

## If a client isn't installed
Skip its row and note it. Source-mode protocol verification (above) stands in for it; do not
claim a client passed if it wasn't actually run.

## Manual one-shot sanity check (no client)
```powershell
cd C:\J.A.R.V.I.S\local_atlas
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' | py -3 run_atlas.py --mcp
# expect one line: {"jsonrpc":"2.0","id":1,"result":{..."serverInfo":{"name":"atlas-local","version":"1.0.0"}}}
```
