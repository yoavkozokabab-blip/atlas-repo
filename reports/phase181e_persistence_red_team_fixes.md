# Phase 181E — Persistence Red Team Fixes

**Date:** 2026-06-06  
**Goal:** Clear the three Phase 181C P0 persistence trust failures without touching UI, graph intelligence, impact engine, billing, or website.

## Failures Addressed

| Phase 181C attack | Fix |
| --- | --- |
| History poisoning | Integrity hash on every history row; tampered/forged rows rejected at read time |
| Memory / scan mismatch | Memory sidecar validated against `repo_id`, `scan_id`, `scan_signature`, `graph_signature` before restore/export |
| Version mismatch | `atlas_version` validated on scan restore; future/incompatible/malformed versions refused |

## What Changed

### History integrity (`jarvis_desktop/persistence.py`)

- Each workflow history record now stores:
  - `scan_signature`
  - `atlas_version`
  - `integrity_hash` (SHA-256 over canonical fields)
- On read (`list_workflow_history`, `get_workflow_history_item`):
  - Recompute and verify hash
  - Verify `repo_id` matches the on-disk history folder
  - Require `scan_id` and `scan_signature`
  - Validate `atlas_version`
- Tampered or path-mismatched rows are **silently dropped** (not returned to API/UI)
- Export evaluation blocks untrusted restore state and `scan_id` / signature drift

### Memory / scan binding

- New `validate_memory_packet()` checks persisted `memory_packet.json` (and on-disk memory) against scan metadata
- On restore mismatch:
  - Memory is **discarded** (`repository_memory`, `session_export`, `_current_memory` not loaded)
  - `persistence_memory_rejected` and `requires_refresh_before_export` set on state
- `session_export_packet()` refuses export when memory was rejected or packet fails re-validation

### Version gate

- New `validate_persistence_version()` compares persisted vs `PRODUCT_VERSION`
- Refuses restore when version is:
  - **Future** (e.g. `999.0.0-future-incompatible`)
  - **Incompatible major** (major segment differs)
  - **Malformed** (no parseable `x.y.z`)
- User-facing message: **"Rescan required after Atlas update"**
- Wired into `validate_scan_state`, bootstrap resume card, and `resume_persisted_repository` (`code: version_mismatch`)

## Intentionally Unchanged

- UI assets
- Graph intelligence / impact engine / billing / website
- Repository memory on-disk format and hash algorithm
- Scan signature / trust-integrity algorithms

## Test Results

```text
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py -q
10 passed

py -3 -m pytest jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py -q
8 passed
```

### Phase 181E coverage

- Tampered history rejected
- Fake history path rejected
- Old `scan_id` blocked for export
- Memory `scan_id` mismatch rejected on restore/export
- Graph signature mismatch rejected
- Future version refused
- Malformed version refused
- Export blocked from untrusted restore

## Remaining Limitations

- History rows written before Phase 181E (no `integrity_hash`) are ignored on read
- Scan/graph restore may still succeed when only memory sidecar is poisoned; export remains blocked until refresh
- Version check uses numeric `major.minor.patch` segments only (suffixes like `-beta` are ignored for comparison)
- History list always reports `export_allowed=false` until a specific item is opened with active session context

## Verdict vs Phase 181C

The three P0 persistence attacks (history poisoning, memory poisoning, version bypass) are now blocked at the persistence/API layer. Supervised beta persistence trust posture improves from **NO-GO** to **GO with documented limitations above**.
