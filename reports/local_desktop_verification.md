# Atlas Desktop — Local Verification (Ops Phase / Step 2)

**Date:** 2026-06-16
**Launcher:** `run_atlas.py` (source mode, `py -3`)
**Run:** `py -3 run_atlas.py --no-browser --port 8779`

## Results

| Check | Status | Evidence |
|---|---|---|
| App starts | **PASS** | local server ready in ~1s |
| Local UI serves | **PASS** | `GET /` → 200, `<title>ATLAS — Repository Intelligence Platform</title>` |
| Core pages served | **PASS** | `/`, `/index.html`, `/support.html`, `/startup-error.html` all 200 |
| Health endpoint | **PASS** | `GET /api/health` → 200 |
| No startup errors | **PASS** | launcher log shows no error/traceback/exception |
| `--self-test` | **PASS** | "Atlas self-test: READY" (launcher, dirs, shortcuts, browser all ok) |
| `--mcp` stdio mode | **PASS** | initialize + tools/list + tools/call drive returns valid newline-framed JSON-RPC |
| Repo scan | **PASS (engine)** | via MCP `atlas_scan_repo` → codebase_map (dependency_edges, entry_points) |
| Context pack generation | **PASS (engine)** | via MCP `atlas_build_context_pack` → HIGH confidence + files + reasons |
| What-breaks | **PASS (engine)** | via MCP `atlas_what_breaks` → impact analysis (`target` or `changed_files`) |
| Account / login (desktop) | **WARN — not deeply exercised** | UI loads; desktop auth talks to the bundled accounts service (`AtlasAccounts.exe`) which was not driven end-to-end locally this session |

## Notes

- Scan / context-pack / what-breaks were verified through the **MCP server**, which calls the
  exact same `jarvis_desktop` internals the desktop UI uses (`api.change_impact_simulation`,
  `build_context_pack_from_state`). The engine is proven; the desktop HTTP UI is a thin layer
  over it and boots cleanly.
- The 12-check MCP smoke test (`scripts/mcp_smoke_test.py`) passes green, exercising scan →
  map → context pack → find_file → what_breaks → repo_health end-to-end.
- Account creation/login *on the desktop* connects to the local accounts service; a full
  desktop auth round-trip is best validated in the clean-machine test plan
  (`docs/CLEAN_INSTALL_TEST_PLAN.md`), not in source mode here.

## Verdict: **PASS** (desktop app + engine healthy in source mode)

Remaining desktop validation that needs the installed build (not source): first-launch from
the installed `Atlas.exe`, desktop account flow, and MCP from the windowed exe — all covered
in the clean-machine plan.
