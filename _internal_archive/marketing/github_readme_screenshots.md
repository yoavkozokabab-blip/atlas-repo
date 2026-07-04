# GitHub README — Structure & Screenshot Checklist

A great repo README is the highest-converting asset for developers. Structure:

```
# JARVIS — Repository Intelligence Platform
> Stop making AI read your entire repository.

[ hero GIF: 3D dependency graph forming + scan completing ]

Badges: license · python · local-first · "no API keys"

## What it does          (3 sentences, the problem → the fix)
## Demo                  (the GIF + a link to the 60s video)
## Screenshots           (the 5 shots below)
## Quickstart            (run_jarvis_desktop.bat → opens localhost)
## How it works          (scan → graph → risk → impact → AI export)
## Why not just paste files?  (the token/structure argument)
## Status & roadmap      (honest: early, Python-first)
## Join the waitlist     (single CTA)
```

## Screenshot checklist (capture at 1440×900, dark theme)
1. **Hero GIF** — `run` → repository scan stages animating → command center.
   *Filename:* `docs/hero.gif`  *Shows:* the wow moment.
2. **Command Center** — full 3-panel view with the 3D graph settled.
   *Filename:* `docs/command-center.png`  *Shows:* the product feels real.
3. **Dependency Universe** — a clicked hub node with its detail popover (fan-in/risk).
   *Filename:* `docs/graph.png`  *Shows:* depth + interactivity.
4. **Architecture Risk** — the risk ranking with the evidence column visible.
   *Filename:* `docs/risk.png`  *Shows:* evidence, not vibes.
5. **AI Export** — the context packet preview with the live token estimate, target = Claude.
   *Filename:* `docs/export.png`  *Shows:* the core value prop.
6. **Impact** *(optional)* — blast radius + recommended tests for `config.py`.
   *Filename:* `docs/impact.png`

## Capture tips
- Use the bundled **demo mode** so screenshots show a populated, recognizable graph.
- Hide your real repo path in the chip if it's sensitive.
- Keep one accent color dominant; let whitespace breathe.
- Export PNGs to `jarvis_desktop/static/shots/{graph,copilot,impact,risk,export}.png`
  and the in-app **gallery** picks them up automatically (they overlay the CSS mockups).

## README do's
- First screen (no scroll) must answer: *what is this, who is it for, why care.*
- One CTA repeated 2–3×: **Join the waitlist.**
- Link the demo video and the landing page (`landing.html`).
