# Phase 147 — First User Experience Audit

**Date:** 2026-06-02  
**Method:** Observation-only walkthrough of the current product (Phases 143–146). No code changes.  
**Persona:** Developer who has **never heard of Atlas** and will **not** read `docs/ATLAS_QUICKSTART.md` or other documentation.  
**Start:** Double-click `Launch Atlas.bat` in `local_jarvis/`.  
**Success definition:** User receives a **successful Build Plan** — `POST /api/planning/change` succeeds and the UI shows a populated Change Plan card (implementation order, affected files/modules, or equivalent grounded output).

**Inputs reviewed:** `Launch Atlas.bat`, `run_atlas.py`, `index.html`, `app.js`, `atlas_beta.js`, `atlas_polish.js`, `support.html`, Phase 142/144/146 reports.

**Phase 145 note:** No `phase145_*.md` artifact exists. This audit treats Phase 146 polish as the baseline and stress-tests the advertised happy path.

---

## Executive summary

| Verdict | Detail |
|---------|--------|
| **Can a naive user reach Build Plan success without docs?** | **Yes, on the happy path** — if Python 3.10+ and `py` launcher work, and they click **Load Sample Repository** then **Generate Change Plan**. |
| **Likely to succeed on first try?** | **Moderate (~55–65%)** — install/console friction and UI density still lose many first-time users before the second click. |
| **Does success *feel* like success?** | **Weak** — the Build Plan output reads like an internal architecture report, not a clear “you’re done” outcome. |

**Minimum-click happy path (if Welcome → Load Sample):**

1. Dismiss or use Welcome overlay → **Load Sample Repository**  
2. Wait on Scan screen (demo load; often &lt; 5 s)  
3. Auto-redirect to **Build Plan** (pre-filled example)  
4. **Generate Change Plan**  

**Effective clicks to success:** ~3–4, plus a **console window** flash unless the user uses `Launch Atlas.vbs`.

---

## Journey map (observed)

| Step | What the user sees | Cognitive load |
|------|-------------------|----------------|
| 0 | Black **cmd** window: “Starting Atlas… (No pip install needed…)” | Feels like a developer tool, not a consumer app |
| 1 | Browser opens `http://127.0.0.1:8777/` | OK |
| 2 | **Welcome** overlay: “Private beta”, planning-only disclaimer, 3 buttons | Second product name moment (“Atlas” vs later “ATLAS”) |
| 3a | **Load Sample** → Scan view: stages (“Building dependency graph”, “Generating verification evidence”, …) | Jargon-heavy progress |
| 3b | Scan **complete** panel may appear briefly | Easy to miss |
| 4 | **Build Plan** view: example text + “First Build Plan” banner + **Generate Change Plan** | Button label ≠ nav “Build Plan” |
| 5 | Large **Change Plan** card: domain concept, confidence pills, implementation order, rollback, optional impact | High technical density |

**Alternate path (dismiss Welcome → “Use my own repository”):**

- Welcome closes → **second** overlay (**Onboarding**, 4 steps) may appear.  
- Home shows hero + **full repository picker** (path, Validate, Scan scope, Massive Mode, second “Load Sample” area).  
- User can easily believe they **must** paste a path before anything works.

---

## Findings (ranked)

### Critical

