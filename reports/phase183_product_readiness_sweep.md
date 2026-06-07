# Phase 183 — Product Readiness Sweep

**Date:** 2026-06-05  
**Scope:** Atlas UI audit only — no implementation, no new systems, no architecture or intelligence work.  
**Assets reviewed:** `jarvis_desktop/static/**/*.{html,js,css}` (primary app, marketing, support, admin, feedback, demo).

## Executive Summary

| Metric | Count |
| --- | --- |
| Issues logged | **42** |
| Critical | **2** |
| High | **12** |
| Medium | **20** |
| Low | **8** |

**Top ship risks**

1. **Demo page ships with a visible placeholder** instead of a real walkthrough video (`demo.html`).
2. **Support contradicts itself on Python** — installer users are told Python is not required, then told to install Python 3.10+ if the app won’t start.
3. **Change Plan CTA naming is fragmented** across five+ variants (`Create`, `Generate Change Plan`, `Generate your first Change Plan`, `Build Plan`).
4. **Engineering labels leak into user UI** — graph health badges (`partial`, `degraded`, `unsupported`), scan reliability categories, and Impact heuristic pills.
5. **Repository Context is hard to discover** — hidden in Simple mode, gated until the first Change Plan, and empty-state copy implies a plan is required when only a scan is needed.

**Estimated remediation (copy + light UX only):** ~18–28 engineer-hours. Demo video production is additional (4–8 h content work).

---

## Severity Legend

| Level | Meaning |
| --- | --- |
| **Critical** | Blocks beta credibility, onboarding, or first-run success |
| **High** | Visible to most users; causes confusion, mistrust, or a broken path |
| **Medium** | Inconsistent naming, weak empty states, or operator-facing leakage |
| **Low** | Dev-only, source comments, or acceptable on internal/operator pages |

---

## Screen Summaries

| Screen | Issue count | Highest severity |
| --- | ---: | --- |
| Home | 7 | High |
| Scan | 6 | High |
| Change Plan | 8 | High |
| Debug | 2 | High |
| Impact | 3 | High |
| Repository Context | 5 | High |
| Admin | 5 | Medium |
| Support | 6 | Critical |
| Feedback | 4 | High |
| Updates | 3 | Medium |
| Demo | 4 | Critical |
| Cross-cutting (Map / API / trust) | 6 | High |

---

## Issues

### Home

#### P183-001 — Nav “Map” vs home “Codebase Map”
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Home / global nav |
| **Reproduction** | Open `index.html`. Compare top nav label **Map** with home card and map header **Codebase Map**. |
| **Suggested fix** | Pick one customer-facing name (recommend **Codebase Map** everywhere) and align nav, cards, scan success CTA, and guided tour. |
| **Time estimate** | 0.5 h |

#### P183-002 — Locked nav is visual only; pre-scan clicks still navigate
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Home → any locked tab |
| **Reproduction** | Fresh session (no scan). Click **Change Plan**, **Debug**, **What breaks?**, or **Map** despite `data-lock="1"` (opacity 0.4 only). User lands on workflow empty states without explaining why the tab looked disabled. |
| **Suggested fix** | Intercept locked nav clicks: toast “Scan a repository first” and optionally route to Home scan focus; remove lock attribute only after `unlockNav()` on successful scan. |
| **Time estimate** | 2 h |

#### P183-003 — Three overlapping onboarding flows
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Home (first launch) |
| **Reproduction** | Clear `localStorage` keys. Reload app. Observe `#welcomeScreen`, legacy `#onboarding`, and optional **Guided tour** link — three parallel entry paths with different copy and no single recommended path. |
| **Suggested fix** | Collapse to one first-run modal with explicit branches: Sample / Scan / Guided tour. Retire or never show legacy `#onboarding`. |
| **Time estimate** | 3 h |

