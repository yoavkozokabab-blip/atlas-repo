# Atlas MCP client proof — v1.0.2

| Field | Value |
|---|---|
| Atlas version | **1.0.2** |
| Desktop commit | `f3d864e9aee823c1b5b33a54b07f6135c5d61bf1` |
| Installer SHA-256 | `1BDE84E27715D2F71406D0231175C65FB820601EC37EAD1B96CDF0ECF61FC465` |
| Demo repository | **Atlas Demo — Medium demo** (bundled) |
| Test date | 2026-07-15 |
| Tools exercised | `atlas_health`, `atlas_repo_summary`, `atlas_find_relevant_files`, `atlas_what_breaks` |

## Client matrix

| Client | Config | Restart | Tools visible | Tool call | Repo grounded | Result |
|---|---|---|---|---|---|---|
| Claude Desktop | `%AppData%\Roaming\Claude\claude_desktop_config.json` | Manual relaunch required | Config path discoverable via `atlas_health` | Not captured in Claude UI this pass | — | **NOT TESTED** |
| Cursor | `%UserProfile%\.cursor\mcp.json` | MCP reload after config update | **18 tools** | **PASS** — all four primary tools OK | **Atlas Demo — Medium demo** | **PASS** |
| Codex CLI | `%UserProfile%\.codex\config.toml` | — | — | Not completed in this pass | — | **NOT TESTED** |

## Installed MCP stdio battery (v1.0.2 clean install)

Executed via `scripts/mcp_install_proof.py` against the v1.0.2 clean-install `Atlas.exe`.

| Tool | Result |
|---|---|
| `atlas_health` | OK |
| `atlas_repo_summary` | OK — 17 modules, demo repo |
| `atlas_find_relevant_files` (authentication) | OK — cites `services/auth.py` |
| `atlas_what_breaks` (`services/auth.py`) | OK — direct + transitive impact |

Tool listing: **18 tools**. Stderr: clean.

## Cursor proof (client-side)

Executed through **Cursor IDE MCP** (`user-atlas`) after pointing MCP config at the v1.0.2 clean-install binary:

- `atlas_health` — OK
- `atlas_repo_summary` — OK (17 modules, 24 edges)
- `atlas_find_relevant_files` — OK (`services/auth.py`)
- `atlas_what_breaks` — OK (high blast radius, 2 direct / 10 indirect)

Claude Desktop and Codex remain **NOT TESTED** in this pass; configuration paths remain valid but were not re-verified through those UIs on v1.0.2.
