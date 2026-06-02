# Phase 115B — Dependency Graph Performance Optimization

## Summary

Django-sized scans are now usable. The primary bottleneck was **exhaustive import-cycle enumeration** on dense graphs (appeared hung for 15+ minutes), compounded by **O(n²) text lookup**, **double AST parsing** in cross-file resolution, and **misleading synthetic UI progress**.

After optimization, a full Django desktop scan completes in **~15s** with an **import-level graph in ~1.3s** (massive tier). Full module graph builds in **~8.6s** when requested.

## Before / After (Django `C:\J.A.R.V.I.S\django`)

| Metric | Before (115A) | After (115B) |
|---|---:|---:|
| Diagnostic timeout | 900s (incomplete) | — |
| Scan total | >900s (no completion) | **15.05s** |
| `building_dependency_graph` | >900s (stuck) | **1.30s** |
| Graph detail | full (implicit) | **imports** (massive tier) |
| Modules in graph | — | **911** |
| Import edges | — | **2916** |
| UI progress | Synthetic timer (~80% misleading) | **Backend `scan-status` polling** |
| Full module graph (on demand) | N/A | **~8.6s** (`detail=full`) |

Artifacts:
- `reports/phase115b_django_graph_before.json`
- `reports/phase115b_django_scan_after.json`

## Root Cause

1. **`_import_cycles` DFS** in `builder_core/bug_intelligence/depgraph.py` — on Django’s dense import graph (~3k resolved import edges), cycle enumeration explored the full adjacency repeatedly and did not return within practical time.
2. **`dict(file_list)[rel]` inside the per-file loop** — O(n²) file-text lookups during full graph expansion.
3. **`cross_file.build_project_context(list(parsed))`** — passed AST trees where source text was expected; cross-file context was rebuilt incorrectly and full builds paid redundant parse/index cost. Fixed via `build_project_context_from_parsed`.
4. **Desktop UX** — `app.js` advanced stages on a fixed `setInterval`, not backend state.

## Changes

### Builder Core (`depgraph.py`, `cross_file.py`)

- Import-only fast path: `DETAIL_IMPORTS` / `build_graph(..., detail=...)`.
- Time budgets via `time_budget_sec` + `deadline` with partial/degraded return (`jarvis_timed_out`, `jarvis_partial`).
- Cached qualnames per file; single `text_by_rel` map.
- Shared `_append_module_import_edges` helper.
- `build_project_context_from_parsed` — no second `ast.parse` pass.
- Large-repo cycle policy: skip enumeration when import edges > 3000; bounded sampling between 800–3000.
- Deadline checks while reading source files.

### Desktop (`graph_build.py`, `api.py`, `app.js`, `server.py`)

- Tiered build plan: massive → imports graph first + lazy full; medium/small → full graph with optional 180s cap.
- `build_scan_graph()` wrapper used by `scan_repository()`.
- `POST /api/repositories/current/build-full-graph` for lazy full module graph.
- `scan_status()` exposes `progress_pct`, `stage_label`, graph sub-progress.
- Frontend polls `/api/repositories/current/scan-status` during scan (no synthetic stage timer).

## Targets vs Results

| Target | Result |
|---|---|
| Pre-scan < 5s | **~0.8s** (estimate + validate) |
| Hierarchy/subsystem graph < 60s | **~1.3s** (import-level graph) |
| Full module graph < 180s or degraded | **~8.6s** full build; budget + partial path available |

## Files / Functions

| Area | File | Functions |
|---|---|---|
| Cycle blow-up | `builder_core/bug_intelligence/depgraph.py` | `_import_cycles`, `_import_cycles_bounded`, `compute_statistics` |
| Graph tiers | `builder_core/bug_intelligence/depgraph.py` | `build_graph`, `build_graph_from_files`, `_build_imports_detail_graph` |
| Cross-file reuse | `builder_core/bug_intelligence/cross_file.py` | `build_project_context_from_parsed` |
| Scan policy | `jarvis_desktop/graph_build.py` | `graph_build_plan`, `build_scan_graph` |
| Scan integration | `jarvis_desktop/api.py` | `scan_repository`, `scan_status`, `build_full_module_graph` |
| UI progress | `jarvis_desktop/static/app.js` | `pollScanProgress`, `applyScanStatus` |

## Tests

- `builder_core/tests/test_phase115b_depgraph_performance.py`
- `jarvis_desktop/tests/test_phase115b_graph_performance.py`

## Follow-up (not in 115B)

- Re-enable bounded cycle reporting for large repos via Tarjan SCC (single pass).
- Parallel file parse (optional) for repos >2k modules.
- Show `full_graph_pending` banner in Command Center when hierarchy view uses import-only graph.