#### P183-004 — Engineering comment in shipped HTML
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Home (page source) |
| **Reproduction** | View source of `index.html` lines 11–13: comment references “spiderweb” bug and Three.js fallback internals. |
| **Suggested fix** | Remove or shorten to a neutral “3D graph requires THREE global” note in dev docs only. |
| **Time estimate** | 0.25 h |

#### P183-005 — “Telemetry unavailable” banner uses engineering language
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Home (global banner) |
| **Reproduction** | Trigger `analytics_status === "degraded"` (or mock via API). Banner reads **Telemetry unavailable. Repository analysis unaffected.** |
| **Suggested fix** | Rephrase for users: e.g. “Usage stats temporarily unavailable — scanning and plans still work.” Hide banner entirely in default local-only installs if telemetry is optional. |
| **Time estimate** | 1 h |

#### P183-006 — Simple mode hides advanced nav and map tools without explanation
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Home / global |
| **Reproduction** | Default `body.mode-beginner`. Note missing **Repository Context** nav, map **Tour/Export Bundle/PNG** controls (`advanced-only` CSS). Toggle **Full detail** — items appear with no prior hint. |
| **Suggested fix** | Add one-line hint under mode toggle: “Full detail unlocks Repository Context and evidence panels.” Or show disabled nav with tooltip instead of `display:none`. |
| **Time estimate** | 2 h |

#### P183-007 — Duplicate primary action labels on Home funnel
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Home |
| **Reproduction** | After scan success, primary CTA is **Generate your first Change Plan**. Home card says **Change Plan**. Nav says **Change Plan**. User must infer they are the same action. |
| **Suggested fix** | Standardize post-scan CTA to match nav: **Create Change Plan** or **Open Change Plan**. |
| **Time estimate** | 0.5 h |

---

### Scan

#### P183-008 — Scan stage label “Building AI context packets”
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Scan (progress) |
| **Reproduction** | Run any scan. Watch final stage in `STAGES` array: **Building AI context packets**. |
| **Suggested fix** | User-facing stage: **Preparing export context** or **Finalizing analysis**. |
| **Time estimate** | 0.25 h |

#### P183-009 — “degraded/partial mode” shown during scan
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Scan (running / complete) |
| **Reproduction** | Scan a repo that sets `scan.degraded`. `#scanModeInfo` shows **Graph built in degraded/partial mode — some edges may be missing.** |
| **Suggested fix** | Plain language: “Some dependencies couldn’t be linked. Plans still work; results may cover fewer files.” Link to Support scan-scope tips. |
| **Time estimate** | 1 h |

#### P183-010 — Scan failure hints say “Build Plan” not “Change Plan”
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Scan (failed) |
| **Reproduction** | Force `partial_graph` or `symbols_missing` failure. Hint text references **Build Plan** and **Investigation** (`app.js` `showScanFailed` hints). |
| **Suggested fix** | Replace **Build Plan** → **Change Plan**, **Investigation** → **Debug** to match nav. |
| **Time estimate** | 0.5 h |

#### P183-011 — Raw reliability category in scan success notice
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Scan (success) |
| **Reproduction** | Scan repo with `scan.reliability.degraded` and empty `health_warnings`. `#scanReliabilityNotice` shows **Scan category: partial_graph** (or similar snake_case from API). |
| **Suggested fix** | Map `reliability.category` to friendly strings in `renderScanReliabilityNotice`; never show raw enum values. |
| **Time estimate** | 1.5 h |

#### P183-012 — “Large repo mode (sample top files)” is jargon
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Home → Scan options |
| **Reproduction** | Expand **Scan options**. Checkbox: **Large repo mode (sample top files)**. |
| **Suggested fix** | **Very large repository (faster scan, samples key files)** with short help text. |
| **Time estimate** | 0.5 h |

#### P183-013 — Success metrics use “Subsystems”
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Scan (success metrics) |
| **Reproduction** | Complete scan. Metrics grid includes **Subsystems** count. |
| **Suggested fix** | **Areas** or **Architecture groups** with tooltip. |
| **Time estimate** | 0.5 h |

---

### Change Plan

