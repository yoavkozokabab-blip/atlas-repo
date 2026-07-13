# Three.js Scene Plan — The Constellation

One **persistent canvas** mounted behind all home content (`position: fixed`, `z-index: 0`,
`pointer-events: none` except the hero interaction zone). It has **scene states** driven by a
single scroll progress value (0→1). Content sits in normal DOM above it (`z-index: 1`).

Stack: vanilla `three` in a client-side React effect, with scroll from Lenis + GSAP
(see motion-system.md). React 19.

## Data model (deterministic, seeded — no per-frame randomness)

Generate once with a seeded PRNG (`mulberry32`, fixed seed) so renders are reproducible:
- `N` nodes. Desktop 260, tablet 160, mobile 70, low-power 0 (static fallback).
- Each node: `{ id, homePos:Vec3 (clustered), noisePos:Vec3 (scattered), cluster, kind:
  'file'|'symbol'|'concept', label?:string, importance:0..1 }`.
- Clusters = 5–7 modules positioned on a loose disc with depth; nodes gaussian-scattered around
  cluster centroids for `homePos`; `noisePos` = homePos + large random offset (the "raw repo").
- Edges: intra-cluster (k-nearest within cluster) + a few labeled **bridge** edges between
  clusters. Precompute index pairs once. ~1.6×N edges max.
- The **core**: a single faceted icosahedron lattice at origin-ish, slightly off-center per the
  asymmetric composition.

## Rendering (must be cheap — see performance-budget.md)

- Nodes: **one `InstancedMesh`** (octahedron/tetra, 8–12 tris), per-instance matrix + color.
  Active/important nodes tinted toward `--accent`; dormant toward `--accent-deep`/grey.
- Edges: **one `LineSegments`** with `BufferGeometry`; per-vertex color alpha encodes active vs
  dormant. Bridges brighter. Update positions in-place (no re-alloc) only while state morphs.
- Core: low-poly icosahedron, `MeshStandardMaterial` dark with subtle emissive accent + a thin
  wireframe overlay. Slow rotation only (≤0.05 rad/s), never a "spinning object" as the subject.
- Labels: DOM overlays for ~8 mono file labels max, fading in on the "scan" state.
  Cap to avoid draw-call/DOM cost; hidden on mobile.
- Lighting: 1 hemi + 1 key directional. No dynamic shadows. Fog = `--bg-0`, near/far tuned so
  far nodes dissolve into the void.
- Post: **AO off**. At most a *gentle* Bloom (luminanceThreshold high ~0.9, intensity ≤0.4) so
  only accent core/nodes bleed — desktop only, disabled on mobile & reduced-motion. No heavy DOF.

## Scene states (lerped by scroll `p`, see scroll-storyboard.md)

| p | State | Node positions | Edges | Core | Camera |
|---|---|---|---|---|---|
| 0.00 | **Raw** | `noisePos` (scattered), dim, dormant colors | invisible | faint | wide, drifting, deep |
| 0.20 | **Scan** | lerping noise→home; a scan plane sweeps, nodes light as it passes | fading in per cluster | forming | push in slightly |
| 0.45 | **Memory** | `homePos` (clustered), important nodes accent | full, bridges bright | solid, emissive | orbit toward core |
| 0.65 | **Agent** | clusters hold; a lit path routes core→selected nodes (retrieval) | retrieval path pulses | active | frame core + path |
| 0.82 | **Persist** | subtle "breathing"; a session-boundary ripple passes, map survives intact | steady | steady glow | slow pull back |
| 1.00 | **Converge** | nodes gather toward the core → resolves to the Atlas mark | collapse to core | dominant, centered | centered, still |

Hero (before scroll) = an idle loop of the **Memory** state with slow camera drift + mouse
parallax, and a one-time **crystallize** intro (noise→home over ~2.2s ease) on load.

## Interaction

- Mouse/gyro parallax: camera offset ±(0.3,0.2) eased; depth layers respond through the vanilla scene loop.
- Hover a node (hero only, pointer-events zone): node scales 1.4×, its edges brighten, a mono
  label + relevance chip appears. Throttled raycast (every ~4th frame, small candidate set).
- All interaction is non-essential; keyboard/content path is complete without it.

## Loading & failure

- `Suspense` fallback = the **loading sequence** (see below); hero text/CTA render immediately
  in DOM regardless (never blocked by WebGL).
- `onError` / no-WebGL / `deviceMemory<4` / reduced-motion → render a **static pre-rendered
  constellation frame** (WEBP) with a very slow CSS parallax. No blank canvas ever.
- Pause `useFrame` when canvas is offscreen (IntersectionObserver) and on `visibilitychange`.

## Loading sequence (premium, honest — no fake delay)

Wordmark + a scan line + mono status stepping through real stages only as assets resolve:
`Mapping repository → Resolving symbols → Building memory → Ready`. If load is fast, cut
straight through. Progress reflects actual asset/geometry readiness, not a timer.
