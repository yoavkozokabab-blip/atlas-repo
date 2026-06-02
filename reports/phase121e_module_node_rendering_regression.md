# Phase 121E — Module Node Rendering Regression

**Date:** 2026-06-02  
**Symptom:** Module graph shows correct counts (e.g. 942 modules, 1832 edges) and visible edges, but **module nodes appear invisible**.  
**Data pipeline:** Confirmed correct in Phase 121C.

---

## Root cause

**World-space scale mismatch** between galaxy layout and `SphereGeometry` radius.

| Layer | Span / size |
|-------|-------------|
| Galaxy layout (`galaxy_x/y/z`) | ~100–300 world units across the scene |
| Phase 121B `moduleNodeScale` | `0.36 × √visual_size` → **~1–2 unit** radius |
| Subsystem overview (11 nodes) | `~0.48 × √visual` × larger hubs → **~6–14 units** (visible) |

Edges are drawn between node **positions**, so they span the full scene and look correct. Module meshes were **sub-pixel** at the fitted camera distance — not null, not transparent-zero, simply too small to see.

Secondary factors (not primary):

- `nodeVal` used `hub × visual_size` (up to ~95) while mesh radius was ~1 — **hover/click still worked** on invisible nodes via large interaction volume.
- Glow shell at `1.65×` radius with transparency did not fully occlude; size was not the main issue.
- `fg.nodeOpacity` dimming to `0.14` on non-focus nodes only applies during hover/selection (116B); idle opacity was `0.97` but irrelevant when geometry was invisible.

**Failing code path:** `universe.js` → `moduleNodeScale()` → `sphereNodeObject()` → `SphereGeometry(scale, …)` inside `buildGraph()` → `nodeThreeObject(n => sphereNodeObject(n))`.

---

## Fix (Phase 121E)

1. **`computeSceneNodeScale(nodes)`** — derives multiplier from galaxy spatial extent (`max radius / 82`, clamped 1.15–6.5).
2. **`moduleNodeScale`** — `sceneScale × (0.95 + 0.42×√visual)` clamped to **1.85–22** world units; hubs scale up.
3. **`nodeVal`** — matches mesh radius (`moduleNodeScale` / `subsystemNodeScale`) for consistent picking.
4. **Materials** — opaque Phong core (`transparent: false`, `opacity: 1`); softer glow at **1.22×** radius, `depthWrite: false`.
5. **Camera** — `near=0.8`, `far=25000`; stronger ambient/key lights with longer range.
6. **Collision** — `forceCollide` on module graphs ≤1500 nodes (radius ≈ mesh) to reduce overlap without 116B hover changes.

Subsystem / hierarchy paths use the same helpers with `subsystemNodeScale` adjusted by scene scale — overview modes unchanged in behavior.

---

## Verification

| Check | Result |
|-------|--------|
| `nodeThreeObject` returns `null` only if THREE missing or invalid scale | ✓ guarded |
| Module radii at galaxy span | ✓ ~2–12+ units typical (was ~1–2) |
| Phase 116B hover (RAF, no graphData on hover) | ✓ unchanged |
| `test_phase121e_module_node_rendering.py` | ✓ pass |
| Full `jarvis_desktop/tests` | ✓ 275+ pass |

### Lab scale example (ts_sample_repo, module view)

- Layout span: ~400+ units  
- `sceneNodeScale`: ~4.9  
- Typical module radius: ~5–8 units (visible)

### Operator confirmation (required for sign-off)

After pull, scan and open **Module Graph**:

| Repo | Expect |
|------|--------|
| FINAL_ALGO_TRADER | ~200+ visible spheres |
| FastAPI / Django | full module graph visible |
| VS Code | module or hierarchy per mode; module nodes visible when selected |

---

## FPS / performance impact

| Area | Impact |
|------|--------|
| Geometry | Slightly larger meshes; fewer transparent layers on core |
| `forceCollide` | Enabled for module graphs ≤1500 nodes (light strength 0.28) |
| Glow | Smaller shell (1.22× vs 1.65×) |
| Hover | No change to adjacency / RAF path |

Large graphs (942 modules): no collide force ( >1500 threshold uses null collide ) — same as before for very large repos.

---

## Before / after (description)

| Before | After |
|--------|-------|
| Edge web visible, no perceptible nodes | Distinct spheres at each module position |
| Hover hits “empty” space | Hover highlights visible sphere |
| Hub nodes same size as leaves | Hubs larger via `is_hub` / visual_size |

Screenshots: capture Module Graph for FINAL_ALGO_TRADER and FastAPI in desktop app post-fix.

---

## Files changed

- `jarvis_desktop/static/universe.js`
- `jarvis_desktop/tests/test_phase121e_module_node_rendering.py`
