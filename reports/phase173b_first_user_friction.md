# Phase 173B — First User Friction Hunt

**Date:** 2026-06-05  
**Role:** UX research (assume user knows nothing about Atlas)  
**Journey:** Install → first successful use with Claude  
**Method:** Walkthrough of `index.html`, `app.js`, `atlas_*` scripts, `quickstart.html`, `support.html` (no code changes)

---

## Executive summary

| Question | Answer |
| --- | --- |
| **Can a random developer discover Atlas value within 5 minutes?** | **PARTIAL** — **Yes** on the golden path (Load Sample → Change Plan → Copy for Claude, ~3–4 min). **No** if they install cold and self-navigate without clicking Load Sample (~40% likely to abandon before first export). |
| **Biggest friction theme** | **Too many front doors** (Welcome + Onboarding + Home picker + nav labels) before one clear win. |
| **Second biggest** | **Two export systems** (workflow “Copy for Claude” vs “Send to AI” compact packets) — users don’t know which to paste. |

---

## Journey map (naive developer)

| Step | Time | What happens | Friction level |
| --- | ---: | --- | --- |
| 0 Install | 0–3 min | `.exe` SmartScreen or `Launch Atlas.bat` + Python check | High (non-installer) |
| 1 Land | +10s | Boot splash → Welcome overlay OR Home | Medium |
| 2 Orient | +30–90s | Read hero, nav, path picker, demo packs | **High** |
| 3 Scan | +5–60s | Sample load fast; own repo slower | Low (sample) / High (own) |
| 4 Plan | +30s | Generate Change Plan | Medium (label mismatch) |
| 5 Export | +20s | Find Copy for Claude | Medium (two export UIs) |
| **Total (golden path)** | **~3–4 min** | Value = grounded file list + paste-ready prompt | ✅ |

---

## Friction catalog by area

### Install & first launch

#### F-01 — Python / terminal visible on source launch
- **Problem:** `Launch Atlas.bat` opens a console; failure ends in terminal text, not in-app UI.
- **Impact:** Non-developers abandon; developers feel “unfinished.” Blocks reach browser entirely if Python missing.
- **Location:** Install / `Launch Atlas.bat`, `run_atlas.py`; Support → Install notes.
- **Exact fix:** Installer-only path in docs; silent `Launch Atlas.vbs`; in-browser “Atlas couldn’t start” page with one recovery link.
- **Priority:** **P0**

#### F-02 — Windows SmartScreen unsigned warning
- **Problem:** First launch requires “More info → Run anyway” with no in-product preview.
- **Impact:** Trust drop before any value; many users never open the app.
- **Location:** Pre-install / first double-click `Atlas_Setup.exe`; mentioned only in `quickstart.html`.
- **Exact fix:** Add 3-line “First launch on Windows?” card to Welcome screen with screenshot-style steps.
- **Priority:** **P1**

#### F-03 — Brand name inconsistency (Atlas vs ATLAS)
- **Problem:** Welcome says “Atlas”; hero and onboarding say “ATLAS”; subtitle “Repository Intelligence Platform.”
- **Impact:** Mild confusion; feels beta/unpolished.
- **Location:** `index.html` — `#welcomeScreen`, `.hero-title`, `#onboarding`, `<title>`.
- **Exact fix:** Pick **Atlas** everywhere; demote “Repository Intelligence Platform” to optional subtitle once.
- **Priority:** **P2**

---

### Onboarding & first screen

#### F-04 — Triple onboarding layers
- **Problem:** Welcome overlay → (optional) Onboarding overlay → Home hero → optional Guided Walkthrough (8 steps).
- **Impact:** Cognitive overload; user doesn’t know which button is “the” start.
- **Location:** `#welcomeScreen`, `#onboarding`, `#guidedWalkthroughPanel`, Home hero (`index.html` L96–101).
- **Exact fix:** Single first-run flow: Welcome with **one** primary CTA “Try sample (1 min)” and collapse onboarding into Welcome body; defer 8-step tour behind “Show me around (optional).”
- **Priority:** **P0**