| ID | Finding | Why it blocks or breaks first success |
|----|---------|--------------------------------------|
| C1 | **Python / `py` launcher required; failure stops in terminal** | If Python is missing or `py -3` fails, `Launch Atlas.bat` prints install instructions and **`pause`** — user never reaches the browser. No in-app recovery. This is the largest real-world drop-off (Phase 142 #1–#3). |
| C2 | **Launcher exposes a terminal window** | `Launch Atlas.bat` runs in **cmd.exe**. Non-technical users often assume they did something wrong or close the window, killing the server. `Launch Atlas.vbs` exists but is not the default double-click target from installer messaging. |
| C3 | **Success is easy to miss on the demo path** | After sample load, `promptFirstBuildPlanAfterScan` sends users to Build Plan in **~900 ms**, often **before** they read Scan complete or click “Try your first Build Plan.” They may not know a “scan” happened or why Build Plan is now available. |

### Major

| ID | Finding | Category |
|----|---------|----------|
| M1 | **Two stacked first-run modals** | Confusion / unnecessary clicks | Welcome (`atlas_welcome_v141_done`) then, if user chooses “Use my own repository”, **Onboarding** (`atlas_onboarding_v2_done`) can appear immediately after. Feels repetitive; neither says “click once below to see a Build Plan.” |
| M2 | **Home screen contradicts “sample first”** | Misleading expectations | Hero says “Load sample” first, but scrolling reveals a **full repo path form**, Scan scope, Massive Repository Mode, and **duplicate** sample entry (“Sample repository size” cards). Naive users think path entry is **required**. |
| M3 | **“Repository Intelligence Platform” + sci-fi UI** | Technical feel | Subtitle, Orbitron typography, “◈ ATLAS”, grid/glow — reads as internal/dev infrastructure, not a guided product for “I want a plan for my feature.” |
| M4 | **Jargon before value** | Unclear wording | Scan stages: “dependency graph”, “architectural risks”, “verification evidence”, “AI context packets”. Nav: “Repository Map”, “Investigate **Bug**”, “Impact”, “Export”, “Diagnostics”, “Copilot”. |
| M5 | **Build Plan ≠ Generate Change Plan** | Unclear wording | Nav/tab: **Build Plan**. Primary action: **Generate Change Plan**. Output heading: **Change Plan**. First-time users hesitate on whether these are the same feature. |
| M6 | **Build Plan output does not signal clear success** | Misleading expectations / technical feel | Success shows domain panels (“Concept confidence”, “Repo mapping”, “Curated knowledge”), risk level, intent, rollback, optional impact simulation. A novice cannot tell “this worked” vs “this is a debug view.” No plain-language “You’re done — here’s what to do next.” |
| M7 | **Task cards work before scan (partial dead end)** | Dead end / confusion | Cards like “Plan a feature change” call `go('build')` even when nav tabs are locked. User gets an empty/gate panel — recoverable via Load Sample, but feels broken. |
| M8 | **“Planning only — does not write code”** | Misleading expectations | Correct legally, but many beta users expect an **AI that implements**. They may abandon at banner before trying Build Plan (Phase 142 #15). |
| M9 | **Top bar: Support, Diagnostics, Report Issue** | Technical feel / anxiety | Visible on first screen with no tooltips. “Diagnostics” sounds like something is already wrong. |
| M10 | **Guided Walkthrough is 8 steps and not Build-Plan-first** | Unnecessary clicks | Includes Repository Map, Investigate, Impact, Export before “You’re ready.” Only step 4 auto-runs Build Plan. Users who pick tour over Load Sample take a long detour. |
| M11 | **Locked nav is visual-only** | Confusion | `data-lock="1"` dims opacity but **does not block** clicks. Users click greyed **Build Plan** and still enter (gate or content) — inconsistent mental model. |

### Minor

| ID | Finding | Category |
|----|---------|----------|
| m1 | **“Private beta”** on Welcome/Onboarding | Mild anxiety; unclear what’s unstable |
| m2 | **Telemetry banner** (if analytics degraded) | “Telemetry unavailable” — confusing; says analysis unaffected but adds noise |
| m3 | **Toast-only instruction** | “Describe your change, then click Generate Change Plan” disappears in ~2.4 s |
| m4 | **Example request is generic** | “Add structured logging to API handlers” — fine for demo, but user may not recognize it as editable example |
| m5 | **Thumbs up/down on first result** | Fine for beta; adds UI noise before user understands output |
| m6 | **about.html leaves main app** | Welcome footer link opens marketing-style page — context switch |
| m7 | **Export screen: Compact / Verbose / tokens** | Technical; not on critical path but visible in nav |
| m8 | **Scan nav tab always visible** | User can open Scan before selecting repo — empty or confusing running UI |
| m9 | **Repo chip “No repository”** until load | Small signal; OK after sample |
| m10 | **Duplicate branding** “Atlas” vs “ATLAS” | Welcome vs header casing |

---

## Confusion points (narrative)

1. **What is Atlas?** Headline “Map your repository before your AI reads it” suggests Atlas *is* the AI. Subhead mentions Claude/Codex/Cursor — relationship unclear until Export or Build prompt copy.

2. **What should I do first?** Three equal-weight hero buttons (Sample / Walkthrough / Scan my repo) plus five task cards plus repo form — no single obvious “start here” except primary styling on Sample.

3. **Did anything happen after Load Sample?** Fast demo load → route change → Build Plan. No celebratory, plain-language confirmation (“Your sample codebase is ready”).

4. **What does Generate Change Plan produce?** User expects a checklist or ticket list; gets architecture concepts and evidence collapsibles.

5. **Is the product broken because it won’t edit my code?** Planning-only messaging is repeated but easy to skim; disappointment hits after investment.

---

## Unnecessary clicks (relative to goal)

| Click / step | Necessary? | Notes |
|--------------|------------|-------|
| Welcome overlay | Optional | Could default straight to Home with one CTA |
| Onboarding (second modal) | **No** for sample path | Skip if Welcome used |
| Guided Walkthrough (8 steps) | **No** for minimal goal | 4+ steps before Build Plan |
| Dismiss scroll to repo form | **No** | Noise for sample-first |
| Explore Repository Map (auto detour) | **No** | Demo path skips; tour includes it |
| Ask Copilot on scan success | **No** | Thirdary button |
| Expand “Full plan (markdown)” | **No** | Power user |
| Copy Claude / impact simulation | **No** | Post-success |

**Lean path:** Load Sample → Generate Change Plan (2 intentional UI actions after launch).

---

## Misleading expectations

| Message / UI | User belief | Reality |
|--------------|-------------|---------|
| “Map your repository before your AI reads it” | Atlas reads code like ChatGPT | Atlas scans locally and produces plans/packets; user still uses external AI |
| Task cards on Home | Features work immediately | Most need scan except gated empty states |
| Step “Build Plan” in hero strip | They already have a plan | Plan exists only after scan/sample |
| “Try Atlas in under a minute” | Fully automatic | Still requires Generate click |
| Product name “Intelligence Platform” | Automated decisions | Heuristic, planning-only analysis |
| Sample + repo form both prominent | Must configure both | Sample alone is sufficient |

---

## Dead ends

| Scenario | Recovery? |
|----------|-------------|
| Python not installed | Terminal message only; user must leave and install Python |
| Port 8777 in use | Not surfaced in UI audit; blank/failed load possible (Phase 142 #6) |
| User closes cmd window | Server stops; browser stops working — no explanation |
| Scan own repo fails (huge tree, permissions) | Hints + Load Sample on fail panel — **recoverable** |
| Click Export / Impact before scan | Empty states with Load Sample — **recoverable** |
| Startup checks fail | Redirect to `support.html` — **recoverable** if user reads it |
| Build Plan API error | Friendly panel — **recoverable** |

---

## Screens that feel technical

| Screen | Why |
|--------|-----|
| **Terminal launcher** | cmd, Python, pip mention |
| **Scan (running)** | Stage list reads like CI pipeline |
| **Repository Map** | 3D graph, Module/Architecture/Hierarchy, Advanced ▾, Tour, PNG/SVG |
| **System Health** (left panel on map) | Indexed files, edges, unresolved imports, performance ms |
| **Build Plan (result)** | Domain knowledge, confidence, repo mapping, evidence, rollback |
| **Export** | Packet, tokens, Codex |
| **Support** | Environment checks, rebuild index, support bundle |

**Least technical:** Welcome overlay (plain language) and Build Plan **input** box before generation.

---

## Success path scorecard

| Criterion | Pass? | Evidence |
|-----------|-------|----------|
| Reach app without docs | Conditional | Requires working Python + not closing terminal |
| Discover “start” without docs | Partial | Sample is primary but not sole CTA |
| Load sample without path | **Pass** | `loadDemoMode()` |
| Reach Build Plan screen | **Pass** | Auto `goToFirstBuildPlan()` on demo |
| Understand what to click | Partial | Toast + banner; easy to miss |
| Complete generation | **Pass** | `runChangePlan()` on example text |
| Recognize success | **Fail** for novices | Output is expert-oriented |

---

## Recommended focus for a future polish phase (observation only)

Not implemented in Phase 147. Priority order if reducing support burden:

1. **Default launcher without console** (shortcut to `.vbs` or packaged GUI wrapper).  
2. **Single first-run screen** — one modal: “Load sample → Build Plan in 1 minute.”  
3. **Collapse repo picker** until user expands “Use my own repository.”  
4. **Plain-language success state** on Build Plan — 3 bullets + “Copy to Cursor” only.  
5. **Align naming:** Build Plan everywhere, or one verb: “Generate plan.”  
6. **Scan complete:** hold 2–3 s or modal before auto-advance on demo.  

---

## Audit conclusion

Atlas **can** deliver a successful Build Plan without documentation on the **sample-repository path**, assuming install prerequisites. The product still **behaves like a developer instrument** rather than a guided first-run experience: terminal launch, stacked modals, duplicated entry points, and expert-heavy output undermine the Phase 146 goal for non-technical or distracted first-time users.

**Observed readiness for “never heard of Atlas” → successful Build Plan without help:** **6.5 / 10** (up from ~5 pre-146 on this path, held back by install shell, UI density, and weak success recognition).

---

## Appendix: File references

| Behavior | Source |
|----------|--------|
| Welcome / onboarding keys | `atlas_beta.js` — `WELCOME_KEY`, `ONBOARDING_KEY`, `phase141Boot()` |
| Demo → Build redirect | `atlas_polish.js` — `promptFirstBuildPlanAfterScan`, 900 ms delay |
| Scan stages copy | `app.js` — `STAGES` array |
| Locked nav dim only | `styles.css` — `.nav button[data-lock="1"]`; `unlockNav()` on scan complete |
| Build output template | `app.js` — `runChangePlan()` |
| Launcher failure | `Launch Atlas.bat` lines 18–23 |
