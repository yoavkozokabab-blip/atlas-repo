# Atlas MCP client proof — v1.0.1

| Field | Value |
|---|---|
| Atlas version | **1.0.1** |
| Desktop commit | `c50567e3f97cda4be77885bf77939c234ccecd50` |
| Installer SHA-256 | `93AAC567999B0E3D0AAA30AA6E4FBFC9DCFF605DD35DC1D0E1523F4D066B5649` |
| Demo repository | **Atlas Demo — Medium demo** (bundled) |
| Test date | 2026-07-15 |
| Tools exercised | `atlas_health`, `atlas_repo_summary`, `atlas_find_relevant_files`, `atlas_what_breaks` |

## Client matrix

| Client | Config | Restart | Tools visible | Tool call | Repo grounded | Result |
|---|---|---|---|---|---|---|
| Claude Desktop (Microsoft Store) | `%AppData%\Roaming\Claude\claude_desktop_config.json` | Manual relaunch required | Config present; Agents UI shows **Configured** | Not captured in Claude UI this pass | Demo context ready in Atlas | **NOT TESTED** |
| Cursor | `%UserProfile%\.cursor\mcp.json` | MCP reload after config update | **18 tools** | **PASS** — all four tools OK | **Atlas Demo — Medium demo** | **PASS** |
| Codex CLI | `%UserProfile%\.codex\config.toml` | `codex mcp list` | atlas **enabled** in CLI | `codex exec` tool calls not completed | Config verified only | **NOT TESTED** |

\* Claude Desktop MCP handshake was validated through the **installed Atlas v1.0.1** stdio server with the same demo data root used for screenshots. A full Claude Desktop UI restart + in-app tool listing was not captured in this pass.

## Installed MCP stdio battery (v1.0.1 proof install + demo data)

Executed against the production-verified installer at the isolated demo session used for screenshots.

| Tool | Result |
|---|---|
| `atlas_health` | OK — persistence **restored** |
| `atlas_repo_summary` | OK — 17 modules, demo repo |
| `atlas_find_relevant_files` (authentication) | OK — cites `services/auth.py` |
| `atlas_what_breaks` (`services/auth.py`) | OK — direct + transitive impact |

Tool listing: **18 tools** (`atlas_scan_repo` … `atlas_health`). Stderr: clean.

Sanitized Cursor client results: `docs/mcp-proof/cursor-mcp-proof.json`.

## Cursor proof (client-side)

Executed through **Cursor IDE MCP** (`user-atlas`) after pointing MCP config at v1.0.1 with isolated demo data:

| Tool | Result |
|---|---|
| `atlas_health` | OK — persistence **restored**, scan_version **1.0.1** |
| `atlas_repo_summary` | OK — 17 modules, 24 edges |
| `atlas_find_relevant_files` | OK — top: `services/auth.py` |
| `atlas_what_breaks` | OK — 2 direct + 10 indirect importers |

## Codex notes

- `codex mcp list` reports **atlas** enabled with `--mcp` transport.
- Codex exec MCP tool invocation may be limited by model quota; distinguish quota failures from MCP config failures.

## Known limitations

- Impact and Ask use **static import graph** evidence only.
- Claude Desktop UI tool-call screenshot not included when client session could not be restarted headlessly.
- Do not infer macOS/Linux or Claude Code support from this Windows-focused proof.

## Reproduce (stdio battery only)

```powershell
$env:ATLAS_DESKTOP_DATA = '<isolated-demo-data-root>'
& '<path-to-v1.0.1>\Atlas.exe' --mcp
# Send MCP initialize → tools/list → tools/call for atlas_health, etc.
```

For client-side proof, restart each agent after writing MCP config and confirm tools appear in the agent UI before calling `atlas_health`.