#### F-05 — “Use my own repository” dumps to full Home picker
- **Problem:** Dismiss Welcome → second onboarding OR full path UI (Validate, scope, demo packs, recent).
- **Impact:** User believes they must paste a path before anything works; abandons.
- **Location:** `welcomeStartWalkthrough` / `dismissWelcomeScreen` → `maybeShowOnboarding()` → Home `#repoPath`.
- **Exact fix:** After “Use my own repository,” show **focused** sub-screen: path + Browse only; hide demo pack grid and Advanced scope behind “More options.”
- **Priority:** **P0**

#### F-06 — Home “explore by task” cards bypass scan gate
- **Problem:** Cards call `go('build')` etc. while nav is locked visually but **still clickable**.
- **Impact:** Empty states / confusion — “Scan first” after user thought they started a task.
- **Location:** Home `details.home-explore` cards; nav `data-lock` only lowers opacity (`styles.css` L35).
- **Exact fix:** Disable card clicks until `STATE.summary.ok`; or route to “Load sample first” modal.
- **Priority:** **P1**

---

### Terminology & navigation

#### F-07 — Nav label ≠ button label ≠ outcome
- **Problem:** Nav: **Change Plan**; scan success: **Generate your first Change Plan**; action button: **Generate Change Plan**; quickstart: **Change Plan**.
- **Impact:** Hesitation — “Am I in the right place?”
- **Location:** `#nav` build button; `#view-build` button; `goToFirstBuildPlan()` toast.
- **Exact fix:** Unify to **“Change Plan”** on nav + primary button; scan CTA: **“Create your first Change Plan.”**
- **Priority:** **P1**

#### F-08 — Seven top-level nav items before first win
- **Problem:** Home, Scan, Codebase Map, Change Plan, Investigate Bug, What breaks?, Send to AI.
- **Impact:** Paradox of choice; Map and Copilot distract from plan→export loop.
- **Location:** `index.html` header `#nav`.
- **Exact fix:** Beginner mode: show **Home · Change Plan · Send to AI** only until first successful plan; unlock rest with “More tools.”
- **Priority:** **P1**

#### F-09 — “What breaks?” vs Impact vs blast radius
- **Problem:** Three phrases for same workflow; “What breaks?” is colloquial but vague.
- **Impact:** Users scanning for “impact analysis” or “dependencies” miss it.
- **Location:** Nav `#view-impact`; help text “blast radius.”
- **Exact fix:** Nav label: **“Impact check”** with subtitle tooltip “What breaks if I change this file?”
- **Priority:** **P2**

#### F-10 — Beginner / Advanced toggle unexplained
- **Problem:** Toggle in header with no first-run explanation; hides/shows evidence panels.
- **Impact:** Users toggle accidentally and lose trust signals—or never see evidence.
- **Location:** `#modeToggle` in topbar.
- **Exact fix:** Default Beginner; first toggle shows one-line tooltip: “Advanced shows evidence and raw markdown.”
- **Priority:** **P2**

---

### Scan & loading

#### F-11 — Scan button disabled until Validate
- **Problem:** User must discover Validate step; Scan stays disabled silently.
- **Impact:** “Broken app” moment on own-repo path.
- **Location:** `#scanBtn` disabled; `setScanEnabled()` in `app.js`.
- **Exact fix:** Enable Scan after non-empty path with inline hint “Validate recommended”; or auto-validate on blur.
- **Priority:** **P1**

#### F-12 — Scan stage labels are internal jargon
- **Problem:** Stages include “Generating verification evidence”, “Extracting contracts”, “Building AI context packets.”
- **Impact:** Anxiety during wait; sounds like ML pipeline user doesn’t understand.
- **Location:** `STAGES` in `app.js` L659–660; `#stages` during scan.
- **Exact fix:** User-facing labels: “Reading files → Mapping imports → Summarizing architecture → Almost done.”
- **Priority:** **P1**

#### F-13 — “~60 seconds” oversells sample path
- **Problem:** Copy says sample load “about 60 seconds”; small demo is often &lt;10s; large pack is longer.
- **Impact:** Mistrust when numbers don’t match; or surprise when large pack slow.
- **Location:** Empty states / onboarding “about 60 seconds.”
- **Exact fix:** “Usually under a minute” or show live timer on scan screen only.
- **Priority:** **P3**

