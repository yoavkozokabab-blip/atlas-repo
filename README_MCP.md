# Atlas MCP Server

Give your AI coding agent (Claude Code, Claude Desktop, Cursor, Codex) direct access to
Atlas's repository intelligence. Ask, mid-task:

> "Ask Atlas what files matter for implementing Stripe checkout."
> "Ask Atlas what breaks if I change `sessions.py`."

The server is **local-first** (nothing leaves your machine), **read-only** (it never
writes to your repo), and has **no third-party dependencies** — it runs on the Python
already shipped with Atlas.

## Tools

| Tool | What it does |
|---|---|
| `atlas_scan_repo` | Scan/rescan a repo; returns module & dependency counts and risk summary. |
| `atlas_repo_summary` | Compact summary: language, graph health, entry points, hubs, risks, subsystems. |
| `atlas_get_codebase_map` | Modules, subsystems, dependency hubs, risk hotspots, entry files. |
| `atlas_get_architecture` | Architectural overview and layering. |
| `atlas_get_dependency_graph` | Resolved import/dependency edges. |
| `atlas_build_context_pack` | **The headline tool.** Given a task: the exact files to read + reasons + confidence + a paste-ready context pack. |
| `atlas_find_relevant_files` | Rank task-relevant files from graph, memory, subsystems, tests, and symbol evidence. |
| `atlas_find_file` | Rank files by a free-text query, with reasons + confidence. |
| `atlas_what_breaks` / `atlas_get_impact_analysis` | Given changed files: impacted importers, risk, and tests to run. |
| `atlas_plan_change` / `atlas_get_change_plan` | Files to inspect, ordered steps, risks, validation plan. |
| `atlas_root_cause` | Given an exception/stack trace/failing test: probable root-cause symbols, evidence, investigation order. |
| `atlas_repo_health` | Scan quality, unresolved imports, stale/degraded warnings, risk score. |
| `atlas_export_for_claude` / `_cursor` / `_codex` | Export a context pack formatted for each agent. |
| `atlas_health` | MCP runtime, repository, trust, memory, and Claude Desktop config health. |

**18 tools total.**

Every tool takes an absolute `repo_path`. Tools auto-scan on first use, so you don't have
to call `atlas_scan_repo` first (they report `scanned_now` so you know if a scan happened).

## Run it

**Installed Atlas (beta users):**

```bat
"C:\Program Files\Atlas\Atlas.exe" --mcp
```

**Source mode (developers, Python 3.10+):**

```bash
py -3 run_atlas.py --mcp
# equivalent low-level entry:
py -m atlas_desktop.mcp_server
```

It speaks newline-delimited JSON-RPC over stdio — that's how MCP clients launch it.
Logs go to `<Atlas data dir>/mcp_server.log` (no telemetry). stdout carries the
protocol, so it must stay clean — never run other Atlas commands on the same stream.

> Status: **experimental for the installed app.** The stdio entry works in source
> mode (verified). Launching it from the windowed `Atlas.exe` rebinds stdio from the
> client's pipes; this path is implemented but not yet verified against every client.
> See `docs/MCP_CLIENT_SETUP.md` and `reports/mcp_final_beta_readiness.md`.

## Smoke test

```bash
py scripts/mcp_smoke_test.py
# or against your own repo:
py scripts/mcp_smoke_test.py C:\path\to\your\repo
```

## Connect Claude Desktop

Edit `claude_desktop_config.json`
(Windows: `%APPDATA%\Claude\claude_desktop_config.json`,
macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "atlas": {
      "command": "py",
      "args": ["-m", "atlas_desktop.mcp_server"],
      "cwd": "C:/path/to/Atlas"
    }
  }
}
```

On macOS/Linux use `"command": "python3"`. Set `cwd` to your Atlas install directory.
Restart Claude Desktop; "atlas" appears in the tools (hammer) menu.

A ready-to-copy file is in `docs/examples/claude_desktop_config.json`.

## Connect Claude Code (CLI)

```bash
claude mcp add atlas -- py -m atlas_desktop.mcp_server
```

Run that from your Atlas directory (so `cwd` is correct), or add a project `.mcp.json`:

```json
{
  "mcpServers": {
    "atlas": { "command": "py", "args": ["-m", "atlas_desktop.mcp_server"], "cwd": "C:/path/to/Atlas" }
  }
}
```

## Connect Cursor

Cursor → Settings → MCP → Add new server, or add `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "atlas": { "command": "py", "args": ["-m", "atlas_desktop.mcp_server"], "cwd": "C:/path/to/Atlas" }
  }
}
```

## Connect Codex / other MCP clients

Any MCP client that launches a stdio server works. Point it at:
`command = py`, `args = ["-m", "atlas_desktop.mcp_server"]`, `cwd =` your Atlas directory.

## Example session

```
You:    Ask Atlas which files matter for adding rate limiting to the API.
Agent:  (calls atlas_build_context_pack { repo_path, task: "add rate limiting to the API" })
Atlas:  recommended_files: middleware/throttle.py, api/router.py, config.py ...
        confidence: MEDIUM, compact_context: <paste-ready markdown>
You:    What breaks if I change middleware/throttle.py?
Agent:  (calls atlas_what_breaks { repo_path, changed_files: ["middleware/throttle.py"] })
Atlas:  impacted_files: api/router.py, app.py ... tests_to_run: tests/test_throttle.py
```

## Safety

- No network calls in any tool. No secrets are ever returned (`atlas_repo_health`
  whitelists only version/build/repo fields).
- No tool executes your input or writes to your repo. Scanning only reads source files.
- Invalid paths and unscanned repos return structured errors with a `hint`.