#### P183-014 — Five conflicting labels for the same primary action
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Change Plan |
| **Reproduction** | Trace strings: button **Create Change Plan** (`index.html`); banner **Generate Change Plan** (`#firstBuildBanner`); toast **Generate Change Plan** (`atlas_polish.js`); support/quickstart **Generate your first Change Plan**; guided tour **Build Plan** (`atlas_beta.js`). |
| **Suggested fix** | Single verb+noun everywhere: **Create Change Plan** (primary) / **Your first Change Plan** (banner only). Grep-replace Build Plan / Generate Change Plan in user strings. |
| **Time estimate** | 2 h |

#### P183-015 — First-build banner contradicts button label
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Change Plan |
| **Reproduction** | Scan sample, open Change Plan before first plan. Banner says click **Generate Change Plan**; adjacent button says **Create Change Plan**. |
| **Suggested fix** | Align banner text to exact button label or change button to match banner. |
| **Time estimate** | 0.25 h |

#### P183-016 — “Raw planning prompt” exposed in Full detail
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Change Plan (Full detail) |
| **Reproduction** | Run Change Plan in **Full detail**. Expand **Raw planning prompt** `<details>` — shows internal Claude prompt template. |
| **Suggested fix** | Rename **Advanced prompt preview** and move behind “For power users” collapsible; or remove from beta UI. |
| **Time estimate** | 0.5 h |

#### P183-017 — Engineering fields in plan output (subsystem, confidence raw)
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Change Plan (Full detail) |
| **Reproduction** | Generate plan. Note copy: “**subsystem**”, `confidence: high` badge, **Affected systems** vs API `likely_affected_subsystems`. |
| **Suggested fix** | User copy: **part of the codebase** instead of subsystem; map confidence to **Strong / Moderate / Limited** labels. |
| **Time estimate** | 1.5 h |

#### P183-018 — Stale history allows Copy for Claude despite export block
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Change Plan (history) |
| **Reproduction** | Rescan repo (invalidates history). Open **Recent results** → reopen stale item. Toast says refresh required; **Copy for Claude** still works (`copyForAi` checks `zfHasResult` only, ignores `export_blocked`). |
| **Suggested fix** | Gate `copyForAi` / `downloadAiMarkdown` on `!STATE.buildResult.export_blocked`; disable pinned CTA when stale. |
| **Time estimate** | 2 h |

#### P183-019 — Guided tour uses “Build Plan” and auto-runs API on Next
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Change Plan (guided tour) |
| **Reproduction** | Home → **Guided tour** → advance to step 4. Title **Your first Build Plan**; pressing Next triggers `runChangePlan()` without user reading the screen. |
| **Suggested fix** | Rename steps to **Change Plan**; change action to prefill example only and require explicit **Create Change Plan** click. |
| **Time estimate** | 2 h |

#### P183-020 — Empty state primary button says “Scan Repository” but routes Home
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Change Plan (pre-scan) |
| **Reproduction** | Open Change Plan before scan. Empty panel button **Scan Repository** calls `go('home')` — correct behavior but label implies scan starts immediately. |
| **Suggested fix** | **Go to Home to scan** or **Choose a folder**. |
| **Time estimate** | 0.25 h |

#### P183-021 — `n/a` in implementation order (Simple view export path)
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Change Plan (Simple / clipboard) |
| **Reproduction** | Plan with empty `implementation_order`. Simple hero shows list item **n/a** (`atlas_zero_friction.js`). |
| **Suggested fix** | Omit section or show **No specific order suggested**. |
| **Time estimate** | 0.5 h |

---

### Debug

#### P183-022 — Nav “Debug” vs About “Investigations” vs changelog “Investigation”
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Debug / About / marketing |
| **Reproduction** | Nav: **Debug**. About modal: **Investigations**. `changelog.html`: **Investigation**. `billing.js`: **Investigations**. |
| **Suggested fix** | Pick one public name. Recommend **Debug** in app nav and **Debug a problem** in marketing; retire “Investigation(s)” in user-facing strings. |
| **Time estimate** | 1.5 h |

