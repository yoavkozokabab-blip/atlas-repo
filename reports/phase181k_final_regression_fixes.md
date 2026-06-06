# Phase 181K — Final Persistence Regression Fixes

**Date:** 2026-06-06  
**Goal:** Clear the two Phase 181J beta blockers.

## Failures Addressed

| Phase 181J issue | Root cause | Fix |
| --- | --- | --- |
| Fresh scan → `memory_untrusted` | `update_after_scan()` put unsigned packet in `_STATE`; only disk sidecar was HMAC-signed in `save_scan_state()` | After signing `memory_packet.json`, sync signed packet back into `state["session_export"]` and `state["repository_memory"]` |
| Support bundle leaks `persistence_secret` marker | Log redaction used `_redact_support_text()` without persistence marker scrub; JSON sanitize had partial coverage | Central `_redact_persistence_secret_markers()` applied to all support text paths |

## Bug 1 — Fresh Scan Export

### Trace

1. `scan_repository()` → `update_after_scan()` builds MEMORY packet (no `memory_hmac`)
2. `_persist_scan_snapshot()` → `save_scan_state()` signs disk sidecar only
3. `session_export_packet()` validates in-memory `_STATE["session_export"]`
4. Missing `memory_hmac` → `legacy_unsigned` → `memory_untrusted`

### Fix

In `save_scan_state()`, after `sign_memory_packet()`:

- Write signed sidecar to disk
- Update `_STATE["session_export"]` and `_STATE["repository_memory"]` with the same signed packet
- Clear `persistence_memory_rejected`

### Preserved behavior

- Valid restored signed memory still exports
- Tampered memory still rejected
- Legacy unsigned memory still blocked

## Bug 2 — Support Bundle Marker Leak

### Fix

Added `_redact_persistence_secret_markers()` in `install_support.py` redacting:

- `persistence_secret`, `PERSISTENCE_SECRET`, `Persistence secret`
- `persistence_secret=…`
- `security/persistence_secret`, `\persistence_secret`, `/persistence_secret`
- Paths containing `persistence_secret`

Replacement: `[REDACTED]`

Applied via `_redact_support_text()` for logs, JSON dumps, and diagnostics.

Security secret file is never added to bundle zip entries.

## Minor Fix

`get_workflow_history_item()` now `continue`s when a matching `history_id` fails repo validation instead of returning `None` immediately — prevents forged cross-folder rows from hiding valid history.

## Test Results

```text
test_phase181b_persistence.py          10 passed
test_phase181e_persistence_red_team_fixes.py   8 passed
test_phase181g_persistence_signing.py  11 passed
test_phase181k_final_regressions.py    10 passed
```

## Files Changed

- `jarvis_desktop/persistence.py` — sync signed memory to state; history lookup continue fix
- `jarvis_desktop/install_support.py` — persistence secret marker redaction
- `jarvis_desktop/tests/test_phase181k_final_regressions.py` — 10 regression tests

## Manual Phase 181J Checks

1. Fresh scan → `session_export_packet()` → `ok=true`, trusted MEMORY export
2. Support bundle with `persistence_secret` in `launcher.log` → marker absent from zip payload
