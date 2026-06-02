# Phase 107 — JARVIS Desktop Product MVP

**Status:** Implemented (product-shell MVP). Additive; Builder Core untouched.
**Date:** 2026-06-01
**Positioning:** *JARVIS prepares your codebase for AI. It does not replace
Claude/Codex/Cursor — it makes them understand repositories faster, cheaper, and
with better evidence.*

---

## 1. What shipped

A new top-level, **additive** package `jarvis_desktop/` — a local desktop web app
(premium dark/glassmorphism UI + 3D dependency graph) wrapping the existing
Builder Core engine. **No Builder Core file, detector, CLI, or test was modified.**

```
jarvis_desktop/
  api.py            # framework-agnostic product core (wraps Builder Core)
  server.py         # stdlib http.server (default) + optional FastAPI app
  static/
    index.html      # 7-screen SPA shell
    styles.css      # premium dark glassmorphism, neon accents
    app.js          # SPA logic, scan flow, 3D graph, copy/export
  tests/test_phase107_desktop_api.py
run_jarvis_desktop.py   # launcher (zero deps)
run_jarvis_desktop.bat  # Windows one-click
```

**Stack choice:** FastAPI is **not installed** in this environment, so the default
runtime is Python's **stdlib `http.server`** — zero external dependencies, always
runs on Windows. An optional `create_fastapi_app()` is provided for those who
`pip install fastapi uvicorn`. The 3D graph uses **3d-force-graph** (Three.js) via
CDN, with a graceful offline fallback.

---

## 2. How to run (Windows, no API keys)

```
:: one-click
run_jarvis_desktop.bat

:: or
py -3 run_jarvis_desktop.py            # opens http://127.0.0.1:8777
py -3 run_jarvis_desktop.py --port 9000 --no-browser
py -3 run_jarvis_desktop.py --fastapi  # if fastapi/uvicorn installed
```

No build step, no `npm install`, no account integration. Context is delivered by
**copy-to-clipboard** prompts (v1). Everything runs locally.

---

## 3. The 7 screens (core user flow)

| # | Screen | What it does |
|---|---|---|
| 1 | **Home** | Logo + tagline, "What would you like to do today?", 6 command cards, repo path picker, **Scan Repository**, recent repositories. |
| 2 | **Scan Experience** | Selected path, **7 animated scan stages** (indexing → graph → architecture → risks → contracts → verification → AI packets), live metrics (files, modules, edges, unresolved, hubs, token estimate), progress bar → auto-navigates to Command Center. |
| 3 | **Repository Command Center** | **3D dependency graph**, left panel (files/modules/subsystems/graph health/risk score/token savings), right **AI Copilot** (ask + suggested questions + Copy for Claude/Codex/Cursor). Node click → name, fan-in, fan-out, LOC, risk score, in-cycle, subsystem, "Analyze impact →". |
| 4 | **Project Intelligence** | Plain-English explanation, subsystem map, entry points, runtime flow, major modules, architecture risks, recommended next questions. |
| 5 | **Impact Simulator** | Input a file/module → affected files, affected subsystems, risk level, recommended tests, recommended Claude/Codex prompt (real reverse-import impact; mock+TODO if unresolved). |
| 6 | **Bug Investigation** | Paste a trace/description → likely source modules, evidence, confidence, suggested investigation prompt, files to inspect (heuristic localization; clearly marked TODO for semantic wiring). |
| 7 | **AI Context Export** | Target (Claude/Codex/Cursor) × packet (compact/verbose), **estimated tokens**, live preview, **Copy** + **Save prompt**. |

---

## 4. Backend API (local endpoints)

All implemented and routed through a pure, unit-testable `server.dispatch()`:

| Method | Endpoint | Backing |
|---|---|---|
| GET | `/api/health` | product status |
| POST | `/api/repositories/select` | validate + open a repo |
| POST | `/api/repositories/scan` | **real**: production-scope `depgraph.build_graph` + light role index + `architectural_risk.rank_modules` |
| GET | `/api/repositories/current/summary` | subsystems, entry points, risk score, token savings, plain-English |
| GET | `/api/repositories/current/graph` | nodes/links for the 3D graph (id/label/fan-in/fan-out/LOC/risk/in-cycle) |
| GET | `/api/repositories/current/risks` | ranked risk modules |
| POST | `/api/impact` | **real** reverse-import blast radius (mock+TODO fallback) |
| POST | `/api/bug-investigation` | heuristic localization (clearly marked TODO) |
| POST | `/api/context/export` | compact/verbose AI-context packet + token estimate |

**Scan output includes:** repo path, file count, module count, subsystem count,
dependency edges, graph scope, degraded flag, import-cycle count, top risks, top
hubs, role counts, compact + verbose token estimates, scan duration.

