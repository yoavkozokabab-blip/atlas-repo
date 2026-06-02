# Phase 116B — Graph Hover Performance Fix

## Problem

On large repositories (e.g. VS Code with 8k+ modules), moving the mouse over graph nodes caused severe UI lag. Root cause: **`onNodeHover` re-bound ForceGraph3D accessors on every hover** (`nodeColor`, `linkColor`, `linkWidth`, `linkDirectionalParticles`, `nodeLabel`) and scanned **all links** via `graph.links.forEach` to find neighbors.

## Fix (frontend only)

### `universe.js`

| Change | Detail |
|---|---|
| **Precomputed adjacency** | `buildAdjacencyMaps()` once after graph load: `nodeId → Set(neighborIds)` + hover tooltip metadata |
| **One-time accessors** | `installGraphAccessors()` registers color/width/particle functions that read mutable `U.highlightState` |
| **Hover path** | `scheduleHoverUpdate()` — `requestAnimationFrame`, skip same `lastHoverId`, `syncHighlightVisuals()` → `fg.refresh()` only |
| **No `graphData()` on hover** | Graph topology unchanged during hover |
| **Selection vs hover** | Hover: highlight + tooltip string. Click/`showNode`: full inspector via `applySelectionHighlight` |
| **Large graph mode** | `nodes > 1000`: cap hover neighbors at **100**, disable pulse loop & link particles |
| **Perf logging** | `enablePerfLogging(true)` → warn if hover >50ms, debug if >16ms |

### `app.js`

- Inspector / `renderModuleInspector` remains **click-only** (no change on hover).
- `STATE.hoverNodeId` updated in lightweight `onNodeHover` callback.

## Before / after (expected)

| Behavior | Before | After |
|---|---|---|
| Hover handler | Re-bind 6+ accessors + O(E) link scan | O(1) id check + O(k) neighbors (k≤100) + `refresh()` |
| `graphData()` on hover | No | **No** |
| Same node re-hover | Full rework | **Ignored** |
| 8k node pulse animation | Always on | **Off** when large |
| Link particles on hover | Reconfigured every hover | **Off** when large |

## Tests

- `jarvis_desktop/tests/test_phase116b_graph_hover_performance.py`

## Manual verification

1. Scan `C:\J.A.R.V.I.S\vscode`
2. Open Command Center graph
3. Hover multiple nodes — UI should stay responsive
4. Click node — inspector opens, camera flies, selection highlight applies
5. Optional: `JARVIS_UNIVERSE.enablePerfLogging(true)` in browser console

## Files

- `jarvis_desktop/static/universe.js` — primary fix
- `jarvis_desktop/static/app.js` — comment / click-only inspector unchanged
- `jarvis_desktop/tests/test_phase116b_graph_hover_performance.py`
