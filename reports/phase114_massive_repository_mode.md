# Phase 114 — Massive Repository Mode

Status: complete  
Scope: product/runtime support for very large repositories, with Builder Core analysis semantics unchanged.

## What was added

- Massive Repository Mode auto/manual trigger:
  - files > 20,000
  - modules > 5,000
  - repo size > 1GB
  - manual force toggle
- Pre-scan estimator (`POST /api/repositories/estimate`):
  - total files, code files, estimated modules
  - repo size
  - language breakdown
  - ignored folders
  - likely scan time and suggested scopes
- Scope selector support (scan input):
  - entire repo
  - specific folder
  - python only
  - backend only
  - frontend only
  - custom include/exclude patterns
- Safe defaults:
  - excluded folders include `.git`, `node_modules`, `dist`, `build`, `target`, `vendor`, `.venv`, `__pycache__`
  - binary/generated/log/temp-like files excluded in light indexing
- Hierarchical graph endpoint:
  - `GET /api/repositories/current/hierarchy-graph`
  - levels: subsystem -> package -> module
- Progressive scan runtime stages + cancel hooks:
  - scan stage tracking in `_STATE["scan_job"]`
  - `GET /api/repositories/current/scan-status`
  - `POST /api/repositories/current/cancel-scan`
- Cache:
  - signature-based in-memory cache
  - cache hit/miss surfaced in scan summary
- Large graph safety:
  - in massive mode, module view defaults to subsystem overview unless forced
  - warning message included in graph payload
- UX:
  - Massive Repository Mode badge
  - pre-scan estimate readout
  - scope controls in Home
  - hierarchy view option
  - scan cancel button

## Endpoints added

- `POST /api/repositories/estimate`
- `GET /api/repositories/current/scan-status`
- `POST /api/repositories/current/cancel-scan`
- `GET /api/repositories/current/hierarchy-graph`

## Files changed

- `jarvis_desktop/api.py`
- `jarvis_desktop/server.py`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/styles.css`
- `jarvis_desktop/tests/test_phase107_desktop_api.py`
- `jarvis_desktop/tests/test_phase114_massive_repository_mode.py`

## Tests

Added Phase 114 test coverage for:

- pre-scan estimator
- ignore rules and scope selector
- manual massive mode trigger
- cache hit/miss
- cancel scan state
- graph downsampling safety behavior
- hierarchy graph levels
- server route wiring

Run:

```powershell
py -m pytest jarvis_desktop/tests/test_phase114_massive_repository_mode.py jarvis_desktop/tests/ -q
```

## Notes

- Builder Core analysis semantics were not changed.
- Support is implemented as runtime orchestration, pre-filtering in product layer, safer visualization defaults, and progressive UX.
