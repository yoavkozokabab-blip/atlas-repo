# Phase 121B — Repository Universe Visual Rebuild

**Date:** 2026-06-02  
**Product version:** `phase121b-repository-universe-visual`  
**Scope:** Command Center visualization only — Phase 116B hover/selection performance architecture preserved.

---

## Summary

Restored visual presence and repository-scale storytelling in the 3D graph without reverting Phase 116B optimizations (adjacency precompute, RAF hover, accessor install-once, no `graphData()` on hover).

| Requirement | Implementation |
|-------------|----------------|
| Module graph default | `resolveDefaultGraphView()` — module if &lt; 5000 modules, else hierarchy; never auto-subsystem |
| Node presence | `log(fan_in + fan_out + 1)` sizing, clamped 5.5–28; stronger emissive + halo meshes |
| Galaxy universe | Hub at cluster center, members on rings, leaves on outer ring (`galaxy_role`) |
| Camera | `fitGraphCamera()` uses spatial bounding radius (~86% fill) |
| Massive repos | Architecture overview clusters (Workbench, Platform, Extension Host, …) + hierarchy default |
| Visual depth | Fog, glow shells, focus fade (`nodeOpacity` / `linkOpacity`), pulse particles on focus only |
| Inspector | Selection/hover neighbor focus + dim non-neighbors (no graph rebuild) |
| Scale header | `#graphScaleHeader` — modules, dependencies, risk, cycles |

---

## Tests run

| Suite | Result |
|-------|--------|
| `test_phase121b_repository_universe_visual.py` | **9 passed** |
| `test_phase114_massive_repository_mode.py` (updated) | **pass** |
| `test_phase116b_graph_hover_performance.py` | **pass** |
| Full `jarvis_desktop/tests` | **261 passed** |

---

## Performance (lab)

| Metric | Target | Notes |
|--------|--------|-------|
| Hover path | &lt; 16ms typical | Still `scheduleHoverUpdate` + `fg.refresh()` only |
| Hover | No `graphData()` in hover handler | Verified by tests |
| Large graph neighbors | Cap 100 hover / 250 select | Unchanged from 116B |
| Graph build (ts_sample) | ~module graph API &lt; 50ms | Payload generation only |
| Browser FPS | 60 FPS target | Requires live session; no regression in chunk loader |

Run payload benchmarks: `py -3 scripts/phase121b_visual_metrics.py`

**Memory:** No duplicate adjacency on hover; glow meshes add one low-poly shell per node (visual tradeoff).

---

## Before / after screenshots (operator)

Capture from Command Center after scan:

| Repository | Suggested view | Path |
|------------|----------------|------|
| FINAL_ALGO_TRADER | Module graph | User repo |
| FastAPI | Module graph | `demo_repos/fastapi` or local clone |
| Django | Module graph | Local clone |
| VS Code | Hierarchy + Architecture overview | Massive mode |

Use **Screenshot** mode in graph toolbar; save PNG via **PNG** export.

---

## Files changed

- `jarvis_desktop/api.py` — sizing, galaxy layout, cluster overview, default graph policy
- `jarvis_desktop/static/universe.js` — scale, glow, camera, focus fade, particles
- `jarvis_desktop/static/app.js` — default view, scale header, cluster drill-down
- `jarvis_desktop/static/index.html` — scale header, overview label
- `jarvis_desktop/static/styles.css` — scale header styles
- `jarvis_desktop/tests/test_phase121b_repository_universe_visual.py`
- `jarvis_desktop/tests/test_phase114_massive_repository_mode.py`
- `jarvis_desktop/tests/test_phase116d_browse_and_subsystem_graph_hotfix.py`

---

## Caveats

1. Repositories with &gt; 5000 modules still cap module graph display at 5000 highest-risk nodes.
2. Architecture cluster names are heuristic (path/subsystem patterns), not MSBuild/VS Code manifests.
3. `nodeThreeObject` glow adds GPU geometry — very large graphs (&gt;1000 nodes) should use hierarchy/overview first.
4. Screenshot before/after assets are not checked into the repo; capture during release QA.

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Premium visual presence (hubs, glow, scale header) | ✓ |
| Module default for normal repos | ✓ |
| Hierarchy default for 5000+ modules | ✓ |
| Subsystem never forced as default | ✓ |
| 116B hover performance preserved | ✓ |
| All desktop tests green | ✓ (261)
