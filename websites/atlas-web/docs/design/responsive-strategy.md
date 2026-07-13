# Responsive Strategy

Mobile is a *designed* experience, not a squeezed desktop. The narrative is preserved; the
implementation adapts per tier.

## Breakpoints

| Tier | Width | Scene | Notes |
|---|---|---|---|
| Large desktop | ≥1440 | full: 260 nodes, bloom, labels, parallax, full camera travel | |
| Desktop | 1024–1439 | full: ~220 nodes | |
| Tablet | 768–1023 | 160 nodes, no bloom, fewer labels, shorter camera travel | |
| Mobile | 420–767 | 70 nodes, no bloom, no labels, no hover, DPR≤2, reduced travel | touch-safe |
| Low-power mobile | <420 or `deviceMemory<4` or save-data | **static pre-rendered frame** + slow CSS parallax | no WebGL |

Detection: `matchMedia`, `navigator.deviceMemory`, `navigator.connection.saveData`, WebGL probe,
`prefers-reduced-motion`. Choose tier once on mount; expose via context to scene + layout.

## Layout adaptation

- Hero H1 reflows to ≤3 lines; CTAs stack full-width, thumb-reachable (min 48px targets).
- Asymmetric desktop compositions become single-column with preserved left/right emphasis via
  alignment, not centered mush.
- Scroll acts shorten (less pin distance) so mobile scroll isn't endless.
- Labels/parallax that don't translate → replaced by a static high-quality frame with subtle
  movement, never forced.
- No text over visually noisy graph areas on mobile: content gets a solid/gradient scrim.
- Tables (compare/benchmarks) scroll inside `overflow-x:auto`; body never scrolls horizontally.

## Nav

Desktop: transparent → blur-on-scroll minimal bar. Mobile: full-screen technical panel (large
labels, version, download CTA, faint graph/contour texture, explicit close), not a collapsed
hamburger list.

## Testing viewports (Playwright — see visual-qa-checklist.md)

1440×900, 1920×1080, 2560×1080 (ultrawide), 768×1024 (tablet), 390×844 (iPhone), 360×640 (low).
