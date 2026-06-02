# Phase 116F — Analytics Isolation Hardening

**Date:** 2026-06-02  
**Product version:** `phase116f-analytics-isolation`  
**Scope:** Desktop reliability only — no Builder Core or analysis logic changes.

## Problem

Phase 116E found that `PermissionError` on `%USERPROFILE%\.jarvis_desktop\analytics.jsonl` could abort:

- `POST /api/repositories/scan` (via `track_analytics_event("scan_completed")` at end of `scan_repository`)
- `POST /api/demo/load` (same scan tail + `demo_loaded`)

Telemetry was on the **critical path** with no error boundary.

## Solution

### 1. Fail-safe analytics module (`jarvis_desktop/analytics.py`)

- All writes wrapped in `try/except OSError` (covers `PermissionError`, `IOError` on Windows).
- Failures are **logged** (`jarvis.analytics` logger) and return a result dict — **never raised**.
- Module status: `analytics.status_snapshot()` → `analytics_status: "ok" | "degraded"`.
- Degraded message: **"Telemetry unavailable. Repository analysis unaffected."**
- Thread lock around append to reduce same-process races.
- Reads (`_read_events`, `analytics_summary`) also fail-safe — empty counts, degraded status, no raise.

### 2. API payloads (`jarvis_desktop/api.py`)

- `_attach_analytics_status(payload)` merges status + `telemetry_warning` + `warnings[]` into scan/demo responses.
- Applied after `scan_completed` on cache hit and full scan, and after `load_demo_mode`.
- `GET /api/health` and `GET /api/repositories/current/summary` expose telemetry status for UI.

Scan/demo still return `"ok": true` when analysis succeeds; `analytics_status: "degraded"` signals telemetry-only failure.

### 3. Desktop UI

- Banner `#telemetryWarning` below top bar (amber glass).
- `updateTelemetryWarning()` — driven by health, scan, demo, and summary payloads.
- Health Cockpit shows telemetry card when degraded.

### 4. Tests

`jarvis_desktop/tests/test_phase116f_analytics_isolation_hardening.py`:

| Test | Asserts |
|------|---------|
| `test_track_event_does_not_raise_on_permission_error` | Simulated `PermissionError` on append → degraded, no raise |
| `test_scan_succeeds_when_analytics_write_fails` | Scan `ok`, modules present, `analytics_status: degraded` |
| `test_demo_succeeds_when_analytics_write_fails` | Demo `ok`, `demo_mode`, degraded telemetry |
| `test_scan_succeeds_when_analytics_directory_cannot_be_created` | `makedirs` `PermissionError` → scan still `ok` |
| `test_health_reports_degraded_telemetry_after_write_failure` | Health carries warning |
| `test_summary_reports_degraded_telemetry_after_write_failure` | Summary carries warning |

Run:

```powershell
cd local_jarvis
py -3 -m pytest jarvis_desktop/tests/test_phase116f_analytics_isolation_hardening.py -q
```

## Files changed

| File | Change |
|------|--------|
| `jarvis_desktop/analytics.py` | Fail-safe writes/reads, status snapshot, write lock |
| `jarvis_desktop/api.py` | `_attach_analytics_status`, health/summary telemetry fields |
| `jarvis_desktop/static/index.html` | Telemetry banner |
| `jarvis_desktop/static/styles.css` | `.telemetry-banner` |
| `jarvis_desktop/static/app.js` | `updateTelemetryWarning`, cockpit + init hooks |
| `jarvis_desktop/tests/test_phase116f_analytics_isolation_hardening.py` | New tests |
| `reports/phase116f_analytics_isolation_hardening.md` | This report |

## Acceptance

| Requirement | Status |
|-------------|--------|
| OSError / PermissionError / IOError logged and ignored for scan path | ✓ |
| Scan continues on analytics failure | ✓ |
| Demo continues on analytics failure | ✓ |
| `analytics_status: "degraded"` on failure | ✓ |
| Desktop health warning | ✓ |
| Tests | ✓ |
| No Builder Core changes | ✓ |
