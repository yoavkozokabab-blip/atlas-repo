# Phase 113 — Branding, Waitlist, Polish & First Impression

**Status:** Shipped (additive marketing & conversion layer).
**Date:** 2026-06-01
**Lens:** Head of Product & Design. Goal — make a developer who's never heard of
JARVIS *immediately want to try it.*
**Constraints honored:** No Builder Core changes. No benchmark work. No token
optimization. Pure design / UX / branding / conversion / first impression.

---

## 0. What shipped (the front door)

A standalone marketing site + conversion system layered **additively** over the
existing app — nothing in the product engine was touched.

```
jarvis_desktop/static/
  landing.html     # the showpiece: hero, features, how-it-works, screenshots, FAQ, waitlist
  demo.html        # 60-second demo video page + chapters
  gallery.html     # product screenshot gallery (5 surfaces)
  beta.html        # private beta program (who/what/timeline)
  admin.html       # local metrics dashboard (waitlist + usage)
  marketing.css    # premium design system (Linear/Vercel/Stripe-grade)
  marketing.js     # waitlist (local, backend-ready), counts, reveals, mock screenshots
marketing/         # X / Reddit / HN / GitHub launch kit + copy bank
```

The marketing pages cross-link and each routes back to the app (`index.html`).
A real launch would serve `landing.html` as `/`.

---

## 1. Global design audit (the 7 app screens)

| Screen | Issue found | Fix / direction |
|---|---|---|
| **Home** | Emoji command cards + Orbitron "gamer" wordmark read hobby-project, not product; value prop buried below the fold | Landing page now carries the value prop *above the fold*; recommend migrating the app wordmark to the refined Inter mark used in marketing |
| **Scan** | Strong already (animated stages) — but "Indexing repository" is tool-speak | Reframe stage labels to outcomes ("Mapping your architecture"); keep the animation |
| **Command Center** | Three dense panels compete; neon glow overload; "Dependency Graph" is generic | Rename to **"Repository Universe"** (already adopted by the app); reduce glow, add breathing room; let the graph be the hero |
| **Intelligence** | Good content, weak hierarchy | Bigger section headers, more whitespace, one accent color |
| **Impact** | Functional but plain; "heuristic/TODO" chips read internal | Keep honesty, restyle as a quiet "preview" badge, not a warning |
| **Bug Investigation** | "Bug Hunt" nav label is cute, not premium | Rename to **"Investigate"**; lead with confidence + evidence |
| **AI Export** | This is the crown jewel but reads like a form | Make it feel like *generating something valuable* — "Prepare context for Claude" with a token-savings reveal |

**Cross-cutting:** inconsistent neon (cyan/violet/pink all at full strength),
Orbitron everywhere (gamer), tight spacing, no empty states, no onboarding for a
first-time visitor. The marketing layer fixes the **first impression**; the in-app
polish recommendations are captured here for the app team to adopt without engine risk.

---

## 2. Premium visual design (the answer to "no gamer aesthetics")

The marketing surface establishes the target quality (Linear / Vercel / Arc /
Stripe / Anthropic Console):

- **Typography:** Inter only (dropped Orbitron). Large, tight, confident headings;
  generous line-height; a real type scale.
- **Color:** restrained — near-black `#07070c`, mostly monochrome text, **one**
  signature gradient (indigo→violet→pink) used sparingly. No full-strength neon walls.
- **Glass & depth:** subtle low-opacity panels, hairline borders, soft shadows —
  not glow-bombing.
- **Spacing:** an 8px system (`--s1…--s6`), wide margins, ~1120px content column.
- **Motion:** reveal-on-scroll (IntersectionObserver), button lifts, gradient
  hero — *subtle, professional*. No bounce, no confetti.
- **Icons:** simple, consistent, restrained.

Design tokens live in `marketing.css :root` so the whole surface is one system.

---

## 3. Landing page

