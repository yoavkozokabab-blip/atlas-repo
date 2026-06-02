<div align="center">

# ◈ JARVIS

### Stop making AI read your entire repository.

**JARVIS builds architecture maps, dependency graphs, impact analysis and AI-ready
context — before Claude, Codex or Cursor ever see your code.**

`local-first` · `deterministic` · `no API keys` · `Python-first`

[Join the waitlist »](jarvis_desktop/static/landing.html) &nbsp;·&nbsp; [Watch the demo »](jarvis_desktop/static/demo.html) &nbsp;·&nbsp; [Gallery »](jarvis_desktop/static/gallery.html)

<img src="jarvis_desktop/docs/hero.gif" alt="JARVIS dependency universe forming" width="820"/>

</div>

---

## What is JARVIS?

JARVIS is a **Repository Intelligence Platform**. Point it at a codebase and it
produces, locally and in seconds, the things an AI coding agent actually needs to
understand your project:

- a plain-English **architecture overview** and subsystem map,
- an interactive **3D dependency graph**,
- an **architectural-risk ranking** (with the evidence behind every score),
- **change-impact analysis** (blast radius before you edit),
- and a compact, **AI-ready context packet** for Claude, Codex or Cursor.

It does **not** replace your AI tool. It makes the one you already use **faster,
cheaper, and better grounded.**

## Why JARVIS exists

Every time you ask Claude, Codex or Cursor a question about a non-trivial repo, it
spends a big chunk of its context window **re-reading files just to orient itself** —
and still occasionally invents structure that isn't there.

JARVIS analyzes the repository **once**, deterministically, and hands your agent a
map. The agent starts *informed*: it reads less, answers faster, and cites real
structure instead of guessing. **Evidence over vibes.**

## Screenshots

| Repository Universe | AI Copilot | AI Context Export |
|:---:|:---:|:---:|
| ![graph](jarvis_desktop/docs/graph.png) | ![copilot](jarvis_desktop/docs/copilot.png) | ![export](jarvis_desktop/docs/export.png) |
| 3D map colored by risk | One-click context for any AI | Token-cheap, evidence-rich packets |

> No screenshots yet? The in-app **Gallery** renders live mockups until you drop real
> PNGs into `jarvis_desktop/static/shots/`. Capture them with the built-in Demo Studio.

## Demo

A hands-free **Demo Studio** (`jarvis_desktop/static/studio.html`) runs a cinematic
~70-second tour over a bundled sample repo — perfect for recording a launch GIF with
zero manual setup:

```
Open app → Load demo repo → Tour → Graph → Risk → Impact → Copilot → Export
```

## Architecture

```
        ┌───────────────────────────────────────────────┐
        │             JARVIS Desktop (product)           │
        │   landing · command center · studio · export   │
        └───────────────┬───────────────────────────────┘
                        │  local API (zero-dependency server)
        ┌───────────────▼───────────────────────────────┐
        │              Builder Core (engine)             │
        │   role index · production dependency graph ·   │
        │   architectural-risk ranking · AI context      │
        └────────────────────────────────────────────────┘
```

A real, deterministic static dependency-graph + risk engine — **not an LLM wrapper.**
Runs entirely on your machine.

## Features

- 🧠 **Repository Intelligence** — architecture, subsystems, entry points, runtime flow.
- 🌌 **Dependency Universe** — interactive 3D map of how every module connects.
- 🎯 **Impact Analysis** — affected modules, subsystems and the tests to run.
- 🛡️ **Architecture Risk Detection** — riskiest modules ranked, with evidence.
- ✨ **Claude / Codex / Cursor Export** — compact context packets, one click.
- 🔒 **Local & deterministic** — no cloud, no API keys, same input → same output.

## Quickstart

```bash
# Windows (one-click)
run_jarvis_desktop.bat

# or any platform
py -3 run_jarvis_desktop.py          # opens http://127.0.0.1:8777
```

No build step, no `npm install`, no account. Marketing front door:
`http://127.0.0.1:8777/landing.html`.

## Roadmap

- [x] Local repository scan · 3D dependency graph · risk ranking
- [x] Impact analysis · AI context export (Claude / Codex / Cursor)
- [x] Demo Studio (recording mode) · waitlist · feedback capture
- [ ] More languages (vote in the beta)
- [ ] Native folder picker (Tauri/Electron shell)
- [ ] One-click MCP / editor integration
- [ ] Team mode & shared context packets

## Beta access

We're onboarding developers in small waves. If you live in Claude / Codex / Cursor
and own a real codebase, we'd love your eyes on it.

**→ [Apply for the private beta](jarvis_desktop/static/beta.html)** &nbsp;·&nbsp;
**[Join the waitlist](jarvis_desktop/static/landing.html)**

<div align="center"><sub>JARVIS — prepare your codebase for AI. Built on the deterministic Builder Core engine.</sub></div>