#### P183-023 — Button “Find root cause” vs feature framing “hypotheses”
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Debug |
| **Reproduction** | Primary CTA **Find root cause**; results show **Hypotheses** and “ranked hypotheses” in About. Users may expect a single definitive answer. |
| **Suggested fix** | Button: **Analyze symptom**; add one-line expectation: “Atlas ranks likely causes — verify before fixing.” |
| **Time estimate** | 0.5 h |

---

### Impact (What breaks?)

#### P183-024 — Nav “What breaks?” vs changelog “Impact analysis”
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Impact / changelog |
| **Reproduction** | In-app nav and headings use **What breaks?**; changelog and perf panel use **Impact analysis** / **blast radius**. |
| **Suggested fix** | Keep conversational nav label; align secondary docs to **What breaks?** or add subtitle **(impact analysis)** once. |
| **Time estimate** | 1 h |

#### P183-025 — “target not in graph — heuristic” pill
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Impact (results) |
| **Reproduction** | Run impact on path not in graph (`r.mock === true`). Yellow pill: **target not in graph — heuristic**. |
| **Suggested fix** | **Estimate only — this file wasn’t in the last scan**. Prompt to pick from scanned file list. |
| **Time estimate** | 0.5 h |

#### P183-026 — “blast radius” in user-facing subtitle
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Impact |
| **Reproduction** | Screen intro: “files that may break if you change it **(blast radius)**.” Workflow gate and map copy repeat **blast radius**. |
| **Suggested fix** | Prefer **what depends on this file**; keep blast radius in Full detail only. |
| **Time estimate** | 0.5 h |

---

### Repository Context

#### P183-027 — Double gate: Simple mode + first-plan localStorage
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Repository Context |
| **Reproduction** | Scan repo but do not create Change Plan. Stay in **Simple** mode → nav hidden (`advanced-only`). Switch to **Full detail** → nav still hidden until `atlas_first_build_plan_done` (`applyExportNavVisibility`). |
| **Suggested fix** | Show nav after successful scan with tooltip; drop first-plan gate or replace with soft badge “Best after a Change Plan”. |
| **Time estimate** | 2 h |

#### P183-028 — Empty-state copy wrong after scan
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Repository Context |
| **Reproduction** | Scan only (no Change Plan). Manually open export view (Full detail + complete first plan, or direct URL). Preview when `!sum.ok` says **Create a Change Plan first** — misleading because scan alone should enable repo-wide export per API. |
| **Suggested fix** | If no scan: **Scan a repository first**. If scan ok: load preview immediately; remove plan-first requirement from copy. |
| **Time estimate** | 1 h |

#### P183-029 — “Export Demo Bundle” on user screen
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Repository Context / Map |
| **Reproduction** | Full detail → Repository Context → **Export Demo Bundle**. Map options → **Export Bundle**. Downloads `atlas_demo_bundle.zip` via `/api/demo/export-bundle`. |
| **Suggested fix** | Remove from production UI or hide behind `ATLAS_ADMIN=1` / dev flag. |
| **Time estimate** | 1 h |

#### P183-030 — Page title casing inconsistency
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Repository Context |
| **Reproduction** | `<h2>` **Repository context** (sentence case) vs nav **Repository Context** (title case). |
| **Suggested fix** | Match nav casing. |
| **Time estimate** | 0.1 h |

#### P183-031 — “Estimated tokens” / chars÷4 disclaimer buried
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Repository Context |
| **Reproduction** | Token estimate shown prominently; footnote **chars/4** easy to miss. Users may treat number as billing-related. |
| **Suggested fix** | Label **Approximate size**; tooltip explains estimation. |
| **Time estimate** | 0.5 h |

---

### Admin