Single-screen value prop, then proof. Sections: **Hero** ("Stop making AI read your
entire repository." + the required subheadline + Join Waitlist / Watch Demo CTAs +
local-first trust + live waitlist count + a product frame), **Problem**, **Features**
(the 5 required + Local/Deterministic), **How it works** (3 steps), **Screenshots**,
**Waitlist CTA band** with social proof, **FAQ** (5 honest Q&As incl. "does it
replace your AI?" → no), **Footer**. Copy never over-claims; positioning held.

---

## 4. Waitlist system

A polished modal reachable from every page. Fields: **name, email, company
(optional), repository size, AI tool used**. Validates name + email inline. On submit
it stores locally (`localStorage`) via `persistSignup()` — a **backend-ready
interface** (one-line swap to `POST /api/waitlist` later). Shows a success state with
the user's queue position. A **configurable count** (`WAITLIST_BASE = 127`) renders
as *"127 developers waiting"* across hero, proof band and modal, incrementing as
people join.

---

## 5. Demo, Gallery, Beta, Admin

- **Demo** (`demo.html`): a premium video frame (placeholder play button → drop
  `demo.mp4`), a "60-second walkthrough" with **timestamped chapters**, and
  architecture-highlight cards.
- **Gallery** (`gallery.html`): five presentation-framed surfaces — **Graph,
  Copilot, Impact, Risk, Export**. Each shows a live CSS mock that a **real PNG
  overlays automatically** when dropped into `static/shots/`.
- **Beta** (`beta.html`): who should join, the feedback we need, and a 4-step
  timeline. Apply = the waitlist.
- **Admin** (`admin.html`): a **local** metrics dashboard — waitlist signups + a
  recent-signups table + breakdowns by AI tool / repo size (from localStorage),
  plus scans / exports / copilot questions read live from `/api/analytics/summary`
  when the app is running. Nothing leaves the machine.

---

## 6. Wow moments (professional, no confetti)

The marketing surface adds restrained delight: a **gradient hero with reveal-on-
scroll**, a **graph that draws itself** in the hero/gallery frames (animated nodes +
links), **counters as social proof**, a **success-state reveal** on waitlist join,
and play-button micro-interactions. In-app wow recommendations (graph fly-in, risk-
score reveal, scan-completion summary) are documented for the app team — several
already exist in the current app build (scan success screen, repository tour).

---

## 7. Copywriting (premium voice)

Rewrote the product vocabulary; full bank in `marketing/launch_copy.md`:

| Tool-speak (avoid) | Product-speak (use) |
|---|---|
| Analyze Repository | Understand your architecture |
| Dependency Graph | Explore your code universe |
| Run scan | Map your repository |
| Risk report | Find your architectural risks |
| Export context | Prepare your codebase for AI |
| Token reduction | Cheaper, faster AI answers |

The hero, features and FAQ all use this voice. Honesty is preserved (early,
local-first, Python-first) — developers reward candor.

---

## 8. Social sharing kit (`marketing/`)

- `x_launch.md` — a 5-post X launch thread + single-tweet version + asset list.
- `reddit_launch.md` — r/programming, r/ChatGPTCoding, r/cursor posts + comment-readiness.
- `hackernews_launch.md` — Show HN title + body + first comment + launch-day checklist.
- `github_readme_screenshots.md` — README structure + 6-shot screenshot checklist.
- `launch_copy.md` — tagline bank, one-liners, elevator pitch, value props, CTA bank.
- `README.md` — the kit index + golden rules.

All hold the line: *JARVIS doesn't replace your AI — it makes it smarter.*

---

## 9. Testing

```
py -3 -m pytest jarvis_desktop/tests/test_phase113_marketing.py -q
17 passed
```
Verifies: every marketing page exists + is non-trivial; the landing value prop,
CTAs and 5 features are present; the **waitlist interface** (fields + storage fns +
configurable count); demo chapters; gallery's 5 surfaces; beta sections; admin KPIs +
analytics wiring; **every page navigates back to app + landing**; the marketing kit
assets exist; and the static server resolves the pages. A live server smoke confirms
`landing/demo/gallery/beta/admin/marketing.css/marketing.js` all serve.

---

## 10. Screenshots instructions

1. `run_jarvis_desktop.bat` (or `py -3 run_jarvis_desktop.py`) → open
   `http://127.0.0.1:8777/landing.html` for the **marketing front door**.
2. Capture at **1440×900**, dark theme.
3. For real product shots, open the app, use **Demo Mode** for a populated graph,
   and capture: hero GIF (scan → command center), command center, a clicked graph
   node, the risk ranking, the AI export with token estimate.
4. Save PNGs to `jarvis_desktop/static/shots/{graph,copilot,impact,risk,export}.png`
   — the gallery overlays them on the mockups automatically.
5. The CSS mock screenshots make every page look populated *before* you have real
   captures, so the landing/gallery already demo well.

---

## 11. Success criteria

| A first-time developer can… | How |
|---|---|
| Understand the value prop in < 30s | Landing hero: problem + fix + 5 features above/near the fold |
| Watch a demo | `demo.html` with chapters (drop `demo.mp4` to finalize) |
| Join a waitlist | One-click modal on every page, 5 fields, instant success state |
| Feel JARVIS is professional | Premium Inter/glass design system, restrained palette, real product frames |
| Want to try it | Clear "it makes your AI smarter," local-first trust, single repeated CTA |

---

## 12. Honest notes & scope

- **Additive only:** no change to Builder Core, detectors, benchmarks, the CLI, or
  any analysis behavior. The marketing layer is static pages + a marketing/ folder.
- **Waitlist is local for now** (`localStorage`), with a clearly-marked one-function
  swap to a real backend endpoint when ready.
- **Demo video + real screenshots are placeholders** — the structure ships; drop in
  `demo.mp4` and `static/shots/*.png` to finalize. CSS mockups keep the pages
  looking alive in the meantime.
- The in-app screens (Home/Scan/Center/Intelligence/Impact/Bug/Export) are being
  evolved by the product app track; §1 captures the design recommendations without
  re-engineering them here.
- A pre-existing, unrelated test (`test_phase104c_fix_compact_evidence`) is failing
  from separate compact-evidence/benchmark work — explicitly out of Phase 113 scope
  (no benchmark / no token work). Phase 113's own tests (17) and the Phase 107
  product API tests pass.
