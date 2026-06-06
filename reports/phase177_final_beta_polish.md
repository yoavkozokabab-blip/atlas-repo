# Phase 177 — Final Beta Polish

**Date:** 2026-06-06  
**Scope:** Everything that would make a real developer abandon Atlas in the first week  
**No code changes. Audit and execution plan only.**

---

## System Status Overview

| System | Status | Worst finding |
|--------|--------|---------------|
| Installation | NEEDS POLISH | Port conflict still fails silently (175C confirmed) |
| Launch experience | NEEDS POLISH | Onboarding calls small demo — 0 files on first use |
| Demo repositories | BLOCKER | Small demo default, `function:` prefix in impact paths |
| First scan | READY | Trust integrity 10/10 (174F) |
| First Change Plan | NEEDS POLISH | 9 internal-vocabulary strings in Advanced output |
| Impact Analysis | NEEDS POLISH | `function:` prefix in direct impact list |
| Investigation | NEEDS POLISH | "Reported:" prefix on user's own symptom |
| Copy to Claude | NEEDS POLISH | 6 trust-system fields in clipboard |
| Feedback | NEEDS POLISH | Local-only; no remote route configured |
| Support | READY | support@useatlas.dev present; support bundle clean |
| Admin visibility | NOT READY | Design-only; no unified beta ops view |
| Update flow | NEEDS POLISH | URL not configured; changelog empty |
| Beta operations | NOT READY | No retention tracking; no install cohort data |

---

## P0 Findings — Must Fix Before First User Installs

### P0-01: Default demo produces zero matched files

**Location:** `jarvis_desktop/static/app.js:270, 534`  
**Finding:** `onboardingLoadSample()` calls `loadDemoMode("small")`. The small demo (5 modules: alpha.py, beta.py, ring/x.py, ring/y.py, core/hub.py) produces **0 matched files** on every standard first-use prompt ("add rate limiting," "add authentication," "add logging," "add caching"). First impression: `## Files (top 5): - (none)`.  
**Fix:** Change `"small"` → `"medium"` in both call sites. Two words. Medium demo produces `api/handlers.py`, `services/auth.py` with medium-high confidence on standard prompts.  
**Effort:** 5 minutes.

---

### P0-02: `function:` prefix leaks raw graph node IDs into impact output

**Location:** `jarvis_desktop/impact_engine/engine.py` (impact resolution) → displayed in `export_minimal`, `export_full`, and UI  
**Finding:** Direct impact list for `api/handlers.py` includes:
```
- function:api/handlers.py
- function:ui/dashboard.py
- list_routes
```
`function:api/handlers.py` and `function:ui/dashboard.py` are internal graph node IDs where the type prefix was not stripped. `list_routes` is a bare function name. A developer reading the impact export sees these alongside real file paths and cannot distinguish file paths from function references.  
**Fix:** Strip the `function:` prefix from display paths. Filter out bare function names that don't resolve to file paths. Show them separately or not at all.  
**Effort:** 2–3 hours.

---

### P0-03: Port conflict crashes Atlas silently — confirmed in Phase 175C

**Location:** `run_atlas.py`, `jarvis_desktop/server.py`  
**Finding:** Phase 175C reproduced: bind a listener on port 8822, run Atlas on 8822, get `PermissionError: [WinError 10013]` with no fallback. Browser opens to nothing. User assumes Atlas is broken.  
**Fix:** Try ports 8777–8779. If all fail, serve a static "Atlas is already running" HTML page.  
**Effort:** 2–3 hours.

---

### P0-04: Unicode traceback on CP1252 console (startup failure path)

**Location:** `run_atlas.py` startup failure printing  
**Finding:** Phase 175C: source-mode startup failure with redirected CP1252 console raises `UnicodeEncodeError: 'charmap' codec can't encode character '✗'`. The cross-mark (✗) in the startup failure output cannot encode on Windows CP1252 consoles. The user sees a Python traceback instead of the intended startup error message.  
**Fix:** Replace Unicode checkmarks/crosses with ASCII equivalents (`[X]`, `[ok]`). Or wrap all console output in `errors='replace'`.  
**Effort:** 1 hour.

