# Visual QA Checklist & Log

Playwright captures + seven-lens review after every major section. A section is done only when
every visible weakness is fixed and numbers are logged. Compilation ≠ done.

## Capture matrix (Playwright)

Desktop 1440×900: hero, 20%, 40%, 60%, 80%, final CTA. Plus 1920×1080 hero, 2560×1080 ultrawide.
Mobile 390×844: hero, 25%, 50%, 75%, final CTA, mobile nav open, /download.
Also: reduced-motion hero, static-fallback hero, light-of-day content page (docs).

## Per-capture review (score each, note specific fixes)

Visual hierarchy · camera framing · typography (size/tracking/measure) · contrast (WCAG) ·
whitespace/rhythm · consistency · 3D composition · alignment · accidental overlap · "does it
look like a template?" · readability over scene · CTA clarity · perceived quality.

## Seven-lens sign-off (each lists ≥1 concrete issue until clean)

- [ ] Creative director — concept legible, cinematic, distinctive, not generic.
- [ ] Product designer — hierarchy, spacing, states, real product presented well.
- [ ] WebGL engineer — draw calls, instancing, no leaks, graceful fallback, 60/30fps.
- [ ] Motion designer — purposeful, no reused fade-up, correct easing, reduced-motion.
- [x] Accessibility (homepage, 2026-07-13) — axe-core WCAG2.1AA **0 violations** (`qa/a11y.mjs`);
      contrast fixed (`--text-2` → #8A938C, ≥4.5:1 on all surfaces); skip-to-content link;
      keyboard scroll works through Lenis; mobile menu traps focus + Escape + focus return;
      reduced-motion freezes the scene to a stable state (Lenis off, opacity-only reveals);
      canvas/labels aria-hidden, landmarks + heading order semantic. Manual checks: `qa/a11y-manual.mjs`.
- [ ] Performance — LCP/CLS/INP, bundle sizes, Lighthouse, mobile.
- [ ] Developer credibility — real facts, honest limits, working links, trust signals.

## Measurement log (fill in per phase)

| Phase | Date | LCP | CLS | INP | LH perf (d/m) | Scene FPS (d/m) | JS shell / scene gz | Notes |
|---|---|---|---|---|---|---|---|---|
| Hero v1 | 2026-07-13 | — | — | — | — | 60 cap / ok | — | Captured via Playwright (SwiftShader). Console errors=0 at 1440/1920/390. Lighthouse + bundle report still TODO. |
| Narrative v1 | 2026-07-13 | — | — | — | — | 60 cap / ok | — | 4 acts (scan/memory/retrieval/converge) verified at 1440 + 390, errors=0. Lenis + GSAP ScrollTrigger drive one progress value; scene morphs (centre slide, scan sweep, retrieval path highlight, converge gather). QA via `qa/capture-narrative.mjs` (scrolls via exposed Lenis to each act). |
| Homepage full | 2026-07-13 | **0.25s** | **0.001** | — | — | 60 cap / ok | **159 / ~74 gz** | Production `next build` + `next start`, measured with Playwright (`qa/perf.mjs`). Home First Load JS 159 kB (three.js NOT in it); scene chunk 315 kB raw / 73.6 kB gz, lazy async. FCP 252ms, LCP 252ms (hero text is DOM, never blocked by WebGL), CLS 0.001, TTFB 8ms (local). All performance-budget targets met/beaten. Redesigned sections (capabilities/integrations/proof/faq/download) captured at 1440, errors=0. Lighthouse-proper (needs full Chrome) still TODO; Web-Vitals via PerformanceObserver used instead. |

## Hero v1 — engineering note

React Three Fiber v9 **silently fails to create its GL root** in this stack (Next 15.5 /
React 19.2.6): canvas mounts but no `__r3f`, no `useFrame`, buffer stuck at 300×150, and no
console error. A bare `<Canvas><mesh/></Canvas>` reproduced it; a vanilla-three `useEffect`
rendered immediately. Decision: **the scene is built in vanilla Three.js** (lighter, full
control of sizing/loop, robust under StrictMode via explicit effect cleanup — verified 1 canvas,
no leak). Drei/postprocessing/R3F deps were pruned after a source search confirmed no production
or QA imports.

Screenshots: the in-app Browser-pane `computer{screenshot}` **times out** in this environment
(even on canvas-free pages), so QA uses **Playwright** (`qa/capture.mjs`, SwiftShader flags) →
PNGs, which is the brief-mandated tool anyway.

## Hero v1 — fixes applied during review

- Composition: constellation shifted into the right column (outer offset group) + lowered into
  the clear lower-right quadrant; headline gets a left scrim → always legible.
- Labels: assigned to right-side high-importance nodes, vertically spaced, gated to sit right-of
  or below the real headline box (measured from the DOM), de-overlapped. ~2–4 show per width.
- Mobile: normal phones (≥340px) now get the simplified live scene (was static <420px); graph
  lifted to frame the headline so body copy stays clean.

## Prohibited-pattern audit (must all be NO)

blue-purple hero gradient · glowing orb · random particles · glass everywhere · 3-card grid as
main rhythm · browser-frame mockups · every section centered · every element fades up · spinning
cube/globe · decorative neural net · fake terminal/chat/testimonial/logos/metrics · default
Tailwind/shadcn look · effects with no product meaning.
