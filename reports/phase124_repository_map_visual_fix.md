# Phase 124 — Repository Map Visual Fix

**Date:** 2026-06-02
**Goal:** Make the Repository Map presentable to a beta user — visible node
spheres and a clean, non-overlapping layout.
**Commit:** `phase124: fix Repository Map visual clarity for beta`

**Test status:** 351 passed (`py -m pytest jarvis_desktop/tests -q`), incl. 18 new
Phase 124 tests.

---

## 1. Root cause of invisible nodes (proven)

The app loaded **only** `3d-force-graph.min.js`, which does **not** expose a
global `THREE`. Verified live in a real browser:

```js
typeof ForceGraph3D  // "function"
typeof window.THREE  // "undefined"   ← the bug
```

Every custom-mesh code path in `universe.js` (`sphereNodeObject`, and the new
`makeNodeMesh`) begins with `if (typeof THREE === "undefined") return null;`.
With no global THREE, those returned `null`, so ForceGraph fell back to its
**default lit spheres** — which, under scene fog + lighting + the fit-to-bounds
camera distance, washed out to near-invisible dots. The edges (plain lines)
always render at ≥1px, so the user saw a **spiderweb of lines with no balls**.

This is why prior "numerically proven radius" fixes didn't help: the radius math
was correct, but the *meshes were never created*.

## 2. The fix — exact rendering path now used

1. **Expose a global `THREE`** (`index.html`): load `three@0.157.0` **before**
   `3d-force-graph`. Now `makeNodeMesh` actually runs.
2. **Explicit opaque, unlit node spheres** (`universe.js`):
   ```js
   fg.nodeThreeObject(n => makeNodeMesh(n)).nodeThreeObjectExtend(false)
   // makeNodeMesh: THREE.Mesh(SphereGeometry(r,18,14),
   //   MeshBasicMaterial({ color, transparent:false, opacity:1, fog:false }))
   ```
   - `MeshBasicMaterial` is **unlit** → constant bright colour regardless of lights/normals.
   - `fog:false` → never fades into the background.
   - radius `r = nativeDisplayRadius(n)` scales with the graph's spatial spread
     (largest ≈ bounds/9, floor ≈ 5) so important modules are visibly larger.
3. **Colour scheme** (`baseNodeColorHex`): normal = bright blue `#6f93ff`,
   hub = cyan, elevated risk = amber, high risk = red/pink, cycle = purple.
4. **Hover / selection / focus** (`refreshNodeMeshColors`, called from
   `syncHighlightVisuals`): selected → white + 1.6× scale; hover → light-cyan +
   1.32×; non-focused → dimmed; blast target → red. No opacity tricks that hide nodes.
5. **Lighter fog** (`FogExp2 0.0016 → 0.00035`) and a **tighter default camera**
   (`bounds*1.35` vs the old `bounds/0.86*1.75`) so spheres are large at first paint.

## 3. Proof that nodes are visible

Rendered the **actual technique** (global THREE + opaque `MeshBasicMaterial`
spheres + real demo-large graph data) in a real Chromium via the preview harness
and screenshotted:

- **Default module graph:** distinct coloured balls — large red/pink high-risk
  hubs, a cyan hub, bright-blue leaf modules, a purple cycle node — with edges as
  faint thin lines. Nodes clearly dominate. ✅ (not a spiderweb)
- **Selection/hover:** the selected node rendered as a large **white** sphere and
  the hovered node as an enlarged **light-cyan** sphere, both standing out. ✅

Audit (`auditRenderedMeshes`): meshes == nodes, radii 9.7–27.1 on a 313-unit
spread (2.9–8.7% of the scene). These are the in-conversation screenshots for
this phase.

## 4. Layout cleanup (before → after)

Removed a stack of **7 absolutely-positioned elements** that overlapped the graph
(`graph-head`, `graph-scale-header`, `massive-mode-banner`, `graph-entity-summary`,
`graph-render-diagnostics`, `graph-mode-badge`) and rebuilt the top as a clean
**flow header**:

- **Row 1:** `Repository Map · <repo>` + graph-health badge (left); controls
  (Module / Architecture / Hierarchy, Reset View, **Advanced ▾**) (right).
- **Row 2:** compact metrics strip — **Modules | Dependencies | Risk | Cycles | Coverage**.
- **Row 3:** concise warning — *"Graph coverage is partial. Most missing links are
  external or dynamic imports."* + a **Details** link (full text on demand).
- **Row 4:** compact one-line Massive Mode banner (button only when not already on
  the module graph).
- Then the graph fills the remaining space (`#graph3d{flex:1}`).

Screenshot of the rebuilt header (mocked with the real CSS) confirmed: no
overlapping cards, readable controls, concise warnings, no center badge. ✅

## 5. UI clutter removed (normal beta view)

- ❌ Floating center **"MODULE GRAPH"** badge → `display:none`.
- ❌ **Render-audit / debug overlay** → behind `ATLAS_SHOW_GRAPH_DEBUG=false`.
- ❌ Redundant **entity-summary** floating line → hidden.
- ❌ Long unresolved-import essay over the graph → concise + Details link.
- ❌ Decorative **Export Bundle / PNG / SVG / Screenshot / Tour** → grouped under
  **Advanced ▾**.
- ❌ Oversized massive banner → one compact line.
- Token-savings stays hidden unless verified (carried over from Phase 123).

## 6. Module list + inspector (carry the product if graph is hard to navigate)

- **Module list** (`moduleBrowsePanel`, below graph): searchable, columns
  **path · risk · fan-in · fan-out · subsystem**, click → selects + inspects the
  node (`selectModuleFromList → showNode`).
- **Inspector empty state**: "Select a module" + a **search box** + **Top hubs**
  and **Top risks** quick-pick lists, so the panel is useful before any click.

## 7. What remains weak

1. **Full-app, end-to-end visual QA** (header + cockpit + inspector + live graph in
   one window on FastAPI/Django/FINAL_ALGO_TRADER) was not possible here — the
   preview sandbox can't reach the local backend. The *rendering technique* and the
   *layout* were each proven in isolation; a local human pass is the final gate.
2. **THREE via CDN** — for an offline desktop beta, bundle `three` + `3d-force-graph`
   locally instead of unpkg (today the graph already requires network).
3. **Cockpit** still shows some metrics that now also appear in the header strip;
   a further de-duplication pass would tighten it.
4. **Subsystem/hierarchy** nodes use the same sphere path (fine), but their
   importance→size mapping is coarser than the module view.

## 8. Screenshot checklist (for local acceptance run)

| # | View | Must show |
|---|------|-----------|
| 1 | FINAL_ALGO_TRADER — Module Graph (default) | ~230 visible spheres, varied size/colour, not lines-only |
| 2 | FINAL_ALGO_TRADER — node selected | white enlarged sphere + populated inspector |
| 3 | Architecture Overview | subsystem spheres, clean header |
| 4 | Django — Module Graph | dense but visible spheres |
| 5 | FastAPI — Module Graph | visible spheres, partial-coverage badge + concise warning |

Verified equivalents (demo-large data, real Chromium) for #1 and #2 are captured
in this phase's conversation; #3–#5 need the local backend.
