# TASK 8 — Test Results (this fix pass)

**Date:** 2026-06-20. Run after the code/doc changes (download-page copy, config validator [prior], doc email, new scripts).

| Suite | Command | Result |
|---|---|---|
| Website typecheck | `npx tsc --noEmit` (websites/jarvis-landing) | **PASS** (exit 0) |
| Website build | `npm run build` | **PASS** — "Compiled successfully", `/download` route built |
| Context pack | `pytest jarvis_desktop/tests/test_context_pack_mvp.py` | **PASS** |
| Root cause | `pytest jarvis_desktop/tests/test_root_cause.py` | **PASS** |
| MCP server unit | `pytest jarvis_desktop/tests/test_mcp_server.py` | **PASS** |
| Accounts service | `pytest accounts_service/tests` | **PASS** |
| **Combined python** | `pytest <the above> -q` | **89 passed, 3 warnings** |
| MCP smoke (source) | `py -3 scripts/mcp_smoke_test.py` | **PASS** (all checks green) |
| **Installed-exe MCP proof** | `py -3 scripts/mcp_install_proof.py` | **PASS** — self-test ready, initialize, tools/list (17), atlas_health, atlas_scan_repo (125 files), atlas_repo_summary |
| Installer self-test | `dist/Atlas/Atlas.exe --self-test` | **PASS** (exit 0, ready) |
| Website smoke (local) | `SMOKE_ALLOW_WRITE=1 py -3 scripts/website_smoke_test.py http://127.0.0.1:3140` | **PASS** — 7 pages 200, /api/health 200, register 201 |

## Failures
None.

## Skipped / blocked (reasons)
- **Auth endpoint tests against live prod** — BLOCKED (no live deploy; prod env drift). Exercised locally instead (register/login error copy verified in the pre-user QA + website smoke).
- **Live website smoke** — BLOCKED (no live URL until owner fixes env/domain). Script ready.
- **Real Claude Desktop UI MCP call** — owner-only (the frozen-exe transport is proven; the client UI is the last mile).
- **Clean-machine install** — owner-only (no VM here).
- **Full root `tests/` (1,491)** — out of scope (legacy monorepo, heavy deps).

## Warnings (non-blocking)
- `InsecureKeyLengthWarning` in `accounts_service/.lib/jwt` during tests — test-fixture key length only.
