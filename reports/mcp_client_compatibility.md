# Atlas MCP — Client Compatibility (Phase 5 / P4)

**Date:** 2026-06-16
**Server:** `jarvis_desktop/mcp_server/runtime.py`, launched via `Atlas.exe --mcp` /
`py -3 run_atlas.py --mcp` / `py -m jarvis_desktop.mcp_server`.
**Protocol:** JSON-RPC 2.0 over stdio, **newline-delimited** (MCP stdio standard),
`protocolVersion: 2024-11-05`.

## Protocol conformance — verified this session

Driven directly over stdio (`run_atlas.py --mcp`), newline-framed:

| Request | Result |
|---|---|
| `initialize` | ✅ `protocolVersion: 2024-11-05`, `capabilities.tools`, `serverInfo{atlas-local, 0.1.0-beta}` |
| `notifications/initialized` (no id) | ✅ correctly produces **no response** (notification semantics) |
| `tools/list` | ✅ returns all 7 tools with input schemas |
| `tools/call atlas_scan_repo` | ✅ codebase_map (dependency_edges, entry_points) |
| `tools/call atlas_build_context_pack` | ✅ confidence HIGH + reasons + files |
| `tools/call atlas_what_breaks` | ✅ accepts `target` or `changed_files[]`; impact analysis |
| `tools/call <unknown tool>` | ✅ graceful structured error (`ok:false, code:unknown_tool`) |
| unknown method | ✅ JSON-RPC error `-32601 Unsupported MCP method` |
| `scripts/mcp_smoke_test.py` (12 checks) | ✅ all green |

**Framing fix (P0, done):** the writer previously emitted LSP-style `Content-Length`
framing, which real MCP stdio clients do not parse. It now emits newline-delimited JSON;
the reader still tolerates both. This is the single change that makes real-client use possible.

## Per-client readiness

| Client | Transport | Source mode | Installed `Atlas.exe --mcp` |
|---|---|---|---|
| **Claude Code (CLI)** | stdio | ✅ `claude mcp add atlas -- py -3 run_atlas.py --mcp` | ⚠️ unverified |
| **Claude Desktop** | stdio | ✅ config in `docs/MCP_CLIENT_SETUP.md` | ⚠️ unverified (windowed-exe stdio rebind) |
| **Cursor** | stdio (`.cursor/mcp.json`) | ✅ | ⚠️ unverified |
| **Codex / generic** | stdio | ✅ | ⚠️ unverified |

Source mode is **verified at the protocol level** for all stdio clients (identical transport).
The installed-app path is implemented (`--mcp` rebinds stdio from the client's pipes because
`Atlas.exe` is a `console=False` build) but **not yet driven by a real client with a freshly
built exe** — see "Known constraints."

## Known constraints / risks

1. **Windowed-exe stdio (Windows).** `Atlas.exe` has no console; `--mcp` rebinds
   `sys.stdin/stdout` from fds 0/1. This works when a client spawns it with inherited std
   handles (Node `child_process`, which Claude Desktop/Cursor use), but is **unverified
   end-to-end**. Robust alternative: ship a dedicated console exe (`atlas-mcp.exe`,
   `console=True`) — recommended before promoting MCP past experimental.
2. **First-call latency.** Tools auto-scan on first use; a large repo's first
   `tools/call` can take seconds. Clients with short startup/handshake timeouts may need the
   user to trigger a scan first. `initialize`/`tools/list` are instant, so discovery is fine.
3. **Path handling.** `repo_path` should be absolute for installed-app use (the working
   directory of a client-spawned server is not the user's repo). Relative paths resolve
   against the server CWD — documented in the setup guide.
4. **No `prompts`/`resources` capabilities.** Server advertises only `tools` — correct;
   clients that probe `prompts/list` get `-32601`, which is spec-acceptable for a
   tools-only server.

## Verdict

**MCP_PROTOCOL_READY / INSTALLED_APP_EXPERIMENTAL.**
The protocol implementation is correct and verified for all stdio MCP clients in source
mode. The installed-app launch path is implemented but must be confirmed against a real
client with a rebuilt exe before being advertised as one-click. No false claims: docs label
the installed path experimental.

### To reach fully READY
- Rebuild `Atlas.exe`; wire Claude Desktop to `Atlas.exe --mcp`; confirm `tools/list` + one
  `tools/call` round-trip. If green → promote. If flaky → ship `atlas-mcp.exe` (console build).