#### P183-032 — Shipped HTML comment “Phase 182 — Beta Insights”
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Admin |
| **Reproduction** | View source `admin.html` line 52. |
| **Suggested fix** | Remove phase label (regression guard in tests if desired). |
| **Time estimate** | 0.1 h |

#### P183-033 — Fake waitlist base count documented on page
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Admin / marketing |
| **Reproduction** | `admin.html` footer exposes **WAITLIST_BASE = 127**; `demo.html` / `landing.html` waitlist modals show **127 developers already waiting**. |
| **Suggested fix** | Remove fake base from user-facing modals; use real count or no count. Keep constant internal-only. |
| **Time estimate** | 1 h |

#### P183-034 — Beta Insights section silently absent
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Admin |
| **Reproduction** | Open `admin.html` without `ATLAS_ADMIN=1`. Beta Insights section stays `hidden`; no message explaining why. |
| **Suggested fix** | Show collapsed card: “Beta Insights require admin mode on this device.” |
| **Time estimate** | 0.5 h |

#### P183-035 — Raw server analytics JSON
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Admin |
| **Reproduction** | **Server analytics** panel dumps `JSON.stringify` of `/api/analytics/summary`. |
| **Suggested fix** | Acceptable for local operator dashboard; optional formatted table for readability. |
| **Time estimate** | 2 h (optional) |

---

### Support

#### P183-036 — Contradictory Python install guidance
| Field | Value |
| --- | --- |
| **Severity** | Critical |
| **Screen** | Support |
| **Reproduction** | Open `support.html`. **Install notes** say **No Python required (installer)** for `Atlas_Setup.exe`. **Common fixes** → **App won’t start** says **Install Python 3.10+** as first bullet without distinguishing installer vs source. |
| **Suggested fix** | Split troubleshooting: **Installer** path (reinstall, run self-test, check shortcuts) vs **Source** path (Python 3.10+). Never tell installer users to install Python first. |
| **Time estimate** | 1 h |

#### P183-037 — Support lead references nonexistent button
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Support |
| **Reproduction** | Lead paragraph: **Generate your first Change Plan** — no such control on Support page; app uses **Create Change Plan**. |
| **Suggested fix** | **Create your first Change Plan** in the Atlas app. |
| **Time estimate** | 0.25 h |

#### P183-038 — Recent Issues hidden without feedback
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Support |
| **Reproduction** | Open Support as normal user. `/api/operations/crashes` returns `!ok` (no admin). `#recentIssuesSection` stays `display:none`; silent `catch` in inline script. |
| **Suggested fix** | Either show section with “No issues recorded on this device” for all users (public crash summary API), or remove section from Support and keep admin-only. |
| **Time estimate** | 2 h |

#### P183-039 — Scan health shows raw graph quality enum
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Support |
| **Reproduction** | After scan, Support → **Scan health** lists **Graph quality: partial** (or `degraded`, `unsupported`) verbatim from API. |
| **Suggested fix** | Map to friendly status + one-line explanation. |
| **Time estimate** | 1 h |

#### P183-040 — Reset onboarding misses keys
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Support → Recovery |
| **Reproduction** | Click **Reset onboarding**. Keys cleared: welcome, onboarding v2, guided tour, workflow examples. **Not** cleared: `atlas_first_build_plan_done`, `atlas_ready_state_shown_v155`, `atlas_output_mode_v157`. User reloads — no welcome, but first-build banner and Repository Context gate remain wrong. |
| **Suggested fix** | Include all onboarding-related keys in `supportResetOnboarding` or document as “partial reset”. |
| **Time estimate** | 0.5 h |

#### P183-041 — “Rebuild index” / localStorage jargon
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Support |
| **Reproduction** | Recovery card uses **Rebuild index**, **Clear cache** without plain-language outcomes. |
| **Suggested fix** | **Rescan saved repository**, **Clear temporary scan cache**. |
| **Time estimate** | 0.5 h |

---

### Feedback

