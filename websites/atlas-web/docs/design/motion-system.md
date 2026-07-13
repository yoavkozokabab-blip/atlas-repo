# Motion System — Atlas

Personality: smooth, confident, slightly slow, technical, cinematic. Never bouncy, elastic, or
chaotic. Motion has narrative purpose or it is cut.

## Primitives

- **Ease**: primary `cubic-bezier(0.22, 1, 0.36, 1)` (expo-out feel). Camera/scene morphs use
  `power2.inOut`. No `back`/`elastic`/overshoot anywhere.
- **Durations**: micro (hover, nav, buttons) 120–220ms · content reveals 500–800ms · section /
  camera transitions 900–1600ms · crystallize intro ~2200ms.
- **Stagger**: text lines 40–70ms; node/label reveals 8–20ms.

## Libraries (no duplication)

- **GSAP + ScrollTrigger**: the master scroll timeline + text reveals tied to scroll.
- **Lenis**: smooth scroll, fed into ScrollTrigger via its `scrollerProxy`/raf.
- **Framer Motion**: only small UI-state transitions (nav, mobile menu, tab/accordion, route
  fades). Not for scroll-driven scene work.
- Vanilla Three.js animation loop for the scene; all scene targets are lerped toward scroll-derived values.

## Text reveal vocabulary (do NOT reuse one fade-up everywhere)

- Hero H1: per-word mask reveal (translateY + clip), staggered, with a subtle tracking settle.
- Section H2: per-line mask reveal on enter.
- Body: short opacity+8px rise, once.
- Mono labels / evidence: type-in or clip-wipe (feels like data resolving).
- Numbers/metrics: count-up on first view (respects reduced-motion → show final).

## Microinteractions

- **Buttons**: subtle magnetic pull (≤6px toward cursor), arrow/label translate 3–4px, border/bg
  transition. No glow bloom.
- **Nav**: transparent over hero; on scroll gains blur + faint bg + fine bottom border + slight
  height reduction. Fast (160ms). Active route underline via clip reveal.
- **Links**: custom underline that wipes in from left.
- **Cards/rows**: border-color + 1–2px lift only.
- **Cursor**: optional custom cursor (small ring that grows over interactive + node hover).
  Desktop + fine-pointer only; never required; disabled on touch and reduced-motion.

## Reduced motion (`prefers-reduced-motion: reduce`)

- Kill camera travel, graph morphs, parallax, count-ups, custom cursor, bloom pulsing.
- Replace scroll scrubbing with stable per-act states; reveals become instant/short opacity.
- All content and proof remain fully available. Scene → static frame.
