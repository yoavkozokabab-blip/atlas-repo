# Visual System — Atlas

Dark-first, warm-graphite, one mineral-teal accent. Tokens live in `app/design/tokens.css`.

## Color

Warm-neutral graphite base (never flat pure black; layered for depth).

| Token | Hex | Use |
|---|---|---|
| `--void` | `#070908` | deepest background / 3D scene clear color |
| `--bg-0` | `#0A0C0C` | page background |
| `--bg-1` | `#0F1312` | raised surface / cards |
| `--bg-2` | `#141918` | inset / inputs |
| `--bg-3` | `#1A211F` | active / hover surface |
| `--line` | `rgba(233,240,236,0.08)` | hairline borders |
| `--line-2` | `rgba(233,240,236,0.14)` | stronger borders |

Foreground — warm off-white, never harsh pure white in body.

| Token | Hex | Use |
|---|---|---|
| `--text-0` | `#ECEFEC` | headings / primary |
| `--text-1` | `#A7B2AD` | body |
| `--text-2` | `#6E7A75` | muted / labels |

**Accent — mineral teal** (the one Atlas color: "active memory / detected context / live
relationship / selected node"). Used sparingly and always meaningfully.

| Token | Hex | Use |
|---|---|---|
| `--accent` | `#5FD3BE` | primary accent, active edges, CTA |
| `--accent-bright` | `#8CF0DC` | live pulse / selected node (rare, small) |
| `--accent-deep` | `#2C6F66` | dim/inactive connections, gradients |
| `--accent-ink` | `#04110E` | text on accent fills |
| `--accent-soft` | `rgba(95,211,190,0.12)` | tints, chips, focus glow |

Semantic states only (never decorative): `--ok #4FBF8B` · `--warn #D6A23B` · `--risk #E5687A`.
Single accent policy: no second saturated hue anywhere. Color = meaning.

## Typography

Self-hosted via `next/font` (no CDN, no layout shift, licensing OK: SIL OFL / MIT).

- **Display** — **Space Grotesk** (grotesk, distinctive, superb at 80–140px). Headlines only.
- **Text/UI** — **Geist Sans** (Vercel, MIT via `geist` pkg). Body, nav, buttons.
- **Mono** — **Geist Mono**. File paths, commands, metrics, scan status, in-scene labels.

Scale (fluid, `clamp`):
- Hero H1: `clamp(2.8rem, 8vw, 8.5rem)`, line-height 0.98, tracking -0.03em, ≤3 lines.
- Section H2: `clamp(2rem, 4.4vw, 3.6rem)`, tracking -0.025em.
- H3: `clamp(1.15rem, 2vw, 1.5rem)`.
- Body: 17–20px, line-height 1.6, measure ≤ 68ch. Never full-viewport paragraphs.
- Labels: 0.72–0.82rem mono, tracking +0.04em, uppercase where structural. Never faint-illegible.

Behavior: masked line-by-line reveals for headings; per-word for the hero; subtle tracking
settle. Do NOT reuse one fade-up on every block (see motion-system.md).

## Texture & depth

- **Contour grid**: faint SVG isolines, `--accent-deep` at 3–6% opacity, masked with a radial
  gradient so it fades at edges. The map motif.
- **Grain**: fixed fine-noise overlay (~3% opacity, `mix-blend: overlay`) to kill banding on
  dark gradients. Nearly subconscious.
- **Depth fog**: 3D scene uses fog matched to `--bg-0` so nodes recede into the void.
- Gradients only for lighting/fog/material transitions/focus — never a decorative hero wash.

## Surfaces & shape

- Radius: `--r-sm 8px`, `--r 12px`, `--r-lg 18px`. Restrained; not everything rounded.
- Elevation via 1px borders + long low-alpha shadows, not heavy blur. Minimal glass; if used,
  a single deliberate instance (nav), never everywhere.
- Layout tokens: `--maxw 1200px`, generous asymmetric gutters, `--ease cubic-bezier(0.22,1,0.36,1)`.

## Iconography

Thin 1.5px line icons on a consistent 24px grid, monochrome (text-1), accent only on active.
No filled/colorful stock icon sets.

## Logo / mark

Wordmark **Atlas** in Space Grotesk medium + a mark: a small faceted node-lattice (3–4 nodes
bound to a core) that echoes the constellation. The OG image is a real render of the
constellation, not text-over-screenshot.