---

## P1 Findings — Fix Before 20 Users

### P1-01: 6 trust-system fields in clipboard content

**Location:** `jarvis_desktop/repository_memory.py:memory_text()`  
**Finding:** The session export prepended to every clipboard copy includes:
```
scan_id: 7213af3b
scan_signature: f05e1663754a
generated_at: 2026-06-06T11:50:04Z
freshness_status: fresh
replay_warning: This context is only valid...
delta: none  [first scan]
```
These are internal trust-integrity fields. They mean nothing to Claude. They create visual noise that makes the product look like it's outputting debug logs.  
**Fix:** Move these fields to a hidden `<!-- trust: ... -->` block or a separate API response field. Show only repository architecture facts in the clipboard text:  
```
ATLAS_REPOSITORY_MEMORY v1
repo: fastapi
modules: 73  edges: 159  graph_health: watch
hubs: fastapi._compat.v2 (17), fastapi.exceptions (13)
risks: fastapi.param_functions, fastapi.security.oauth2
subsystems: fastapi, scripts
```
**Effort:** 2 hours.

---

### P1-02: "Detected concept: Rate Limiting — Rate Limiting" duplicate rendering artifact

**Location:** `jarvis_desktop/planning_engine.py` concept formatting  
**Finding:** The formatted plan output contains `Detected concept: Rate Limiting — Rate Limiting`. The concept name is joined with itself using an em dash separator from an internal template. This appears on every plan that matches a known concept. It signals unfinished software to any developer who reads it carefully.  
**Fix:** Remove the duplicate. Show: `Detected concept: Rate Limiting`.  
**Effort:** 30 minutes.

---

### P1-03: "Evidence score 118/100" — score exceeds its own scale

**Location:** `jarvis_desktop/planning_engine.py` evidence scoring  
**Finding:** In the Advanced (full) plan output: `Evidence score 118/100 — AST definitions/references match: rate`. A score cannot logically exceed 100. Developers who see this assume the software has a bug. The score is a weighted internal metric — this context is absent for the user.  
**Fix:** Either cap display at 100, remove the numeric display entirely and use a label ("High / Medium / Low"), or rename to "Match strength: High."  
**Effort:** 1 hour.

---

### P1-04: 9 internal-vocabulary strings in Advanced plan output

**Location:** `jarvis_desktop/planning_engine.py` formatted output  
**Finding (confirmed live):**
1. `Knowledge quality: Source-backed` — internal confidence classification
2. `Concept confidence: high · Repo mapping: high` — internal scoring dimensions
3. `Insertion confidence 59/100` — unexplained insertion concept, score without scale
4. `AST definitions/references match: rate` — raw AST implementation detail
5. `Recommended insertion: fastapi/_compat/v2.py` — what is "insertion"?
6. `Domain implementation steps:` — sounds like a requirements document
7. `Knowledge-backed risks:` — implies there are "non-knowledge-backed risks"
8. `REPOSITORY EVIDENCE` section header — internal section name
9. `Recommended insertion:` + `score X/100` per file — internal file scoring

**Fix (Beginner mode):** Hide all 9 in Beginner mode. Show only: Goal, Files, May break, Copy for Claude.  
**Fix (Advanced mode):** Rename to user vocabulary:
- "Match strength: High" (not "Evidence score 118/100")
- "Files to check first:" (not "MUST inspect:")
- Collapse the "REPOSITORY EVIDENCE" section by default  

**Effort:** 3–4 hours.

---

### P1-05: "Reported: [symptom]" prefix on user's own words in investigation output