#### P183-042 — “Send Feedback” vs actual control labels
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Feedback / app |
| **Reproduction** | `feedback.html` copy references **Send Feedback** button. In app: floating **Feedback** (hidden on main app via `data-fb-hide-button`) and Help menu **Report an issue**. |
| **Suggested fix** | Align copy to **Report an issue** and **Feedback**; one naming scheme. |
| **Time estimate** | 0.5 h |

#### P183-043 — Developer embed instructions on Feedback page
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Feedback (`feedback.html`) |
| **Reproduction** | Footer tells operators to add `<script src="feedback.js">` to pages — internal integration note, not beta user content. |
| **Suggested fix** | Remove from user-facing page; move to internal docs. |
| **Time estimate** | 0.25 h |

#### P183-044 — Feedback inbox exposes localStorage to operators
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Feedback |
| **Reproduction** | Hero text: stored in **localStorage** — accurate for operators, jargon for product page. |
| **Suggested fix** | **stored on this device only**. |
| **Time estimate** | 0.25 h |

#### P183-045 — Legacy `jarvis_feedback` key (internal)
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Feedback (code) |
| **Reproduction** | `feedback.js` migrates unicode-escaped legacy localStorage key. Not user-visible. |
| **Suggested fix** | No user action; optional cleanup after migration window. |
| **Time estimate** | 0.25 h |

---

### Updates

#### P183-046 — No in-app Updates screen; banner-only UX
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Updates (global) |
| **Reproduction** | Updates only via `#updateBanner` when `update_available` (`atlas_product.js`). No Help menu link to changelog or release notes when no update. Admin **Update status** panel admin-only. |
| **Suggested fix** | Add Help → **What’s new** linking to `changelog.html`; when update check configured, show “You’re up to date” in About. |
| **Time estimate** | 2 h |

#### P183-047 — Malformed update check fails silently
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Updates (banner) |
| **Reproduction** | Configure update URL returning malformed payload (`trust_level: malformed` per Phase 182). Banner stays hidden; no user feedback. |
| **Suggested fix** | Optional dev-only indicator; log to crash registry; never show malformed version strings. |
| **Time estimate** | 1.5 h |

#### P183-048 — Update banner dismiss only; no “install” path
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Updates (banner) |
| **Reproduction** | When update available, banner shows version + release notes link + **Dismiss**. Installer users have no guided update steps. |
| **Suggested fix** | Add **How to update** link (Windows installer steps) or download URL when configured. |
| **Time estimate** | 2 h |

---

### Demo

