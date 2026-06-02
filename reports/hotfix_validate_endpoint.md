# Hotfix — Validate Endpoint Release Blocker

**Status:** Fixed  
**Severity:** P0 release blocker  
**Date:** 2026-05-28

## Symptom

Home screen **Validate** calls `POST /api/repositories/validate` and the UI showed:

```text
Unknown endpoint: POST /api/repositories/validate
```

(or the trailing-slash variant)

## Root cause

Three contributing factors:

| # | Cause | Detail |
|---|--------|--------|
| 1 | **Trailing-slash mismatch** | `dispatch()` compared paths literally. `POST /api/repositories/validate/` did not match `/api/repositories/validate` → `Unknown endpoint`. Some clients/proxies append `/`. |
| 2 | **Fragile manual routing** | Routes were duplicated across a long `if` chain, `ROUTES` tuple, and FastAPI handlers — easy to drift during rapid phases (109 frontend vs 110 backend was a prior gap). |
| 3 | **Stale server process** | Phase 109 and earlier servers **did not register** `/api/repositories/validate` (added in Phase 110). A long-lived desktop process would reject Validate even with a current UI bundle. |

The route **was present** in current source (`jarvis_desktop/server.py`), but path normalization and registry hardening were missing.

## Fix

1. **`normalize_api_path()`** — strips trailing slashes (except root) before lookup.
2. **`_route_handlers()` registry** — single source of truth; `dispatch()`, `ROUTES`, and tests all derive from it.
3. **`route_is_registered()`** — used by route-audit tests.
4. **HTTP handler** — normalizes paths in `do_GET` / `do_POST` / `_route_api`.
5. **Frontend `api()` helper** — normalizes paths (preserves query strings), logs `Unknown endpoint` to console for faster diagnosis.

## Verification

### Where Validate is called

| Location | Trigger |
|----------|---------|
| `index.html` | Validate button → `validateRepoPath()` |
| `app.js` | Enter in repo path field |
| `app.js` | `scanFlow()` before scan |
| `app.js` | `selectRecentPath()` on recent repo chip |

All use: `POST /api/repositories/validate` with `{ path }`.

### Tests added

`jarvis_desktop/tests/test_hotfix_validate_endpoint.py`:

- HTTP integration: valid path → success payload
- HTTP integration: empty path → structured `empty_path` error (not Unknown endpoint)
- Trailing slash normalized
- Validate after demo load
- Full frontend → backend route audit

Run:

```powershell
cd local_jarvis
py -m pytest jarvis_desktop/tests/test_hotfix_validate_endpoint.py jarvis_desktop/tests/ -q
```

## Frontend API audit

| Screen | Endpoint | Method | Registered | Tested |
|--------|----------|--------|------------|--------|
| Boot | `/api/health` | GET | Yes | Existing |
| Boot / Home | `/api/repositories/current/summary` | GET | Yes | Existing |
| Home | `/api/repositories/validate` | POST | Yes | **Hotfix HTTP** |
| Home | `/api/demo/packs` | GET | Yes | Phase 112 |
| Home / Scan | `/api/repositories/select` | POST | Yes | Existing |
| Home / Scan | `/api/repositories/scan` | POST | Yes | Existing |
| Demo | `/api/demo/load` | POST | Yes | Phase 112 |
| Command Center | `/api/repositories/current/graph` | GET | Yes | Phase 108 |
| Command Center | `/api/repositories/current/timeline` | GET | Yes | Phase 111 |
| Command Center | `/api/repositories/current/module` | GET | Yes | Phase 111 |
| Command Center | `/api/demo/export-bundle` | POST | Yes | Phase 112 |
| Copilot | `/api/copilot/ask` | POST | Yes | Phase 109 |
| Impact | `/api/impact` | POST | Yes | Existing |
| Bug Hunt | `/api/bug-investigation` | POST | Yes | Existing |
| AI Export | `/api/context/export` | POST | Yes | Existing |
| Analytics (client) | `/api/analytics/event` | POST | Yes | Phase 112 |

**Result after fix:** 0 missing routes in `app.js` audit.

## Operator note

If Validate still fails after pulling this fix:

1. Stop any old JARVIS Desktop process (Task Manager).
2. Restart via `py run_jarvis_desktop.py` from `local_jarvis/`.
3. Hard-refresh browser (Ctrl+F5) to reload `app.js`.

## Files changed

- `jarvis_desktop/server.py` — route registry + path normalization
- `jarvis_desktop/static/app.js` — client path normalization + error logging
- `jarvis_desktop/tests/test_hotfix_validate_endpoint.py` — integration + audit tests
