# Performance Budget

Advanced-looking, not irresponsible. Budgets are enforced, not aspirational. Measure — never
claim success without numbers (Lighthouse + Web Vitals + WebGL FPS + bundle report).

## Targets

| Metric | Target |
|---|---|
| LCP (hero text/CTA) | < 2.0s desktop, < 2.5s mobile — text is DOM, never blocked by WebGL |
| CLS | < 0.02 (fonts via next/font, reserved media boxes) |
| INP | < 200ms |
| Initial JS (before scene) | < 180KB gz for the hero text/nav shell; scene code-split & lazy |
| Scene chunk (three only) | dynamic `import()`, loaded after first paint; target stays lean by avoiding R3F/Drei/postprocessing |
| WebGL frame | 60fps desktop, ≥ 30fps mobile; adaptive DPR drops quality before dropping frames |
| Lighthouse Perf | ≥ 90 desktop, ≥ 80 mobile (home); ≥ 95 on content pages (no canvas) |

## Tactics

- Hero copy + nav + CTA are server-rendered DOM. The `<Canvas>` is `next/dynamic` (`ssr:false`)
  and mounts after hydration; `Suspense` fallback = loading sequence. Never block the hero.
- Content pages (product, download, legal, docs…) carry **no** three.js — the persistent canvas
  is home-only (and any page that genuinely needs it), imported lazily.
- One `InstancedMesh` + one `LineSegments`; memoized geometry/material; no per-frame allocation;
  update buffers in place. Cap pixelRatio at `min(devicePixelRatio, 2)`; `adaptiveDpr`.
- Pause the scene loop when offscreen (IntersectionObserver) and on tab blur. Dispose on unmount.
- Textures: compressed WEBP/AVIF; static fallback frame ≤ 120KB. No large GLB (geometry is
  procedural). Fonts subset via next/font. Images `next/image`, modern formats, explicit sizes.
- No duplicate animation libs; framer-motion tree-shaken to used features. No uncontrolled RAF
  loops; single GSAP ticker synced to Lenis.
- Guard against leaks: cleanup ScrollTriggers + GSAP context + Lenis + vanilla Three renderer on route change.

## Verification workflow (per phase)

Run dev preview → check console/network for errors → `next build` (bundle sizes) → Lighthouse on
`next start` → record FPS via stats in dev → capture screenshots. Log numbers in
`visual-qa-checklist.md`. A phase is not "done" on compile alone.