**Location:** `jarvis_desktop/planning_engine.py` investigation formatting  
**Finding:** User types "why are requests slow?" Investigation returns: `Symptom: Reported: "why are requests slow?". Likely area: api/routes.py.`  
The `Reported:` prefix is an internal planning engine label. It adds no information. Appending `. Likely area: api/routes.py.` to the symptom field conflates the symptom and the hypothesis.  
**Fix:** `Symptom: why are requests slow?` — no prefix, no appended hypothesis.  
**Effort:** 30 minutes.

---

### P1-06: Internal error string in root cause output

**Location:** `jarvis_desktop/planning_engine.py` insufficient evidence response  
**Finding:** When Atlas can't find a root cause: `Insufficient evidence. Atlas did not find enough repository evidence for a strong root cause (best evidence score 36/100, threshold 50). Provide a stack trace, error message, or exact file path and re-run.`  
The numeric threshold (50) and score (36/100) are internal implementation details exposed to users.  
**Fix:** `Atlas couldn't identify a confident root cause from the symptom alone. Try adding a file path or error message for better results.` Remove all numeric references.  
**Effort:** 30 minutes.

---

### P1-07: "JARVIS Demo Mode" in demo source files

**Location:**
- `jarvis_desktop/demo/small_repo/core/hub.py:1`: `"""Demo hub module — bundled sample for JARVIS Demo Mode."""`
- `jarvis_desktop/demo/sample_repo/core/hub.py:1`: Same
- `jarvis_desktop/demo/generate_demo_packs.py:17,37`: Generates READMEs with "# JARVIS Demo — Medium/Large"

**Finding:** Any developer who opens the demo repo folder or views file contents sees "JARVIS" instead of "Atlas."  
**Fix:** Replace all instances with "Atlas Demo."  
**Effort:** 15 minutes.

---

### P1-08: Changelog page is empty

**Location:** `jarvis_desktop/static/changelog.html`  
**Finding:** "Versioned public release notes will appear here as external beta builds are shared." This placeholder has been present since before version 0.1.0-beta shipped. A developer checking what Atlas can do or what changed finds nothing.  
**Fix:** Write one real entry:
```
## 0.1.0-beta — June 2026
First external beta release.
- Local-first repository scanning (Python, TypeScript)
- Change Plan: files, order, and risks for any described feature
- Impact analysis: dependency blast radius before editing
- Investigation: symptom-to-file hypothesis
- AI context export for Claude, Cursor, and Codex
```
**Effort:** 10 minutes.

---

### P1-09: Onboarding still has three screens before any action

**Location:** `jarvis_desktop/static/app.js`, `jarvis_desktop/static/index.html`  
**Finding:** Welcome screen → Onboarding card → Home screen, each requiring a dismissal before the next appears. Phase 173B measured 10–15% drop-off at the onboarding step.  
**Fix:** Merge Welcome + Onboarding into a single card. One primary CTA: "Load Sample Repository." No multi-step walkthrough on first launch.  
**Effort:** 1 day UI work.

---

### P1-10: "Copy for Claude" not the dominant CTA after generating a plan

**Location:** `jarvis_desktop/static/atlas_zero_friction.js`, `jarvis_desktop/static/index.html`  
**Finding:** After plan generation, "Copy for Claude" appears inside a `sendToAiPanel` div that is part of the plan result. It's not anchored or sticky. On longer plans with rollback sections and architectural risks, it can be below the fold. Phase 173B measured 15–25% of plan creators never copy.  
**Fix:** Pin "Copy for Claude" as a floating action or place it immediately after the Files section, before any secondary content.  
**Effort:** 2 hours.

---

## P2 Findings — Fix Before Public Beta

### P2-01: "Status: Implemented" when user asked to add something

**Finding:** When a plan matches an existing partial implementation: `Status: Implemented`. User typed "add rate limiting." User reads "Status: Implemented" and thinks either the tool is wrong or the feature already exists.  
**Fix:** Rename to "Related code found:" or "Partial implementation exists:" with a brief note.

### P2-02: MEMORY_EXPORT mode computed but not in UI

