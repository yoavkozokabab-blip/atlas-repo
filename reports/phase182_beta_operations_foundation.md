# Phase 182 — Beta Operations Foundation

**Date:** 2026-06-06  
**Scope:** Operations layer only — no intelligence, graph, trust, persistence, or benchmark changes.

## Pre-Implementation Inventory

| Area | Existing | Gap |
| --- | --- | --- |
| Analytics | `analytics.py` — local JSONL, `track_event`, `analytics_summary`, `/api/analytics/event` | No install identity enrichment, no unified pipeline schema |
| Feedback | `submit_feedback()` → `feedback/feedback.jsonl`, optional remote URL | No inbox/list API for beta operators |
| Update system | `product_info.check_for_update()` — optional URL, basic semver compare | No malformed/downgrade/jump hardening |
| Diagnostics | `beta_diagnostics()`, support bundle, startup status | No unified beta insights dashboard |

## Implemented Components

### 1. Installation identity

- Path: `{data_dir}/operations/installation.json`
- Stable `installation_id` (16-char hex), created on first health/ops touch
- Exposed on `/api/health` and `/api/operations/identity`

### 2. Analytics event pipeline

- `operations.pipeline_track_event()` wraps `analytics.track_event()`
- Enriches every event with: `installation_id`, `pipeline_version`, `channel`, `product`
- Wired through `api.track_analytics_event()` (all existing callers)

### 3. Beta insights dashboard

- `GET /api/operations/insights` (requires `ATLAS_ADMIN=1`)
- Aggregates: installation, analytics summary, feedback inbox, crash registry, token savings, hardened update status

### 4. Feedback inbox

- `GET /api/operations/feedback` (admin)
- Reads local `feedback/feedback.jsonl`
- `submit_feedback()` now adds `feedback_id` and `installation_id`

### 5. Token savings dashboard

- `GET /api/operations/token-savings`
- Aggregates `export_created` / `session_export_used` token fields from analytics
- Includes current scan `_token_savings` estimate when a repo is open

### 6. Crash registry

- Path: `{data_dir}/operations/crashes.jsonl`
- `operations.record_crash()` + `POST /api/operations/crash`
- Scan failures (`ok=false`) auto-recorded as `scan_failure`
- `GET /api/operations/crashes` (admin)

### 7. Update hardening

- `operations.check_update_hardened()` replaces raw `check_for_update()` in API
- Rejects: malformed versions, downgrades, major jumps >1, unknown channels
- Surfaces `trust_level`: `trusted` | `unavailable` | `malformed`

## API Routes Added

| Method | Path |
| --- | --- |
| GET | `/api/operations/identity` |
| GET | `/api/operations/insights` |
| GET | `/api/operations/feedback` |
| GET | `/api/operations/token-savings` |
| GET | `/api/operations/crashes` |
| POST | `/api/operations/crash` |

## Test Results

```text
py -3 -m pytest jarvis_desktop/tests/test_phase182_beta_operations.py -q
11 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py -q
10 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py -q
8 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181g_persistence_signing.py -q
11 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181k_final_regressions.py -q
10 passed
```

Combined persistence + operations: **50 passed**

## Files Changed

- `jarvis_desktop/operations.py` (new)
- `jarvis_desktop/api.py` — pipeline wiring, ops endpoints, health install id
- `jarvis_desktop/server.py` — route table entries
- `jarvis_desktop/tests/test_phase182_beta_operations.py` (new)

## Intentionally Unchanged

- UI static assets
- Graph engine, impact engine, planning intelligence
- Trust integrity and persistence modules
- Billing and website
- Benchmark harnesses

## Operator Usage

```powershell
$env:ATLAS_ADMIN = "1"
py -3 -m jarvis_desktop.server
# GET /api/operations/insights
# GET /api/operations/feedback
# GET /api/operations/crashes
```

## Remaining Limitations

- Insights/feedback/crash list APIs require local `ATLAS_ADMIN=1` (same gate as usage admin)
- Token savings depend on events recording token fields (export/session paths wired; workflow exports optional)
- Crash registry is local-only — no remote aggregation
- Update hardening validates metadata only; does not verify package signatures
