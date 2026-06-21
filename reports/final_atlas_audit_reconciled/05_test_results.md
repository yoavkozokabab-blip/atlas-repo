# 05 — Test Results (current build, this reconciliation)

**Date:** 2026-06-20. The only code change this turn was a docs file (`ATLAS_QUICKSTART.md`), which cannot affect code tests or the website build; results below are the current, post-change state.

| Suite | Command | Result |
|---|---|---|
| Context pack | `pytest jarvis_desktop/tests/test_context_pack_mvp.py` | **PASS** (included below) |
| Root cause (#10) | `pytest jarvis_desktop/tests/test_root_cause.py` | **PASS** |
| MCP server | `pytest jarvis_desktop/tests/test_mcp_server.py` | **PASS (5)** — `required.issubset(names)` holds with 18 tools |
| Desktop auth UX | `pytest .../test_phase188_auth_ux.py` | **PASS** |
| Frozen accounts | `pytest .../test_phase192_frozen_accounts.py` | **PASS** |
| Access-state UX | `pytest .../test_phase193_access_state_ux.py` | **PASS** |
| Accounts service | `pytest accounts_service/tests` | **PASS** |
| **Combined run** | `pytest <all above> -q` | **112 passed, 94 warnings in 46.29s** |
| MCP smoke | `py -3 scripts/mcp_smoke_test.py` | **SMOKE TEST PASSED: all checks green** (12/12) |
| Website typecheck | `npx tsc --noEmit` (websites/jarvis-landing) | **PASS (exit 0)** |
| Website build | `npm run build` | **PASS** (all routes compiled/prerendered) |

## Failures
None.

## Skipped / not run (with reasons)
- **Full root `tests/` (1,491 collected)** — not run. It covers the legacy JARVIS monorepo (voice/vision/browser) outside the Atlas beta surface and pulls heavy optional deps. Out of scope for this reconciliation; the Atlas-relevant suites above were run instead.
- **Installer smoke / clean-machine** — not run (no clean VM; OWNER_ONLY). `dist/Atlas/Atlas.exe --self-test` previously returned `ready:true, frozen:true` on the dev box.
- **Real Claude/Cursor/Codex MCP** — not run (no client/VM; OWNER_ONLY). Only local in-process MCP proof exists.
- **Live website / Supabase** — not run (not deployed; OWNER_ONLY).
- **Blind agent A/B** — not run (no API key; self-grading forbidden; harness ready).

## Warnings (non-blocking)
- `InsecureKeyLengthWarning` (HMAC key 17 bytes) in `accounts_service/.lib/jwt` during tests — test-fixture secret length only; production uses `AUTH_SECRET`/`ATLAS_JWT_SECRET`. Not a failure.
- Git CRLF/LF warnings on commit — cosmetic.
