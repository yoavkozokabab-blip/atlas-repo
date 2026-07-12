# Atlas Design Tokens

Status: Phase 1 design checkpoint

Canonical prototype source: [`prototypes/atlas-premium-experience/tokens.css`](../../prototypes/atlas-premium-experience/tokens.css)

The production desktop and website should consume the same token names and values. Platform-specific component CSS may differ, but color, type scale, spacing, shape, and motion should not drift.

## Typography

### Families

| Role | Token | Prototype stack | Production direction |
| --- | --- | --- | --- |
| Display and headings | `--font-display` | Aptos Display, Segoe UI, system UI | Self-host one licensed display family or retain the system stack |
| Interface text | `--font-ui` | Aptos, Segoe UI, system UI | Keep one highly readable UI family |
| Code and evidence | `--font-code` | Cascadia Code, SFMono-Regular, Consolas | Use for paths, symbols, hashes, and measured values only |

The prototype uses installed system fonts so it works offline. A later production typography decision must include font licensing and self-hosting; the website must not depend on a third-party font request during build or runtime.

### Scale

| Role | Desktop | Small viewport | Line height | Use |
| --- | --- | --- | --- | --- |
| Hero | 56 px | 40 px | 1.08 | Website offer only |
| Page title | 36 px | 30 px | 1.08 | Desktop workspace title |
| Section title | 24 px | 22 px | 1.08 | Major output section |
| Item title | 18 px | 18 px | 1.2 | Evidence and repeated item title |
| Body | 15 px | 15 px | 1.6 | Interface and explanatory text |
| Small | 13 px | 13 px | 1.5 | Metadata and compact controls |
| Label | 12 px | 12 px | 1.4 | Section labels and statuses |

Rules:

- No viewport-based font-size interpolation.
- Letter spacing is `0` throughout.
- Hero-size text appears only in a real hero.
- Code paths use the code family but keep body-readable contrast and size.
- Avoid more than three visible font weights on one screen.

## Color

### Core palette

| Token | Value | Role |
| --- | --- | --- |
| `--canvas` | `#090B0E` | Primary near-black background |
| `--canvas-soft` | `#0D1014` | App workspace background |
| `--surface-1` | `#12161B` | Inputs and grouped technical output |
| `--surface-2` | `#171C22` | Secondary control surface |
| `--surface-3` | `#1E252D` | Selected or elevated state |
| `--paper` | `#E8EDF4` | Deliberate light summary break |
| `--line` | `#252C35` | Default grouping border |
| `--line-strong` | `#36404D` | Active grouping border |

### Text

| Token | Value | Role |
| --- | --- | --- |
| `--ink-strong` | `#F3F6FB` | Headings and primary values |
| `--ink` | `#C3CBD6` | Body text |
| `--ink-muted` | `#8994A3` | Metadata and supporting text |
| `--ink-faint` | `#65707D` | Decorative separators only, not normal text |
| `--paper-ink` | `#151A20` | Text on the light summary surface |

### Action and semantic colors

| Token | Value | Role |
| --- | --- | --- |
| `--atlas-blue` | `#78A9FF` | Primary action, focus, and selected navigation |
| `--atlas-blue-strong` | `#9BC0FF` | Hover and inline path emphasis |
| `--atlas-blue-ink` | `#08111F` | Text on Atlas blue |
| `--evidence` | `#65D4C2` | Direct evidence and verified relationship |
| `--success` | `#64D88E` | Ready, connected, complete |
| `--warning` | `#E8B65B` | Uncertain, manual verification, caution |
| `--stale` | `#E2A45D` | Stale repository state |
| `--danger` | `#FF7F91` | Failure and destructive action |
| `--focus` | `#B8D3FF` | Keyboard focus outline |

Semantic color always appears with a text label. A teal edge also says Direct; an amber state also says Stale or Needs verification.

### Contrast targets