#### P183-049 — Demo video placeholder visible in production page
| Field | Value |
| --- | --- |
| **Severity** | Critical |
| **Screen** | Demo |
| **Reproduction** | Open `demo.html`. Video frame shows caption **Demo recording placeholder · add demo.mp4 to ship the real clip**. Play button toast: **coming soon — drop demo.mp4 into static/**. |
| **Suggested fix** | Ship `demo.mp4` or hide page from marketing nav until ready; replace placeholder with static storyboard images. |
| **Time estimate** | 4–8 h (content) + 0.5 h (wiring) |

#### P183-050 — Mock gallery shots labeled as demo content
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Demo |
| **Reproduction** | Section **What you'll see in the demo** uses CSS `mock` screenshots (`data-mock="graph"`), not product captures. |
| **Suggested fix** | Replace with real screenshots from presentation mode or annotated captures. |
| **Time estimate** | 2 h |

#### P183-051 — Fake waitlist social proof on demo page
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Demo |
| **Reproduction** | Waitlist modal: **127 developers already waiting**; success **#128 in line** (`WAITLIST_BASE`). |
| **Suggested fix** | Remove inflated counts or use real signup count from local/server store. |
| **Time estimate** | 1 h |

#### P183-052 — Chapter timestamps with no video
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Demo |
| **Reproduction** | Chapter cards show **0:00 — 0:12** etc. with no working video chapters. |
| **Suggested fix** | Hide chapters until video ships, or convert to static step list without timestamps. |
| **Time estimate** | 0.5 h |

---

### Cross-cutting (Codebase Map / API / trust)

#### P183-053 — Map health badge shows raw API enum
| Field | Value |
| --- | --- |
| **Severity** | High |
| **Screen** | Codebase Map |
| **Reproduction** | Scan repo with `graph_health.label` of `partial`, `degraded`, `unsupported`, or `watch`. Badge on map header displays raw string (`renderMapHeader`). |
| **Suggested fix** | Map labels: **Complete / Limited / Incomplete / Unsupported** with color coding. |
| **Time estimate** | 1.5 h |

#### P183-054 — System Health cockpit engineering metrics
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Codebase Map (left panel) |
| **Reproduction** | Open Map. **System Health** shows **Edges**, **Unresolved imports**, **Graph quality**, **Evidence index** timings, **Internal unresolved ÷ (resolved + unresolved internal)** ratio note. |
| **Suggested fix** | Simple mode: hide cockpit or show 3 plain metrics (Files scanned, Linked modules, Scan time). Reserve engineering metrics for Full detail. |
| **Time estimate** | 3 h |

#### P183-055 — Module list shows fan-in / fan-out / risk scores
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Codebase Map |
| **Reproduction** | Module browse list items: **risk 42 · in 8 · out 3 · subsystem_name** (`filterModuleBrowseList`). |
| **Suggested fix** | **42 dependents · 3 imports**; drop subsystem slug or humanize. |
| **Time estimate** | 1 h |

#### P183-056 — `console.error` on missing API routes
| Field | Value |
| --- | --- |
| **Severity** | Low |
| **Screen** | Any (devtools) |
| **Reproduction** | Call unknown endpoint via `api()`. Console: **Atlas API route missing:** + method/path. |
| **Suggested fix** | User toast once in dev builds only; strip console noise in production bundle if applicable. |
| **Time estimate** | 1 h |

#### P183-057 — Workflow errors may surface raw API `error` strings
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Change Plan / Debug / Impact |
| **Reproduction** | Trigger planning API failure. `workflowErrorHtml` displays `r.error` verbatim when no `demo_notice`. |
| **Suggested fix** | Map known error codes to friendly messages; generic fallback for unknown errors. |
| **Time estimate** | 2 h |

#### P183-058 — Trust status bar may show raw `status.message`
| Field | Value |
| --- | --- |
| **Severity** | Medium |
| **Screen** | Global trust bar |
| **Reproduction** | Stale repo triggers non-Fresh trust label. `atlasRenderTrustBar` injects API `status.message` without sanitization/mapping. |
| **Suggested fix** | Whitelist messages per `user_trust_label`; never show internal reason codes. |
| **Time estimate** | 1.5 h |

---

## Recommended Fix Order (no implementation in Phase 183)

| Priority | IDs | Theme | Est. hours |
| --- | --- | --- | ---: |
| 1 | P183-036, P183-049 | Critical trust/onboarding blockers | 5–9 |
| 2 | P183-014, P183-015, P183-022, P183-002 | Naming + broken paths | 6 |
| 3 | P183-009, P183-011, P183-025, P183-053, P183-054 | Engineering leakage in scan/map/impact | 8 |
| 4 | P183-027, P183-028, P183-040, P183-003 | Onboarding / discoverability | 7.5 |
| 5 | P183-033, P183-043, P183-032 | Internal/demo artifacts in shipped UI | 1.5 |
| 6 | Remaining Medium/Low | Copy polish sweep | 6–8 |

---

## Audit Method

- Static review of all listed screens and shared JS (`app.js`, `atlas_*.js`, `support.js`, `feedback.js`, `marketing.js`, `atlas_product.js`, `universe.js`).
- Cross-reference with Phase 179 ship verification and Phase 182 operations additions (admin insights, support crashes).
- No code changes made in Phase 183.

---

## Out of Scope (per charter)

- Backend intelligence, graph quality algorithms, persistence, billing logic.
- Implementing fixes (separate phases).
- Automated visual regression or live browser pass (recommended follow-up).
