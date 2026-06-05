# Phase 169 — Minimal Atlas Export Implementation

**Status:** Shipped  
**Branch:** `phase78-tool-registry`  
**Depends on:** Phase 168 measurement (`phase168_minimal_export_spec.md`)

## Summary

Phase 168 compression findings are now production behavior. Atlas exposes two export modes — `FULL_EXPORT` (legacy rich markdown) and `MINIMAL_EXPORT` (default) — with once-per-scan session context and per-question measurement blocks on every workflow API response.

## Export modes

| Mode | Constant | Default | Behavior |
| --- | --- | --- | --- |
| Full | `FULL_EXPORT` | No | Formatted markdown + Claude prompt + impact detail sections |
| Minimal | `MINIMAL_EXPORT` | **Yes** | Goal/target, top files, confidence, evidence, implementation order only |

Defined in `jarvis_desktop/atlas_export.py`. Active mode is selected via `export_metrics(..., mode=...)`.

## Session context (once per scan)

After `scan_repository` completes (including cache restore), Atlas builds and stores `ATLAS_SESSION v1`:

- Repository identity
- Graph health
- Module/edge/file statistics
- Top subsystems (≤5)
- Top hubs (≤3)
- Top risks (≤3)

**API:** `GET /api/repositories/current/session-export` → `session_export_packet()`  
**Storage:** `_STATE["session_export"]`  
**UI:** `STATE.sessionExport` fetched after scan/demo load; prepended once when copying to AI tools (`zfSessionPrefix()`).

Session is **not** re-serialized on each Build/Investigate/Impact call.

## Per-question minimal payloads

### Build
- Goal, concept label (name only), confidence, risk
- Top 5 files, implementation order (≤4), may-break importers (≤5)
- Evidence (≤2 bullets), one caveat if present

### Investigate
- Symptom, confidence, most likely root cause
- Top hypothesis + files (H1 only)
- Evidence (≤2), verify checklist (≤4), minimal fix (≤3)

### Impact
- Target, semantic label, confidence, risk
- Direct impact (≤8), indirect (≤5), evidence (≤2)

### Removed from minimal path
- Rollback blocks
- Safety footer / HOW TO USE
- Duplicated file lists and evidence dumps
- Domain understanding essays
- Subsystem enumeration beyond session envelope

## API wiring

`attach_workflow_exports()` is called from:

- `plan_change()` — build
- `investigate_symptom()` — investigate
- `change_impact_simulation()` — impact (ok paths only)

Each successful workflow response includes:

```json
{
  "export": { "mode": "MINIMAL_EXPORT", "tokens": N, "reduction_vs_full_pct": X, "text": "..." },
  "export_full": { "mode": "FULL_EXPORT", ... },
  "export_minimal": { "mode": "MINIMAL_EXPORT", ... }
}
```

## UI wiring

`jarvis_desktop/static/atlas_zero_friction.js`:

- `zfServerExportText()` prefers server `export.text` (minimal by default)
- `zfSessionPrefix()` prepends session envelope once
- Legacy full prompt builders retained as fallback only

`jarvis_desktop/static/app.js` sets `STATE.exportMode = "MINIMAL_EXPORT"` and loads session export after scan/demo.

## Measurement

Every workflow export records:

| Field | Description |
| --- | --- |
| `tokens` | Active export token estimate (`len/4`) |
| `mode` | `FULL_EXPORT` or `MINIMAL_EXPORT` |
| `full_export_tokens` | Full export size |
| `minimal_export_tokens` | Minimal export size |
| `reduction_vs_full_pct` | `(1 - minimal/full) × 100` |

`quality_fidelity_score()` provides structural regression proxy (top-path retention + confidence preservation).

## Files changed

| File | Change |
| --- | --- |
| `jarvis_desktop/atlas_export.py` | New — modes, session, minimal/full formatters, metrics |
| `jarvis_desktop/api.py` | Session storage, `session_export_packet()`, workflow attachment |
| `jarvis_desktop/server.py` | `GET /api/repositories/current/session-export` |
| `jarvis_desktop/static/atlas_zero_friction.js` | Minimal export + session prefix |
| `jarvis_desktop/static/app.js` | Load session export after scan |
| `jarvis_desktop/tests/test_phase169_export_regression.py` | Regression suite |

## Success criteria mapping

| Criterion | Result |
| --- | --- |
| ≥40% export reduction | ✅ 86–94% on reference repo workflows |
| ≤5% quality loss | ✅ 0% structural fidelity loss (reference repo) |
| No trust regression | ✅ Phase 164/164D suites pass (24 tests) |
| No impact regression | ✅ Impact refusal guard intact; impact exports attach on ok paths |

See `reports/phase169_regression.md` for measured numbers.