**Finding:** `export_memory` (ATLAS_DELTA v1) is computed on every workflow — 57% smaller than minimal. The UI only offers FULL and MINIMAL. Users send 2× more tokens than necessary.  
**Fix:** Add a third copy mode "Memory mode" that uses the delta after the memory header is sent once.

### P2-03: Scan stage labels are internal pipeline names

**Finding:** "Generating verification evidence," "Extracting contracts," "Building AI context packets" — these are implementation stages, not user-facing progress labels. A 20-second Django scan with 7 scrolling technical stage names creates anxiety.  
**Fix:** "Scanning files," "Building dependency map," "Analyzing risks," "Ready."

### P2-04: Beginner/Advanced toggle is poorly named

**Finding:** "Beginner" and "Advanced" describe skill level. The toggle changes output verbosity. A senior engineer will switch to Advanced expecting better output, then see internal scores and labels.  
**Fix:** Rename to "Summary" / "Full detail" or simply remove the toggle and default to a clean summary view.

### P2-05: "What breaks?" nav label is good; tooltip is missing

**Finding:** "What breaks?" is clear. But users arriving at the Impact view see an empty text input with no guidance on what format to use. The placeholder says `e.g. config.py  or  builder_core/ask.py` — but in the demo, users don't know the file names. There's no file picker.  
**Fix:** Add a "Pick from scanned files" dropdown populated from the scan index.

### P2-06: macOS/Linux binary installer missing

**Finding:** Windows-only binary. Mac users (35–40% of developer market) must clone `C:\J.A.R.V.I.S\local_jarvis` to run Atlas. The path itself is a trust issue.  
**Fix:** PyInstaller macOS `.app` bundle. Estimated 1–2 days. Not needed for 5 supervised users, needed for 20+.

---

## P3 Findings — Later

- `LEGACY_RECENT_KEY = "jarvis_recent_repos"` in `app.js` — old localStorage key name (not user-visible but messy)
- `EV_KEY = "jarvis_events"` in `marketing.js` — old key name
- `__init__.py` PRODUCT_VERSION `"phase107-mvp"` still stale
- The "Rollback plan" section in full plan output is generic git advice every developer already knows
- "Or explore by task" card section on Home page — 5 cards before any action taken

---

## Complete Execution Plan

### Before first user installs (Days 1–2)

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 1 | Switch default demo to medium | `app.js:270,534` | 5 min |
| 2 | Fix `function:` prefix in impact paths | `impact_engine/engine.py` | 2–3h |
| 3 | Fix port conflict recovery | `run_atlas.py`, `server.py` | 2–3h |
| 4 | Fix Unicode crash on startup failure | `run_atlas.py` | 1h |
| 5 | Write changelog entry (0.1.0-beta) | `changelog.html` | 10 min |
| 6 | Fix "Reported:" prefix in investigation | `planning_engine.py` | 30 min |
| 7 | Fix concept duplicate rendering | `planning_engine.py` | 30 min |
| 8 | Fix JARVIS in demo files | `demo/*/hub.py`, `generate_demo_packs.py` | 15 min |

**Total: ~7 hours. Must be done before Day 1.**

### Before 20 users (Week 1–2)

| # | Fix | File(s) | Effort |
|---|-----|---------|--------|
| 9 | Strip trust metadata from clipboard | `repository_memory.py:memory_text()` | 2h |
| 10 | Fix "Evidence score 118/100" | `planning_engine.py` | 1h |
| 11 | Fix internal vocabulary in Advanced mode | `planning_engine.py` | 3–4h |
| 12 | Fix internal error string in investigation | `planning_engine.py` | 30 min |
| 13 | Pin "Copy for Claude" above fold | `atlas_zero_friction.js` | 2h |
| 14 | Collapse onboarding to one screen | `app.js`, `index.html` | 1 day |
| 15 | Configure `ATLAS_UPDATE_CHECK_URL` | Infra | 1h |
| 16 | Configure `ATLAS_FEEDBACK_URL` | Infra | 2h |

**Total: ~2–3 days. Must be done before 20 users.**