- Strong and body text target at least 7:1 on the primary canvas.
- Muted normal text targets at least 4.5:1 on the surface where it appears.
- Primary-button text targets at least 7:1 against Atlas blue.
- Focus outlines must be distinguishable against canvas and all surface tokens.
- `--ink-faint` is not approved for normal text until a contrast check confirms the specific background and font size.

Verified prototype pairs:

| Pair | Contrast |
| --- | ---: |
| Strong text on canvas | 18.19:1 |
| Body text on canvas | 12.04:1 |
| Muted text on Surface 1 | 5.91:1 |
| Atlas blue text on canvas | 8.37:1 |
| Dark text on Atlas blue | 8.03:1 |
| Direct evidence on canvas | 11.02:1 |
| Warning on canvas | 10.58:1 |
| Error on canvas | 8.16:1 |
| Paper ink on paper | 14.87:1 |

## Spacing

The spacing scale is intentionally small and regular:

| Token | Value | Typical use |
| --- | --- | --- |
| `--space-1` | 4 px | Tight icon or inline gap |
| `--space-2` | 8 px | Label to value |
| `--space-3` | 12 px | Compact control gap |
| `--space-4` | 16 px | Standard internal spacing |
| `--space-5` | 24 px | Technical section padding |
| `--space-6` | 32 px | Related section separation |
| `--space-7` | 48 px | Conceptual separation |
| `--space-8` | 64 px | Page-level separation |
| `--space-9` | 96 px | Website section separation |

Technical output uses compact internal spacing. Different concepts use 48 to 96 px separation or a full-width border, not another decorative container.

## Shape

| Token | Value | Use |
| --- | --- | --- |
| `--radius-sm` | 4 px | Code rows, tags, compact controls |
| `--radius` | 7 px | Inputs, buttons, bounded tools |
| `--shadow-float` | `0 24px 72px rgba(0,0,0,.42)` | Modals and command palette only |

Rules:

- Page sections are not floating cards.
- Repeated evidence items use rows and borders before containers.
- Status pills are allowed only for short state labels.
- Cards never contain decorative nested cards.
- Controls keep stable heights and do not resize on hover or state change.

## Motion

| Token | Value | Use |
| --- | --- | --- |
| `--motion-fast` | 140 ms | Hover, focus, selected state |
| `--motion-standard` | 190 ms | View transition, overlay entry |
| `--ease-out` | `cubic-bezier(.2,.8,.2,1)` | State changes |

No continuous decorative motion. Long operations use a text phase and elapsed state. Reduced-motion preference collapses animation and smooth scrolling to 1 ms or immediate behavior.

## Layout

| Token | Value | Use |
| --- | --- | --- |
| `--app-max` | 1480 px | Desktop application frame |
| `--content-max` | 1120 px | Website and main desktop content |
| `--reading-max` | 760 px | Ask answer document |
| `--appbar-height` | 58 px | Desktop global bar |
| `--control-height` | 40 px | Standard button and input minimum |

Fixed-format elements use explicit dimensions or grid tracks. Buttons, repository switchers, status controls, and graph nodes must not change layout when text or state changes.

## Component token usage

### Primary action

- Background: `--atlas-blue`
- Text: `--atlas-blue-ink`
- Radius: `--radius`
- Minimum height: `--control-height`
- One primary action per state

### Evidence row

- Background: transparent or `--surface-1`
- Separator: `--line`
- Direct evidence: `--evidence` plus Direct label
- Inferred relationship: `--warning` plus Related or Likely label
- Path: `--font-code`

### Repository state

- Ready: `--success` plus Ready
- Stale: `--stale` plus Stale and Refresh action
- Scanning: Atlas blue plus current backend phase
- Error: `--danger` plus what happened and retry path

### Impact relationship

- Origin: solid Atlas blue border
- Direct: solid evidence border or edge
- Indirect: dashed warning border or edge
- Unknown or dynamic: dotted danger border or edge

Line style and text make the relationship readable without color.

## Migration rule

Do not append these tokens below the existing desktop CSS and override another historical layer. Production implementation should introduce the token block first, migrate one approved screen to it, remove superseded rules for that screen, and verify visual and behavior tests before moving on.
