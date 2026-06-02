# Phase 108 — Real Dependency Graph

**Product version:** `phase108-real-graph`  
**Verdict:** Real Builder Core graph visualization **implemented**; placeholder topology removed.

## Problem

The Command Center 3D graph looked nearly identical across repositories because:

- Only the top **400 fan-in modules** were rendered (large repos truncated the same way visually).
- Risk coloring used scores for only the **top 12** ranked modules; most nodes shared the same blue fan-in heuristic.
- Node size followed **fan-in**, not architectural risk.
- **`STATE.graph` was not cleared** on rescan, so a second repository could show the first repo’s graph.
- Fixed camera distance (`z=420`) and default forces produced similar silhouettes.

## Solution

Consume existing Builder Core outputs only (`depgraph.build_graph`, `architectural_risk.rank_modules`, subsystem discovery). No analysis logic changes.

### Backend (`jarvis_desktop/api.py`)

- Rank up to **5000** modules for per-node risk scores (all production modules on typical repos).
- Module graph includes **all modules** (cap 5000), not fan-in top-400.
- Node fields: fan-in/out, subsystem, LOC, risk score/rank/tier, cycle membership, size.
- Link fields: `weight` + `opacity` from target fan-in.
- **Subsystem graph** collapses modules into subsystem hubs with aggregated cross-subsystem import edges.
- `GET /api/repositories/current/graph?view=module|subsystem`

### Frontend (`jarvis_desktop/static/app.js`)

- Force-directed layout via **3d-force-graph** with tuned charge/link distance.
- Node color: blue normal · orange elevated · red top risk · purple cycle.
- Node size from risk score (+ fan-in contribution).
- Hover highlights incoming/outgoing neighbors; click opens detail panel.
- Module / subsystem toggle in Command Center.
- Progressive loading via `requestAnimationFrame` for large graphs.
- Lazy labels (shown on hover only).
- Clear graph state on each scan; auto-open Command Center after scan (unchanged flow).

## Validation metrics

| Repository | Modules | Edges | Module nodes | Module links | Subsystem nodes | Subsystem links | Scan (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Synthetic small | 3 | 2 | 3 | 2 | 2 | 1 | 26 |
| Synthetic wide | 13 | 12 | 13 | 12 | 13 | 12 | 21 |
| **local_jarvis** | **689** | **1695** | **689** | **1695** | **42** | **133** | **11593** |

Node/link counts **match** scan totals on all tested repositories (no fabricated edges).

Full JSON: `reports/phase108_real_dependency_graph_metrics.json`

## Before vs after

| Aspect | Before (Phase 107) | After (Phase 108) |
|---|---|---|
| Data source | Real depgraph (partial display) | Real depgraph (full up to 5000) |
| Display cap | 400 modules by fan-in | 5000 modules by risk+fan-in |
| Risk coloring | Top 12 only | All ranked modules |
| Node size | Fan-in | Risk score |
| Layout | Default + fixed camera | Tuned d3-force + scaled camera |
| Subsystem view | No | Yes |
| Rescan bug | Stale graph possible | Cleared each scan |
| Tests | Phase 107 API | + Phase 108 differentiation tests |

## Performance

- **local_jarvis:** ~11.6s scan (unchanged — depgraph build), graph payload build negligible.
- Progressive front-end load targets 500–5000 nodes; 689-node repo loads in one chunk (<1200 threshold).
- Hover labels rendered only for focused node (lazy).

## Screenshots

UI screenshots were **not captured in this environment** (headless test run only). To view the graph:

```bash
cd local_jarvis
py run_jarvis_desktop.py
```

Scan `local_jarvis` and a small folder; module count, edge count, and topology should differ visibly.

## Limitations

- Repos with **>5000** production modules truncate display (sorted by risk, not fan-in only).
- Subsystem graph for wide repos with one module per folder may resemble module graph until cross-subsystem edges dominate.
- Impact simulator still uses reverse-import heuristic (Phase 94B transitive engine not wired).
- 3D library loaded from CDN; offline mode falls back to text hub list.
- Builder Core analysis logic intentionally unchanged.

## Files modified

- `jarvis_desktop/api.py`
- `jarvis_desktop/server.py`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/styles.css`
- `jarvis_desktop/tests/test_phase107_desktop_api.py`
- `jarvis_desktop/tests/test_phase108_real_dependency_graph.py`
- `reports/phase108_real_dependency_graph.md`
- `reports/phase108_real_dependency_graph_metrics.json`

## Tests

```text
py -m pytest jarvis_desktop/tests/test_phase108_real_dependency_graph.py jarvis_desktop/tests/test_phase107_desktop_api.py -q
16 passed
```
