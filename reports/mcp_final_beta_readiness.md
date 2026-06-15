# Atlas MCP — Final Beta Readiness (Phase 4)

**Date:** 2026-06-16
**Repo:** `C:\J.A.R.V.I.S\local_jarvis`, branch `monetization-v1`
**Server:** `jarvis_desktop/mcp_server/runtime.py` (canonical), launched via `--mcp`.

## Verdict: **MCP_EXPERIMENTAL_ONLY**

The MCP server is real, safe, and works in source mode against the standard MCP stdio
transport. It is **not yet verified** as a one-click feature of the installed windowed
app, so it ships to beta **labeled experimental**, with source mode as the supported path.

---

## What was verified this session

| Check | Result | Evidence |
|---|---|---|
| 7 tools exposed, stable input schemas | PASS | `tools/list` returns all 7; `_schema` uses `additionalProperties:false` |
| Newline-delimited JSON-RPC (real-client framing) | **FIXED + PASS** | `_write_message` now emits `data + "\n"` (was Content-Length); reader stays tolerant |
| `initialize` / `tools/list` / `tools/call` over stdio | PASS | live drive of `py -3 run_atlas.py --mcp` returned valid JSON-RPC |
| Smoke test (12 checks) | PASS | `scripts/mcp_smoke_test.py` → "all checks green" |
| Secret sanitization | PASS | `_sanitize` + secret regex; "repo_health leaks no secrets" check passes |
| No code execution / no writes / no network | PASS | stdio-only, read-only tool handlers, no socket/subprocess in tool paths |
| `atlas_what_breaks` schema/doc mismatch | **FIXED** | now accepts `target` *or* `changed_files: [...]`; doc example valid |
| Launcher entry for installed app | **ADDED** | `run_atlas.py --mcp` → `serve_stdio()` with stdio rebind |

## The 7 tools

`atlas_scan_repo`, `atlas_get_codebase_map`, `atlas_build_context_pack`,
`atlas_what_breaks`, `atlas_plan_change`, `atlas_find_file`, `atlas_repo_health` —
each with a stable input schema, structured errors (`{error, message, hint}`), and
secret-sanitized JSON output. Tools auto-scan on first use and report `scanned_now`.

## Why EXPERIMENTAL, not READY

1. **Installed-app launch path is unverified.** `Atlas.exe` is a `console=False`
   (windowed) PyInstaller build, so Python sets `sys.stdin/stdout` to `None`. The new
   `--mcp` handler rebinds stdio from fds 0/1 (the pipes an MCP client connects). This is
   implemented and should work when a client (e.g. Claude Desktop via Node `child_process`)
   spawns it with `STARTF_USESTDHANDLES`, **but it has not been tested against a real client
   with a freshly built exe.** Source mode is verified; the frozen path is not.
2. **No real-client integration test.** Smoke test drives the server directly; we have not
   run it inside Claude Desktop/Cursor end-to-end.
3. **`serverInfo.version` reports `1.0.0`** (server impl version), independent of the app's
   `0.1.0-beta`. Cosmetic; reconcile before calling it GA.

## Path to MCP_READY_FOR_BETA

- **Recommended (robust):** add a dedicated console MCP exe (`atlas-mcp.spec`,
  `console=True`) bundled by the installer; point client configs at `atlas-mcp.exe`. Avoids
  the windowed-exe stdio rebind entirely.
- **Or (pragmatic):** rebuild `Atlas.exe`, install on a clean machine, wire Claude Desktop
  to `Atlas.exe --mcp`, and confirm tools list + a `tools/call` round-trip. If green, the
  rebind path is sufficient and MCP can be promoted to READY.
- Reconcile `serverInfo.version` with app version.

## Docs

- `README_MCP.md` — overview, tools, run commands (installed + source), safety.
- `docs/MCP_CLIENT_SETUP.md` — per-client config (Claude Desktop/Code, Cursor, Codex),
  example prompts, troubleshooting.
- `docs/MCP_SERVER_DESIGN.md` — design/spec (pre-existing).

## Honest claims for marketing/docs

- ✅ "Atlas has a local, read-only MCP server for AI coding agents (experimental)."
- ✅ "Works with Claude Code/Desktop, Cursor, Codex in source mode."
- ❌ Do **not** claim one-click MCP from the installed app until the frozen-exe path is
  verified against a real client.
