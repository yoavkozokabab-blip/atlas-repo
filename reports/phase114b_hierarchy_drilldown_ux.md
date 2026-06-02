# Phase 114B — Hierarchy Drilldown UX

Status: complete

## Goal

Improve Massive Repository Mode usability with practical drilldown navigation:

Subsystem -> Package -> Module -> File

without changing Builder Core analysis semantics.

## Delivered

- Breadcrumb above hierarchy graph:
  - `Repository / subsystem / package / module`
  - Click any crumb to return to that scope.
- Node drilldown behavior:
  - subsystem node click -> package level
  - package node click -> module level
  - module node click -> opens Module Inspector
- `Back to overview` button:
  - returns to top-level overview (`subsystem` graph view)
- Level counts shown in UI (`hierarchyCounts`):
  - files
  - modules
  - edges
  - risk hotspots
- Responsive behavior preserved:
  - hierarchy uses existing progressive graph renderer
  - no full module flood required before drilldown

## Backend updates

`current_hierarchy_graph()` now returns `counts` for each level:

- subsystem: totals from current scan/index
- package: package aggregate counts + package-level edge aggregation
- module: selected module/file subset counts

## Frontend updates

New hierarchy state/navigation helpers:

- `navigateHierarchy(level, parent)`
- `renderHierarchyBreadcrumb()`
- `updateHierarchyCounts(graph)`
- `handleHierarchyClick(node)`
- `backToOverview()`

Graph view option `hierarchy` now drives level-aware API calls and drilldown transitions.

## Files changed

- `jarvis_desktop/api.py`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/styles.css`
- `jarvis_desktop/tests/test_phase114_massive_repository_mode.py`

## Tests

Added/extended tests for:

- hierarchy level counts
- hierarchy navigation state markers in frontend

Run:

```powershell
py -m pytest jarvis_desktop/tests/test_phase114_massive_repository_mode.py jarvis_desktop/tests/ -q
```