#### F-14 — Scan success doesn’t auto-run first plan
- **Problem:** By design (Phase 155) user must click second CTA after success.
- **Impact:** +1 click; some users stop at success screen thinking they’re done.
- **Location:** `#scanSuccess` buttons; `promptFirstBuildPlanAfterScan` toast only.
- **Exact fix:** Optional prominent default: primary button **“Create Change Plan now”** that navigates + pre-fills example (already exists — make it pulse once).
- **Priority:** **P2**

#### F-15 — Browse folder fails → manual path
- **Problem:** Browse may return unsupported; user must paste path.
- **Impact:** High friction on Windows; feels broken.
- **Location:** `browseRepoFolder()` toasts.
- **Exact fix:** On browse fail, open inline path helper with example `C:\dev\my-app` and Validate autofocus.
- **Priority:** **P1**

---

### Workflows (Build / Investigate / Impact)

#### F-16 — Change Plan output density
- **Problem:** First plan shows domain knowledge, evidence, rollback, impact simulation, confidence pills.
- **Impact:** User can’t tell what to paste into Claude; “success” doesn’t feel like success.
- **Location:** `runChangePlan()` output in `app.js`; Beginner mode still dense.
- **Exact fix:** Beginner: collapse to **Goal · Top files · Order · Copy for Claude**; tuck rollback/advanced under “Details.”
- **Priority:** **P0** (value realization)

#### F-17 — Impact requires module path
- **Problem:** “What file or module do you want to change?” with no picker.
- **Impact:** Blank hesitation; wrong paths → refusal or low trust.
- **Location:** `#impactTarget` placeholder.
- **Exact fix:** “Pick from map” button + dropdown of top 10 modules from scan.
- **Priority:** **P1**

#### F-18 — Investigate placeholders are developer-specific
- **Problem:** Examples mention backtest, PnL, scan graph — confuse non-trading users.
- **Impact:** “This isn’t for my codebase.”
- **Location:** `#investigateSymptom` placeholder.
- **Exact fix:** Neutral examples: “Login fails after deploy”, “Tests pass locally but fail in CI.”
- **Priority:** **P2**

---

### Export & Claude handoff

#### F-19 — Two export systems
- **Problem:** (A) Per-workflow **Copy for Claude** on plan (`sendToAiPanel` / minimal export). (B) **Send to AI** tab with compact/verbose **context packets** (repo-wide, not plan-specific).
- **Impact:** **Major** — user pastes wrong packet into Claude; loses plan grounding or duplicates context.
- **Location:** `#view-export` vs `sendToAiPanel` in build/investigate/impact outputs; `refreshExport()` → `/api/context/export`.
- **Exact fix:** Rename nav **“Send to AI”** → **“Repository context”**; after plan, single CTA **“Copy plan for Claude”**; hide export tab until user opens “Advanced: full repo context.”
- **Priority:** **P0**

#### F-20 — Export tab empty state before plan
- **Problem:** “Scan a repository, then choose a target and packet” — doesn’t say this isn’t the main Claude step.
- **Impact:** User goes to Send to AI first, copies generic context, skips Change Plan.
- **Location:** `#exportPreview` empty; `refreshExport()`.
- **Exact fix:** Empty copy: “Tip: create a **Change Plan** first — then use **Copy for Claude** on that screen.”
- **Priority:** **P1**

#### F-21 — Session + delta copy not explained
- **Problem:** Panel says “session context sent once per scan + this question’s files” — assumes Phase 169/171 memory knowledge.
- **Impact:** Confusion about what to paste when; double-paste or omit session.
- **Location:** `atlas_zero_friction.js` `sendToAiPanel` description.
- **Exact fix:** “**One copy includes everything** Claude needs for this plan. Paste once per new chat.”
- **Priority:** **P1**

#### F-22 — “You’re ready” appears only after first build
- **Problem:** Easy to miss; no equivalent after first successful copy to Claude.
- **Impact:** User unsure if workflow complete.
- **Location:** `#readyState` / `afterChangePlanSuccess()`.
- **Exact fix:** After copy, toast: **“Pasted into Claude? Ask it to implement the plan step by step.”** + checkmark on plan card.
- **Priority:** **P2**

---

### Codebase Map & Copilot

