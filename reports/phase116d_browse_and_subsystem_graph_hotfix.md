# Phase 116D — Browse Endpoint Hotfix + Subsystem Graph Visual Fix

**Date:** 2026-06-02  
**Product version:** `phase116d-browse-subsystem-graph`

## Summary

Two desktop blockers were addressed without changing Builder Core analysis or dependency extraction:

1. **Browse folder** — `POST /api/system/browse-folder` is registered, localhost-only, and wired from Home → Browse → validate.
2. **Subsystem graph** — node sizes use log-scaled, clamped radii; layout spacing and collision forces prevent giant overlapping cyan hubs.

## Part A — Browse

### Root cause (user-visible failure)

`Unknown endpoint: POST /api/system/browse-folder` occurs when the running server build does not include the route (e.g. older staging/installer). The current `jarvis_desktop` tree already registers the handler in `server.py` and dispatches via `system_browse.browse_folder()`.

### Implementation

| Layer | File | Behavior |
|-------|------|----------|
| Route | `jarvis_desktop/server.py` | `POST /api/system/browse-folder` → `browse_folder()`; 403 if not loopback |
| Picker | `jarvis_desktop/system_browse.py` | `tkinter.filedialog.askdirectory()` in a daemon thread; 120s timeout |
| UI | `jarvis_desktop/static/app.js` | `browseRepoFolder()` → fill `repoPath` → `validateRepoPath(true)`; cancel is silent |
| Errors | `system_browse.py` | Unsupported/headless: `ok: false`, `code: unsupported_browse_dialog`, `message: "Paste the folder path manually."` |

### Response shapes

- **Selected:** `{ "ok": true, "supported": true, "cancelled": false, "path": "<abs path>" }`
- **Cancel:** `{ "ok": true, "supported": true, "cancelled": true, "path": null }`
- **Unsupported:** `{ "ok": false, "code": "unsupported_browse_dialog", "message": "Paste the folder path manually.", ... }`

No shell commands are executed; only the OS folder dialog path is returned.

## Part B — Subsystem graph visuals

### Root cause

Subsystem nodes were sized linearly from `module_count` (up to **28**), then layout set **every** subsystem as `is_hub` with `hub_scale` up to **5.5** (`2.5 + module_count * 0.05`). `universe.js` multiplied hub scale × √size × icosahedron geometry → unusable overlapping blobs.

### Fix

**Backend (`api.py`):**

- `_subsystem_visual_size()` — `visual = clamp(5, 14, 4 + log1p(module_count) * 1.35)`, `hub_scale = clamp(1.15, 2.5, 1.1 + log1p * 0.2)`; small bump for top-risk rank ≤ 3.
- `_apply_subsystem_galaxy_layout()` — wider ring radius, preserves computed `hub_scale` (no linear blow-up).
- Payload tags: `graph_view: "subsystem"`, `visual_size` on every node.

**Frontend (`universe.js`):**

- Subsystem-specific `subsystemNodeScale()`, `nodeVal`, opacity, labels (`label · N modules`).
- Stronger charge, longer link distance, `d3.forceCollide` in subsystem mode.
- Top-risk emphasis via **outline** (line segments), not size inflation.
- `fitGraphCamera()` / `resetGraphView()` — auto-fit when graph loads; module graph forces unchanged.

**State (`app.js`):** `setGraphView` clears `STATE.graph`, `STATE.graph3d`, and `STATE.graphPerf` to avoid stale graph data when switching modes.

## Part C — Tests

- `tests/test_phase116c_native_browse_flow.py` — updated unsupported code assertion.
- `tests/test_phase116d_browse_and_subsystem_graph_hotfix.py` — browse mocks, route audit, visual size clamps, log growth, frontend/universe helpers.

Run:

```bash
cd local_jarvis
python -m pytest jarvis_desktop/tests/test_phase116c_native_browse_flow.py jarvis_desktop/tests/test_phase116d_browse_and_subsystem_graph_hotfix.py jarvis_desktop/tests/test_phase107_desktop_api.py -q
```

## Manual verification (screenshots)

Capture after restarting the desktop app from the current `local_jarvis` source (not an old `staging/` build):

1. Home → **Browse** opens native folder picker.
2. Selected path appears in repo input and passes validate.
3. Command Center → **Subsystem** view for:
   - `FINAL_ALGO_TRADER`
   - `django` (`C:\J.A.R.V.I.S\django`)
   - VS Code workspace (post Phase 116 TS graph scan)

Expected: readable-sized nodes, labels visible, no giant overlapping cyan spheres; camera auto-fits on load and after switching graph mode.

## Acceptance

| Criterion | Status |
|-----------|--------|
| No Unknown endpoint on Browse (current server) | ✓ route + tests |
| Folder picker selects repo path | ✓ |
| Subsystem graph readable / spaced | ✓ log + clamp + collide |
| Module graph unchanged | ✓ subsystem branch only |
| Builder Core analysis unchanged | ✓ desktop/UI only |
