# Phase 121F — Force Visible Module Nodes Hotfix

**Date:** 2026-06-02  
**Symptom:** Module graph shows 942/942 modules and 1832 edges (lines visible) but module spheres still invisible after Phase 121E custom-mesh scaling.

---

## Root cause (confirmed)

Phase 121E increased **custom** `SphereGeometry` radii in `nodeThreeObject()`, but **ForceGraph3D does not reliably display custom `nodeThreeObject` meshes** at galaxy-scale coordinates in this app build (942-node graphs). Edges use node positions; custom meshes were created but not perceptible (library scaling / material refresh / group handling).

**Fix:** For `view === module`, bypass custom meshes and use **built-in ForceGraph3D spheres** via `nodeVal` + `nodeRelSize`, which are known to render.

---

## Implementation

### Safety mode (`MODULE_FORCE_VISIBLE = true`)

When module graph (non-subsystem nodes):

| Setting | Value |
|---------|--------|
| Custom `nodeThreeObject` | **Disabled** |
| `nodeRelSize` | **7** |
| `nodeVal` | `(desiredRadius / relSize)³` so display radius ≥ **5** world units |
| Glow / halos / torus | **Off** (custom path not used) |
| `nodeOpacity` (idle) | **1.0** (hover dim floor **0.55**, not 0.22) |
| Pulse emissive loop | **Off** in force-visible mode |

Subsystem / architecture overview still uses `sphereNodeObject()` (beauty path).

### Runtime audit (console + overlay)

After graph load:

```
[Atlas graph] render audit { nodes, meshes, minRadius, maxRadius, forceVisibleModule }
```

Warns if `meshes !== nodes.length` or `minRadius < 5`.

**UI overlay** (`#graphRenderDiagnostics`, module view only):

- Nodes: N  
- Meshes: N  
- Min radius: X  
- Max radius: Y  
- `force-visible mode`

### Files

- `jarvis_desktop/static/universe.js`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/styles.css`
- `jarvis_desktop/tests/test_phase121f_force_visible_module_nodes.py`

---

## Tests

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase121f_force_visible_module_nodes.py -q
```

Full desktop suite: green.

---

## Manual acceptance

1. Scan **FINAL_ALGO_TRADER** (or repo with 200–1000 modules).  
2. Open **Module Graph**.  
3. Expect **hundreds of visible cyan/blue spheres** on the edge web.  
4. Diagnostics overlay: `Meshes` = `Nodes`, `Min radius` ≥ 5.  
5. Hover/click still highlights neighbors (116B path unchanged).

### Before / after

| Before | After |
|--------|-------|
| Edge web only | Edge web + visible spheres |
| Diagnostics N/A | Nodes/Meshes/Min/Max radius shown |

**Screenshot:** Operator capture Module Graph after scan — attach to release notes.

---

## Follow-up (beauty re-enable)

1. Set `MODULE_FORCE_VISIBLE = false` in a controlled experiment.  
2. Debug why custom `nodeThreeObject` groups fail at scale (library version, `refresh()` opacity, group scale).  
3. Re-introduce glow/halo only after core visibility is proven in custom path.

---

## Performance

| Item | Impact |
|------|--------|
| Native spheres | Lower GPU cost than custom Groups + glow |
| No pulse loop | Slight CPU savings on large graphs |
| Hover | Unchanged (adjacency + RAF) |
