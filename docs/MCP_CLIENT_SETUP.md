# Atlas MCP — Client Setup

Connect Claude Desktop, Claude Code, Cursor, or Codex to the local Atlas MCP server so
your AI agent can query repository intelligence mid-task.

The server is **local-first** (nothing leaves your machine), **read-only** (never writes
to your repo), and speaks **newline-delimited JSON-RPC over stdio** — the standard MCP
stdio transport.

---

## 1. Pick your launch command

| You have… | `command` | `args` |
|---|---|---|
| Installed Atlas | `C:\Program Files\Atlas\Atlas.exe` | `["--mcp"]` |
| Source checkout (Win) | `py` | `["-3", "run_atlas.py", "--mcp"]` |
| Source checkout (mac/Linux) | `python3` | `["run_atlas.py", "--mcp"]` |

For source mode, set `cwd` to your Atlas directory so imports resolve. For the installed
app, `cwd` is not required.

> **Experimental note (installed app):** `Atlas.exe` is a windowed build, so `--mcp`
> rebinds stdio from the pipes the MCP client opens. This is implemented but not yet
> verified against every client. If the installed-app path misbehaves, use source mode,
> which is verified (12/12 smoke test + live `initialize`/`tools/list`/`tools/call`).

---

## 2. Claude Desktop

Edit `claude_desktop_config.json`
(Windows `%APPDATA%\Claude\claude_desktop_config.json`,
macOS `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "atlas": {
      "command": "C:\\Program Files\\Atlas\\Atlas.exe",
      "args": ["--mcp"]
    }
  }
}
```

Source-mode equivalent:

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

Restart Claude Desktop. "atlas" appears in the tools (hammer) menu.

## 3. Claude Code (CLI)

```bash
claude mcp add atlas -- py -3 run_atlas.py --mcp     # run from your Atlas dir
```

or a project `.mcp.json`:

```json
{ "mcpServers": { "atlas": { "command": "py", "args": ["-3", "run_atlas.py", "--mcp"], "cwd": "C:/J.A.R.V.I.S/local_atlas" } } }
```

## 4. Cursor

Cursor → Settings → MCP → Add new server, or `.cursor/mcp.json`:

```json
{ "mcpServers": { "atlas": { "command": "py", "args": ["-3", "run_atlas.py", "--mcp"], "cwd": "C:/J.A.R.V.I.S/local_atlas" } } }
```

## 5. Codex / any other MCP client

Any client that launches a stdio MCP server works. Use the command/args from the table in
step 1.

---

## 6. Verify it works

Before wiring a client, confirm the server runs:

```bash
py scripts/mcp_smoke_test.py                 # bundled repo (fast)
py scripts/mcp_smoke_test.py C:\path\to\repo # your repo
```

Expected tail: `SMOKE TEST PASSED: all checks green`.

## 7. Example prompts

```
Ask Atlas what files matter for implementing Stripe checkout.
Ask Atlas what breaks if I change src/auth/session.ts.
Ask Atlas to build a context pack for adding a new Django template tag.
```

Tool mapping: the first two call `atlas_build_context_pack` and `atlas_what_breaks`;
`atlas_what_breaks` accepts either `target: "path"` or `changed_files: ["path", ...]`.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Client shows "atlas" failing to start | Wrong `command`/`cwd`. Run the command manually; you should be able to type a JSON-RPC line and get a JSON line back. |
| No response / hangs | The server reads one JSON-RPC message per line. Send newline-terminated requests. |
| `repo not scanned` errors | Tools auto-scan on first use; pass an absolute `repo_path` or call `atlas_scan_repo` first. |
| Garbled output | Something wrote to stdout besides the protocol. Use the installed `--mcp` entry or `py -3 run_atlas.py --mcp`; don't pipe other Atlas output to the same stream. |
| Logs | `<Atlas data dir>/mcp_server.log` and the launcher log. No telemetry. |

## Safety

- No network calls in any tool; no secrets returned (`atlas_repo_health` whitelists only
  version/build/repo fields, and all output is secret-sanitized).
- No tool executes your input or writes to your repo. Scanning only reads source files.
- Invalid paths and unscanned repos return structured errors with a `hint`.
