# Site Architecture

Next.js App Router in `websites/atlas-web`. **Functional routes stay intact** (auth, billing,
account, admin, api, legal). We rebuild the *marketing surface* on the new system.

## Route map

Marketing (rebuild on Living Map system):
- `/` Home — the cinematic scroll narrative (persistent canvas).
- `/product` (new; today `/features`) — deeper technical product page; keep `/features` as alias.
- `/how-it-works` (new) — the Atlas pipeline, diagram-led.
- `/integrations` (new) — Claude Code, Cursor, Codex, MCP: support level, install, workflow, limits.
- `/download` — trustworthy install: OS note, version, SHA256, steps, requirements, troubleshooting, security.
- `/security` · `/privacy` · `/terms` · `/refund` · `/eula` — content pages, reading-optimized shell.
- `/pricing` — real model: Free / Pro $19 (7-day trial) / Team coming soon. No fake tiers.
- `/changelog` · `/roadmap` · `/compare` · `/benchmarks` — proof/trust.
- `/docs` — polished entry into docs, same identity, reading-optimized.
- `/about` (new) — concise, honest, technically grounded. No fake company.
- `/hn` — keep (launch page), align styling.
- `/faq` · `/contact` — keep, restyle.

Functional (do not touch behavior; restyle shells only where safe):
- `/login`, `/account/*`, `/admin`, `/billing/*`, `/checkout/*`, `/cancellation`, `/api/*`,
  `/download/atlas` (route).

## Component architecture

```
app/
  design/tokens.css            # color/type/space tokens
  globals.css                  # reset + base + shared marketing classes
  _components/
    site.tsx                   # SiteNav, SiteFooter, PageShell (restyled)
    nav/                        # Nav, MobilePanel, CommandCTA
    scene/                      # Vanilla Three.js constellation, nodes, edges, core, labels, StaticFallback
    scene/ConstellationCanvas.tsx  # persistent <Canvas>, Suspense, error boundary, DPR/adaptive
    scroll/                    # LenisProvider, useScrollProgress, ScrollAct
    marketing/                 # Hero, Act sections, EvidenceCard, ProofRow, AgentGrid, StatCountUp
    ui/                        # Button, Link, Reveal, Chip, Tag, Accordion
  lib/scene/                   # seededGraph.ts (PRNG, clusters, edges), sceneStates.ts
  lib/content/                 # facts.ts (single source of REAL numbers/copy)
```

- Separation: page composition vs reusable UI vs 3D scene vs animation timelines vs content
  facts vs responsive/perf config vs SEO. No single mega-component; no over-splitting.
- `facts.ts` is the ONLY place product numbers live (imported by pages + scene), so no number
  can drift or be invented ad hoc.

## SEO / metadata

Per-page `metadata`; real OG image (rendered constellation, not text-over-screenshot);
`sitemap.ts` + `robots.ts` already exist — extend for new routes; canonical URLs; JSON-LD
SoftwareApplication on home + download; favicon/app icons from the mark.