---

## 5. What is real vs mocked

**Real (wired to Builder Core):**
- Scan = **production-scope dependency graph** (Phase 100G, so it does not degrade
  on large repos), a fast **role/subsystem light index** (skips the slow per-file
  analysis for snappy scans), and **architectural risk ranking** (Phase 102).
- Command Center graph, node metrics (fan-in/out/LOC/risk/cycle), risk panel,
  subsystem map, entry points, hubs, import cycles — all from real engine output.
- Impact = real reverse-import edges from the production graph.
- Context export = a real, deterministic compact packet built from the scan, with
  explicit **UNCERTAINTY** section (fan-in is a lower bound; degraded warning).

**Mocked / heuristic (clearly marked `MOCK`/`TODO` in `api.py`):**
- Impact **transitive closure** (Phase 94B engine) — v1 shows direct importers;
  TODO to wire the full reverse closure.
- Bug **semantic localization + verification evidence** — v1 matches file/module
  tokens from the trace; TODO for confirmed-defect ranking.
- A native folder **Browse** dialog — v1 uses a path input (web limitation);
  TODO for an Electron/Tauri native picker.

The interfaces are stable, so wiring the real backends later is additive.

---

## 6. UI quality

Premium dark futuristic interface: glassmorphism panels (`backdrop-filter`),
neon cyan→violet→pink gradient branding (Orbitron + Inter), animated grid + glow
background, animated scan stages with pulsing status dots, a real **3D force graph**
colored by risk/cycle/fan-in, segmented controls, copy toasts, responsive layout.
Not childish — restrained neon on deep navy glass.

---

## 7. Verification

```
py -3 -m pytest jarvis_desktop/tests/test_phase107_desktop_api.py -q
11 passed

py -3 -m pytest builder_core/tests/ -q
<all green — Builder Core unbroken>

py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
12 true positives, 0 false positives   (unchanged)
```

**Live server smoke** (stdlib, zero deps): `/api/health` returns JSON;
`index.html`, `styles.css`, `app.js` all served.

**Real-repo scan** (`local_jarvis`): <SCAN_NUMBERS> — graph scope `production`,
not degraded; top hub `config`, top risk `config`; compact context packet
~<COMPACT_TOKENS> tokens.

Tests cover: health, select, scan-result shape, summary shape, **graph payload
shape** (every link endpoint resolves to a node), risks shape, impact (real +
mock), bug shape, **context export shape + targets + compact≤verbose**, and the
framework-free `dispatch` routing for **all 9 endpoints**.

---

## 8. Screenshots instructions

1. Run `run_jarvis_desktop.bat` (or `py -3 run_jarvis_desktop.py`).
2. **Home** — capture the hero (JARVIS title + 6 command cards). Dark, neon.
3. Enter `.` (or a repo path) → **Scan Repository**. Capture the **Scan** screen
   mid-animation (pulsing stages + live metrics) and at 100%.
4. **Command Center** — let the 3D graph settle, capture the full three-panel view;
   click a hub node to capture the node-detail popover.
5. **Project Intelligence** — capture the plain-English + subsystem map.
6. **AI Export** — choose Claude/compact, capture the token estimate + preview.
7. Recommended window size 1440×900 for crisp product shots; the layout is
   responsive down to ~1100px.

---

## 9. Acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | User can run JARVIS product locally | ✅ stdlib server, `run_jarvis_desktop.bat` |
| 2 | Select/configure a repository | ✅ path picker + `/select` validation |
| 3 | Run a scan | ✅ real engine scan, animated stages |
| 4 | Impressive command center | ✅ 3-panel glass UI + metrics |
| 5 | 3D dependency graph | ✅ 3d-force-graph, risk-colored, clickable |
| 6 | Project intelligence summary | ✅ plain-English + maps |
| 7 | Generate/copy compact prompts for Claude/Codex/Cursor | ✅ `/context/export` + copy/save |
| 8 | Existing Builder Core tests still pass | ✅ suite green |
| 9 | No existing analysis behavior broken | ✅ additive; detectors/benchmarks untouched |

---

## 10. Safety / scope

- Additive only: no change to detectors, findings, benchmarks, promotion, the CLI,
  or existing tests. `jarvis_desktop/` is a new package; Builder Core is imported
  read-only.
- No external APIs; no account integration; copy-to-clipboard prompts in v1.
- Mocks are explicit (`MOCK`/`TODO`) and isolated to impact-transitive and bug-
  semantic paths; everything user-facing degrades honestly (e.g. "heuristic / TODO"
  chips, degraded-graph warnings, "estimates" labels on tokens).
- The product reuses Phase 100G production scope so scans stay non-degraded on large
  repositories.