#### F-23 — 3D map as default post-scan suggestion
- **Problem:** Toast “Repository Map ready” competes with Change Plan CTA.
- **Impact:** Tourist mode in graph; never reaches export.
- **Location:** `finishScanSession` toast for non-demo scans.
- **Exact fix:** First-run: toast only **“Create your first Change Plan”**; defer map toast until after first plan.
- **Priority:** **P1**

#### F-24 — Codebase Map cognitive wall
- **Problem:** Module / Architecture / Hierarchy, 3D navigation, Module Inspector, Copilot — expert UI on day one.
- **Impact:** Overwhelm; feels like separate product.
- **Location:** `#view-center`.
- **Exact fix:** First visit: 2D simplified architecture view + “Open 3D map” opt-in.
- **Priority:** **P2**

#### F-25 — Copilot third AI surface
- **Problem:** Map sidebar Copilot + plan export + Send to AI tab = three “ask AI” paths.
- **Impact:** Fragmented mental model.
- **Location:** `#askInput`, copilot card.
- **Exact fix:** Beginner: hide Copilot until after first export; label “Optional: ask about the map.”
- **Priority:** **P2**

---

### Trust, errors & support

#### F-26 — “Planning only” disclaimer reads as limitation
- **Problem:** Beta notice says Atlas doesn’t edit files — before user sees any output.
- **Impact:** Some interpret as “doesn’t work with Claude/Cursor.”
- **Location:** Home `.beta-notice`.
- **Exact fix:** Reframe: **“Atlas prepares the plan; your AI tool writes the code.”**
- **Priority:** **P1**

#### F-27 — Confidence / trust blocks without primer
- **Problem:** “Confidence: medium-high”, evidence panels, graph health — no legend for beginners.
- **Impact:** Misread as error or marketing fluff; trust loss if medium-low.
- **Location:** `atlas_trust.js`, plan cards.
- **Exact fix:** One-line legend first time: “Confidence = how well this repo’s graph supports this answer.”
- **Priority:** **P2**

#### F-28 — Support page recovery actions scary for new users
- **Problem:** “Rebuild index”, “Clear cache” visible early via Help.
- **Impact:** Fear of breaking install; accidental cache clear.
- **Location:** `support.html` Recovery actions.
- **Exact fix:** Move recovery behind “Troubleshooting”; default Support = Quickstart link + diagnostics copy.
- **Priority:** **P2**

#### F-29 — Scan failure codes partial
- **Problem:** Friendly messages exist but `partial_graph` / `symbols_missing` still scary.
- **Impact:** User thinks scan failed when it partially succeeded.
- **Location:** `showScanFailed` vs degraded success paths.
- **Exact fix:** Never use “Scan failed” title for partial success; use **“Scan complete with limitations.”**
- **Priority:** **P1**

---

### Loading & performance perception

#### F-30 — Boot splash + welcome + scan skeleton
- **Problem:** Three loading patterns in first 2 minutes.
- **Impact:** Feels slow even when fast.
- **Location:** `#bootSplash`, scan skeleton, demo load.
- **Exact fix:** Sample path: skip scan view entirely — inline “Preparing sample…” on Home with progress bar.
- **Priority:** **P2**

---

## Value realization scorecard

| Signal user understands | Golden path | Cold start |
| --- | --- | --- |
| What Atlas does | ✅ after Welcome | ⚠️ buried in hero |
| What to click first | ✅ Load Sample | ❌ path picker |
| What success looks like | ⚠️ after plan | ❌ |
| What to paste into Claude | ⚠️ if finds Copy button | ❌ |
| That Atlas is local/safe | ✅ Home picker note | ✅ |

---

## Final answer

**Can a random developer discover Atlas value within 5 minutes?**

**PARTIAL — YES on rails, NO off rails.**

- **YES (~3–4 min)** if they: install successfully → **Load Sample Repository** → **Generate your first Change Plan** → **Copy for Claude** on the plan card.
- **NO (&lt;50% within 5 min)** if they: dismiss sample → paste path → explore **Codebase Map** or **Send to AI** first → never generate a plan.

**To make YES the default for random developers:** collapse onboarding (F-04), simplify first plan UI (F-16), unify export (F-19), and reduce nav to three items until first copy (F-08).
