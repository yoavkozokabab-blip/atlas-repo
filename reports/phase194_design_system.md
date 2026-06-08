# Atlas Design System (Phase 194, Part 9)

A small, intentional set of tokens that all new/updated UI consumes so spacing,
radius, type and color stay consistent. Defined in `jarvis_desktop/static/styles.css`
under `:root`, with opt-in primitive classes (`.ds-*`).

## Color

One primary action color, one secondary accent, plus semantic state colors.

| Token | Value | Use |
|---|---|---|
| `--primary` | `#3ef0ff` (cyan) | Primary actions, active states, links |
| `--primary-ink` | `#04121a` | Text/icon on a primary-filled surface |
| `--accent` | `#9a7bff` (violet) | Secondary accent, gradients |
| `--ok` | `#42f5b0` | Success (e.g. pending = application received) |
| `--warn` | `#ffc24b` | Caution (used sparingly) |
| `--danger` | `#ff5c7a` | Destructive only |
| `--txt` / `--muted` | `#dce6ff` / `#7e8db5` | Body / secondary text |

Rule: never introduce a new accent hue. Compose from the tokens above.

## Typography — 3 heading sizes, 2 body sizes

| Token | Size | Class | Use |
|---|---|---|---|
| `--h1` | 26px | `.ds-h1` | Page title (one per screen) |
| `--h2` | 19px | `.ds-h2` | Section heading |
| `--h3` | 14.5px | `.ds-h3` | Card / sub-section heading |
| `--text` | 14px | `.ds-text` | Body |
| `--text-sm` | 12px | `.ds-text-sm` | Secondary / metadata |

Weights: `--fw-bold` (700) for headings, `--fw-med` (600) for emphasis.

## Spacing — 4px base scale

`--space-1:4` · `--space-2:8` · `--space-3:12` · `--space-4:16` · `--space-5:24`
· `--space-6:32`. Use these for gaps/padding/margins instead of ad-hoc values.

## Radius — one card radius

| Token | Value | Use |
|---|---|---|
| `--radius` | 18px | **Every card** (`.glass` and all card surfaces) |
| `--radius-sm` | 12px | Buttons, inputs, nav items |
| `--radius-pill` | 20px | Chips / pills |

## Buttons — one sizing system

`.btn` is the base. Modifiers: `.btn.small` (compact, used in menus/toolbars),
`.btn.big` (primary CTAs). Variants: `.btn.primary` (filled, `--primary`),
`.btn.ghost` (outline/secondary). All share radius `--radius-sm` and the same
padding rhythm. Pills/badges use `--radius-pill`.

## Adoption

Phase 194 foundation applies the tokens to the topbar, the home dashboard, the
status dashboards and `.glass`. Remaining screens are migrated to the tokens as
each later Part 194 area (result cards, export, admin workspace) is rebuilt;
Part 11 audits the whole app against this document.
