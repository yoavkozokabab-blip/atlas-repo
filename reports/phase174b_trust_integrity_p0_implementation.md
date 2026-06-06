# Phase 174B — Trust Integrity P0 Implementation

**Date:** 2026-06-05 (corrected)  
**Scope:** Stale/wrong/unsafe export paths + user-controlled targeted refresh. No intelligence, UI, billing, or benchmark changes.

## Summary

Phase 174B closes P0 trust-integrity failures from Phase 173C / 172A. Atlas refuses exports when repository context is stale or tampered, exposes persistence/diagnostic status, and offers **targeted file refresh** — never automatic full-repo rescans.

## Why full auto-rescan was rejected

Automatic full rescans after file edits were explicitly **not** implemented because:

- Users may be mid-edit; Claude/Cursor output is often incomplete
- Full rescans are expensive on real repositories
- Silent refresh would hide stale-context bugs and erode trust
- Users must control when Atlas re-trusts the working tree

**Acceptance:** Atlas never silently trusts changed code. Atlas never silently rescans the entire repo.

## Targeted refresh design

When files change **only within the last Atlas plan** (`recommended_files` / `inspected_files` / `likely_modified_files`):

| State flag | Meaning |
|------------|---------|
| `targeted_refresh_available=true` | Changed files ⊆ plan scope |
| `repo_changed_outside_plan=false` | No unrelated edits |

User message:

> Files from the last Atlas plan changed. Refresh those files before exporting new context.

**User action:** `POST /api/repositories/current/refresh-changed-files` (button: *Refresh changed files*)

**Scope updated (not whole repo):**

- AST symbols for changed files
- Imports / call edges touching changed files
- Direct dependency-graph neighbors (importers/importees)
- Index metadata for affected paths
- Evidence store records for touched files
- `signature_v2` manifest + memory delta (`refresh_generation` bump, new `memory_ref`)

When files change **outside** the plan (or git HEAD moves, or no plan exists):

| State flag | Meaning |
|------------|---------|
| `repo_changed_outside_plan=true` | Unscoped edits |
| `targeted_refresh_available=false` | Targeted refresh insufficient |

User message:

> Repository changed outside the last Atlas plan. A full rescan may be required.

Exports remain blocked until **full rescan** or scoped refresh where applicable.

## User-controlled refresh behavior

1. **No silent refresh** — graph/memory/signature never update without explicit API call.
2. **Workflows stay historical** — Build / Investigation / Impact return `ok=true` with `context_stale=true`; prior plan text remains visible.
3. **Exports blocked when stale** — `context_export`, `session_export_packet`, and workflow copy packets refuse with:

   > Atlas needs a refresh before exporting context. The repository changed after this plan was generated.

4. **Workflow context tracked** per export:

   - `recommended_files`, `inspected_files`, `likely_modified_files`
   - `generated_at`, `scan_id`, `memory_ref`, `scan_signature`, `refresh_generation`

5. **Status endpoint:** `GET /api/repositories/current/trust-status`

## P0 fixes (original + correction)

| ID | Fix |
|----|-----|
| 1 | Stale graph detection via per-file manifest + signature v2 (no auto-rescan) |
| 2 | Signature v2: git metadata + full indexed manifest hash |
| 3 | Memory tamper detection (`memory_hash`, `scan_signature`, `repo_id`) |
| 4 | `memory_persistence_status=failed` on write failure |
| 5 | Export validation: path, signature, memory, graph health, `memory_ref` |
| 6 | Weak-graph workflow gate (`unsupported_language_limited`) |
| 7 | `threading.RLock` on scan/select/rebuild/memory/export/workflow |
| 8 | **Targeted refresh** for plan-scoped file changes (user-initiated only) |

## Files

| File | Role |
|------|------|
| `jarvis_desktop/trust_integrity.py` | Signatures, staleness assessment, workflow context, export gates |
| `jarvis_desktop/targeted_refresh.py` | User-initiated partial graph/symbol/evidence refresh |
| `jarvis_desktop/repository_memory.py` | `refresh_generation`, memory hash, persist status |
| `jarvis_desktop/api.py` | Wire gates, `refresh_changed_files()`, `trust_integrity_status()` |
| `jarvis_desktop/server.py` | Routes for trust-status + refresh-changed-files |
| `jarvis_desktop/evidence_engine/symbol_index.py` | `remove_file()` for targeted symbol rebuild |
| `jarvis_desktop/tests/test_phase174b_trust_integrity.py` | 17 regression tests |

## Test results

```
py -3 -m pytest jarvis_desktop/tests/test_phase174b_trust_integrity.py -q   # 17 passed
py -3 -m pytest jarvis_desktop/tests/test_phase172a_memory_attack_surface.py -q
py -3 -m pytest jarvis_desktop/tests/test_phase172_memory_engine.py -q
```

## Remaining limitations

- Targeted refresh rebuilds **import-level** edges for touched Python modules; full call-graph depth for distant transitive deps is not recomputed.
- Non-Python file edits outside the plan always require full rescan.
- Git dirty/uncommitted changes outside the plan scope trigger `repo_changed_outside_plan` even when changes are unrelated to Atlas recommendations.
- UI buttons/messages are exposed via API flags; front-end wiring is out of scope for this phase.
- Concurrent edits during targeted refresh are not merged; user should refresh again if files change mid-refresh.
