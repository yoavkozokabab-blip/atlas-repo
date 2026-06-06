# Phase 175D-A — Independent Product Audit

**Role:** Staff Engineer, first day on project  
**Date:** 2026-06-06  
**Method:** Read code, run the product, read reports — form own opinions  
**Previous conclusions:** Ignored  

---

## First observation before anything else

The project directory is `C:\J.A.R.V.I.S\local_jarvis`. The product is called Atlas. That path is in every error message, every log, every support bundle. The product isn't named Atlas from the inside. It's named JARVIS from the inside.

That is the first thing a developer would notice if they sent a bug report.

---

## 1. What would make a random developer uninstall within 10 minutes?

**The demo produces empty output on the most common first action.**

A developer opens Atlas. They click "Load Sample Repository." They type "add authentication" into Change Plan. They click Generate. They read:

```
## Files (top 5)
- (none)

## Implementation order
- alpha.py
- beta.py
- core/hub.py
- ring/x.py
```

This is the wrong demo repo. A 5-module toy with files named `alpha.py`, `beta.py`, `ring/x.py`, `ring/y.py` does not demonstrate Atlas's actual capability. The core premise of Atlas is "it names your files." The demo names *nothing* — it produces an empty file list and then falls through to showing the full import graph because there's no match. The confidence is "low-medium." The first impression is: this tool doesn't work.

**What actually gets pasted into Claude is confusing.**

The user clicks "Copy for Claude." They open Claude and paste. Claude receives:

```
You are Claude working in this repository. Implement the plan below carefully and safely.

ATLAS_REPOSITORY_MEMORY v1
repo: fastapi  session: 1
scan_id: 7213af3b
scan_signature: f05e1663754a
generated_at: 2026-06-06T11:50:04Z
freshness_status: fresh
replay_warning: This context is only valid for the scanned repository state...
modules: 73  edges: 159  files: 2753  graph_health: watch
hubs: fastapi._compat.v2 (17)...
delta: none  [first scan]

# Atlas Build (minimal)
Goal: add rate limiting
...
```

This is the most important moment in the product — the moment the user hands Atlas's output to Claude. It contains `scan_id`, `scan_signature`, `freshness_status`, `replay_warning`, `delta: none [first scan]`. These are internal trust-system fields. They mean nothing to Claude. They mean nothing to the user. They look like machine output, not developer tool output.

**The formatted plan output reads like a compiler warning, not a developer recommendation.**

The full Change Plan for FastAPI includes:

- `Detected concept: Rate Limiting — Rate Limiting` (the concept is repeated with an em dash — it's a rendering artifact from an internal join)
- `Knowledge quality: Source-backed`
- `Concept confidence: high · Repo mapping: high`
- `Insertion confidence 59/100 — fastapi/_compat/v2.py. Evidence score 118/100`
- `MUST inspect / LIKELY modify / VERIFY only / DO NOT touch unless needed`
- `Status: Implemented` (when the user asked to *add* rate limiting)
- `Evidence score: 118/100` (a score that exceeds its own scale)

A developer reading this the first time will stop at "Evidence score 118/100" and wonder if the tool is broken. They will stop at "Status: Implemented" and wonder if Atlas is telling them the feature already exists. They will not understand what "Insertion confidence" means. They will read "MUST inspect / LIKELY modify" and feel like they're reading a build system's static analysis output, not a developer assistant.

**The "Investigate" placeholder text is from a trading algorithm system:**

```
e.g. The backtest is better than paper trading
Dashboard PnL is wrong
Scan graph shows wrong module count
```

"Backtest," "paper trading," "PnL" — this is the legacy from when this product was named JARVIS and was a trading assistant. A developer trying to debug their web app reads this and thinks: "This is not for me."

**The port conflict crash still isn't fixed** (confirmed in Phase 175C). A developer opens Atlas, closes the tab, comes back later, double-clicks the shortcut. Atlas exits silently. The browser opens to nothing. They think it's broken. They uninstall.

---

## 2. What parts still look unfinished?

**The changelog is empty.** Not "sparse." Empty. The page says "Versioned public release notes will appear here as external beta builds are shared." This is a placeholder sentence from before the product shipped. It should not be visible to beta users.

**The small demo (the first thing every user loads) produces meaningless output.** Files named `alpha.py`, `beta.py`, `ring/x.py` in a 5-module toy repo. The demo should demonstrate the product's best capability: naming real, recognizable files in a realistic codebase. It currently does the opposite. The medium demo (17 modules with `api/handlers.py`, `services/billing.py`) is much better but users are defaulted to Small.

**"Detected concept: Rate Limiting — Rate Limiting"** is a rendering artifact. The concept name is joined with itself using an em dash separator from an internal template. It appears in every Change Plan that matches a known concept.

**The formatted plan output contains file sections with no content:**
```
MUST inspect:
- (none)

LIKELY modify:
- (none)

VERIFY only:
- (none)

DO NOT touch unless needed:
- (none flagged)
```

When the plan has no specific file matches, the template renders empty sections with explicit "(none)" placeholders. This looks broken. A user reads four consecutive sections that say nothing.

**The graph health label "watch" explains itself contradictorily.** FastAPI scans with `graph_health: watch` and the notice reads: "Internal graph is reliable: 0 unresolved internal import(s). The 241 external/stdlib import(s) are normal dependencies." The label says "watch" (sounds like a warning). The description says "internal graph is reliable." These are opposite messages. A developer scanning FastAPI — a well-structured Python library — sees a warning label and a reassuring explanation. They don't know which to believe.

**`__init__.py` still has `PRODUCT_VERSION = "phase107-mvp"`.** This is never user-visible, but it's the kind of thing a developer notices when they're exploring the codebase and it immediately signals that this project has a complicated internal history being papered over.

---

## 3. What parts still look like internal tooling instead of a real product?

**The Change Plan vocabulary is a software project's internal ontology, not a developer tool's language:**

- "Insertion confidence" — what is being inserted? Into what?
- "Knowledge-backed risks" — implies there are "non-knowledge-backed risks"?
- "Domain implementation steps" — sounds like a requirements document, not an action plan
- "Evidence score 118/100" — a weighted internal scoring metric
- "MUST inspect / LIKELY modify / VERIFY only / DO NOT touch unless needed" — a classification system built for internal use
- "AST definitions/references match: rate" — raw implementation detail
- "Knowledge quality: Source-backed" — an internal confidence classification

None of these terms are in any developer's vocabulary. They're the vocabulary of whoever designed the internal evidence engine.

**The "REPOSITORY EVIDENCE" section of the formatted plan reads like a test report:**

```
REPOSITORY EVIDENCE
===================
Status: Implemented
Evidence score: 75.0/100

Found:
- anyio.CapacityLimiter() in `fastapi/concurrency.py`
...

Missing:
- 429 Response
- Limiter
- Middleware
- Rate Limit
- Rate Limit Headers
- Redis
- Throttle
```

This is the internal evidence engine exposing its intermediate state to users. "Missing: Rate Limit" — the user knows Rate Limit is missing, that's why they asked Atlas to help them add it. This list is the diff between "what Atlas knows about rate limiting" and "what exists in the codebase." It's useful to a developer building Atlas. It's noise to a developer using Atlas.

**The clipboard content exposes the trust integrity system's internal data:**

`scan_id`, `scan_signature`, `freshness_status`, `replay_warning`, `delta: none [first scan]` — these are the outputs of the Phase 174 trust integrity architecture. They're necessary for Atlas's internal correctness. They should not be in what a developer pastes into Claude. Claude doesn't know what `freshness_status: fresh` means. The user doesn't know what `scan_signature: f05e1663754a` means. This is an engineering system that accidentally shipped into the user-facing product surface.

**The "Beginner/Advanced" toggle in the topbar.** This toggle changes output verbosity. But "Beginner" and "Advanced" describe the *user's skill level*, not the output detail level. A senior engineer will toggle "Advanced" because they are one. Then they'll see the "Evidence score 118/100" and "Insertion confidence" jargon and be more confused, not less. The toggle should be named something like "Summary / Full detail" or "Quick / Complete."

**The path input field placeholder:** `C:\projects\my-app  or  /home/dev/my-app` — this is a developer writing documentation for other developers, not a product designer writing UX copy.

---

## 4. What parts create distrust?

**"Evidence score 118/100" creates immediate distrust.** A score cannot exceed 100 by definition. When a user sees this in the first Change Plan they generate, they assume the software has a bug. The fact that it's a weighted internal score that can exceed 100 is irrelevant — the display is wrong.

**"Status: Implemented" when you asked to add something creates distrust.** A user types "add rate limiting." Atlas returns "Status: Implemented." The user's immediate reaction is: "That's wrong. I know it's not implemented. I'm asking you to help me add it." The next reaction is: "This tool gives wrong answers." The actual meaning — "Atlas found partial rate-limiting related code" — is not obvious from the label.

**Graph health "watch" on FastAPI (a well-maintained Python library with clean imports) creates distrust.** If Atlas assigns "watch" to FastAPI, what would it assign to a messy production codebase? The label sounds like a problem. If a developer scans their own well-structured project and sees "watch," they wonder what's wrong with their code.

**The "replay_warning" in every clipboard output creates distrust.** Every time a user copies a plan to Claude, the clipboard includes: "This context is only valid for the scanned repository state. If files changed, rescan or refresh before reuse." This is a legal disclaimer. It sounds defensive. It signals that Atlas is uncertain about the quality of its own output. A developer who sees this every time they copy starts wondering how often the context is actually stale.

**The "JARVIS shows exactly what a change touches..." text in studio.js** (confirmed in Phase 175C) creates distrust. A product that can't consistently apply its own brand name to its demo text is not a product that has attention to detail. It signals that the UI was assembled under time pressure and not fully reviewed.

**Confidence "low-medium" on the demo.** The demo should show Atlas at its best. It shows Atlas at "low-medium" confidence on simple requests like "add authentication" and "add rate limiting." This is because the demo repo is too small and generic. The user's takeaway: Atlas isn't confident about anything.

---

## 5. What would prevent recommending Atlas to a colleague?

**The value proposition is not demonstrable in the first 10 minutes without a pre-existing, well-structured Python or TypeScript codebase.** The demo repo is too small to produce impressive output. A colleague would need to scan their own real repo to see Atlas's capability. But scanning a real repo requires:
- Knowing the path
- Dealing with the scan time (2.6s for FastAPI, 18s for Django, 131s for VS Code)
- Understanding the graph health terminology
- Tolerating the verbose plan output

The recommendation path is: "Here, try it on YOUR repo." That's a 20-minute commitment, not a 5-minute demo.

**The output doesn't look better than what Claude can produce alone.** Phase 165 measured that Atlas improves Claude quality from 3.0 to 3.8 on a 5-point scale. But the improvement requires understanding what Atlas is doing, running a scan, generating a plan, and copying the right thing to Claude. A developer who just pastes the demo plan output into Claude and gets back a generic rate-limiting implementation will think: "Claude could have done this without Atlas." They're right about the demo. They're wrong about real repos. But the demo doesn't show them the real-repo case.

**The product is Windows-only with a binary installer.** A Mac developer (35-40% of the developer market) cannot use Atlas as a normal product. They must clone a repository with a JARVIS path prefix and run source mode. This alone prevents recommendation to most developer colleagues.

**No changelog.** When a colleague asks "what does this tool do?" and you say "it scans your repo and makes Claude better," they'll want to know: is it actively maintained? Is it getting better? The changelog page says nothing. A product in active development with a live changelog signals momentum. An empty one signals abandonment.

---

## 6. What features should be hidden from beta users?

**The "Repository Context (Advanced)" tab.** This is the old "Send to AI" tab renamed. It presents the raw, verbose context packet (compact or verbose). A beta user clicking this will be confused about why there's a separate "copy your whole repo context" function when there's already "Copy for Claude" on every workflow result. It should be completely hidden or removed from the nav. It creates a second export path that undermines the primary one.

**The Beginner/Advanced output toggle.** Showing beta users the "Advanced" mode output is counterproductive. The Advanced mode exposes all the internal scoring machinery (Insertion confidence, Evidence score, Knowledge quality) that creates distrust. Beta users should see only the simplified Beginner output. The toggle should be removed from the beta UI and the decision made for them.

**The 3D Codebase Map (for most users).** The Phase 173B analysis showed the Map is a rabbit hole — 15% of users who open it first never generate a plan. It's a visually impressive feature that doesn't help new users reach the value moment. It should be accessible but not promoted. Remove it from the nav and put it behind "Explore" or "Advanced" for beta users.

**The AI Copilot sidebar.** This is a freeform Q&A interface about the repository. It's a separate AI interaction paradigm from the structured workflow (Change Plan → Copy for Claude). A new user should not encounter three different ways to interact with their repository (Change Plan, Copilot, context export) in the first session. The Copilot should be hidden behind Advanced or a post-first-success screen.

**"Full detail" plan output in Beginner mode.** Even in Beginner mode, the plan shows the "Rollback plan", "Implementation order" (often same files as "MUST inspect"), and "Verify" sections. The beta user needs: Goal, Files, Copy button. Everything else should be collapsed by default.

**Verbose support bundle details.** The full beta diagnostics panel on the support page exposes technical fields like "scan_duration_seconds", "evidence_coverage", "workflow_performance". These are useful for debugging. They create information overload for a user who just wants to understand why their scan took 18 seconds.

---

## 7. Which pages are still too complex?

**The Home page / scan view.** The path from "Load Sample" to "scan started" currently involves:
- Welcome screen (good)
- Home page with: hero, 3-step flow, beta notice, cards by task ("Or explore by task"), a full folder path input with validate/scan buttons, advanced scan options accordion, demo pack size picker (Small/Medium/Large), and recent repositories list — ALL on one screen.

A developer arriving at the Home page after dismissing the Welcome screen faces six distinct UI areas before they've done anything. The intended path (Load Sample → auto-scan → plan) is buried under all of this.

**The Scan view** has seven stage labels during scan: "Indexing repository," "Building dependency graph," "Indexing repository" (repeated), "Detecting architectural risks," "Extracting architecture," "Extracting contracts," "Generating verification evidence," "Building AI context packets." These are implementation stages. A user watching them scroll by during a 18-second Django scan learns nothing useful and feels technical anxiety.

**The Change Plan output.** Even in its "Beginner" form, the plan output has: a textarea, a "Generate Change Plan" button, a "Download Markdown" toolbar button, then the result with: Trust bar, "You're ready" card (first time only), then the plan itself with header, scores, file sections, evidence, send-to-AI panel, and another Download Markdown button. The core action (copy to Claude) is buried in the middle of a results page.

**The Support page.** The support page has: Install notes, Common fixes, Environment checks, Version display, Scan health, Installer self-test, Recovery actions (Rebuild index, Clear cache, Reset onboarding, Copy diagnostics, Open support bundle), and action message. This is a debugging interface for developers building Atlas, not for users of Atlas.

---

## 8. Which outputs still look like engineering reports instead of developer tools?

**The full formatted Change Plan** is an engineering report. It has a title (`CHANGE PLAN`), a classification system (MUST/LIKELY/VERIFY/DO NOT), a "REPOSITORY EVIDENCE" section with a separate scoring subsystem, an implementation-step checklist sourced from a domain knowledge database, and a "Rollback plan" section with generic git advice. It reads like the output of a static analysis pipeline, not like advice from a senior engineer.

**The "REPOSITORY EVIDENCE" section** specifically is the most egregious example. The `Found` and `Missing` lists are useful for evaluating the quality of Atlas's evidence — for Atlas developers. For the end user, being told "Missing: Redis, Throttle, Rate Limit" when they asked to add rate limiting is condescending. They know Redis is missing. That's why they're asking for help.

**The session export packet (what gets prepended to Claude).** `scan_id`, `scan_signature`, `freshness_status`, `generated_at`, `replay_warning`, `delta: none [first scan]` — this is a trust-integrity system status report, not repository context for Claude. Claude doesn't read the `scan_signature`. The user doesn't know what it means. It is an engineering audit trail accidentally shipped as a user product feature.

**The Investigation output.** `Symptom: Reported: "why are requests slow?". Likely area: fastapi/applications.py.` The "Reported:" prefix is an internal label format from the planning engine. It implies the symptom was parsed and reformatted. The user said "why are requests slow?" and Atlas replies with "Symptom: Reported: 'why are requests slow?'"  — that's a 1-for-1 echo with an engineering prefix added.

**The Impact output labels.** "Direct importers (may break)" and "Transitive impact (top 5)" are graph theory vocabulary, not developer vocabulary. A developer wants to know "what breaks." That's the nav label. The output should use the same language.

**The graph health report on the scan success screen.** "Internal graph is reliable: 0 unresolved internal import(s). The 241 external/stdlib import(s) are normal dependencies." This is an explanation written for someone evaluating Atlas's graph quality, not for someone trying to use Atlas to plan a change. The scan success screen should say: "Atlas has a good picture of how your files connect. Ready to plan."

---

## 9. What is the biggest remaining product risk?

**The demo creates a false first impression that cannot easily be corrected.**

The small demo (5 toy modules) produces plans with empty file lists, low-medium confidence, and "Implementation order: alpha.py, beta.py" — file names that don't mean anything. This is what 90% of first-time users will see. They will conclude that Atlas is low-quality or broken. The plan output structure will look noisy and technical. They will close the browser.

The Phase 167 data shows Atlas produces real quality improvement on real repos: Claude quality goes from 3.0 to 3.8 (26% improvement), hallucination rate drops from 80% to 0% on FastAPI. That is a compelling result. But it is completely invisible in the first-time demo experience.

Atlas is a product where the demo loses the sale. The real repo wins it. Beta users are expected to scan their own repo and experience the real capability. But they must survive the demo first.

**The secondary risk: the clipboard noise.**

The `ATLAS_REPOSITORY_MEMORY v1` header pasted into Claude every time is:
1. Confusing to users who don't know what it means
2. Potentially confusing to Claude, which may focus on the technical metadata instead of the actual plan
3. Making the product look like it's in beta — because no finished product sends `scan_signature` and `replay_warning` as part of a copy-paste workflow

This is a correctness feature (trust integrity) that has become a UX liability. The trust metadata should be invisible to the user and invisible in the clipboard. It should exist as a server-side verification layer, not as copy-pasted text.

---

## 10. The 10 highest-ROI fixes before external beta

These are ordered by impact-per-hour, not absolute importance. I'm treating ROI as: (user-facing improvement) / (engineering hours required).

### ROI-01: Replace the small demo with the medium demo as default — 30 min

The medium demo has 17 modules with realistic names (`api/handlers.py`, `services/billing.py`, `services/auth.py`). When a user types "add rate limiting," it returns `api/handlers.py` as the target file with "medium-high" confidence. That is demonstrably better than the small demo's "(none)." Switch the default demo pack from `small` to `medium`. One line of code change.

### ROI-02: Remove `scan_id`, `scan_signature`, `replay_warning`, `freshness_status` from clipboard — 2h

The session export packet should contain only information that helps Claude understand the repository. Strip the trust integrity metadata from the user-facing text. Keep `repo`, `modules`, `edges`, `graph_health`, `hubs`, `risks`, `subsystems`. Remove `scan_id`, `scan_signature`, `generated_at`, `freshness_status`, `replay_warning`, `delta: none [first scan]`. These fields can still exist in the packet for internal verification without appearing in the clipboard text.

### ROI-03: Fix "Detected concept: Rate Limiting — Rate Limiting" duplicate — 1h

This is a rendering artifact where the concept name is joined with itself. One line in the formatting template. Every user sees this on every plan with a matched concept. It immediately signals "unfinished software."

### ROI-04: Fix "Evidence score 118/100" by either capping at 100 or renaming — 1h

Rename to "Match score" or "Evidence strength" and cap at 100. Or rename the entire field to "File match quality: High" with no numeric display. Either option removes the single most trust-breaking artifact in the Change Plan output.

### ROI-05: Fix "Status: Implemented" when user requested to add something — 2h

When the workflow is "build" (add a feature), rename "Status: Implemented" to "Evidence found:" or "Partial implementation exists:" or hide this section entirely in Beginner mode. The current label is factually confusing.

### ROI-06: Remove the empty template sections — 1h

When `files_to_inspect_first` is empty, don't render:
```
MUST inspect:
- (none)
LIKELY modify:
- (none)
```
Render nothing at all. An empty section with "(none)" is worse than no section. It makes the output look broken.

### ROI-07: Fix the Investigate placeholder text — 15 min

Change `"e.g. The backtest is better than paper trading\nDashboard PnL is wrong"` to software engineering examples. `"e.g. Requests hang after the third call\nUsers see 401 after login\nTests pass locally but fail in CI"`. This is a 15-minute content change that removes the most visible legacy artifact from the trading system.

### ROI-08: Fix port conflict recovery — 2h

Try ports 8777–8779 before failing. Show "Atlas is already running — check your browser" if all fail. The alternative (process exits silently, browser opens to nothing) is a confirmed conversion killer that Phase 175C reproduced.

### ROI-09: Hide trust metadata from Beginner mode; simplify plan to 3 sections — 4h

In Beginner mode, show:
1. Goal + confidence (one line)
2. Files to touch (bullet list)
3. Copy for Claude button

That's it. Everything else (implementation order, rollback plan, evidence section, domain steps, knowledge-backed risks) goes into Advanced. The "You're ready" card currently only shows on first plan — it should show every time as the primary CTA anchor.

### ROI-10: Fix the JARVIS text in studio.js and remaining console references — 1h

Replace "JARVIS shows exactly what a change touches..." with Atlas copy. Remove or update console log references that say `[JARVIS graph]`, `JARVIS_UNIVERSE`. These are shipped static assets that any developer would read if they opened the browser console.

---

## Verdict

### 5 supervised users

**CONDITIONAL GO.**

The trust integrity system is solid (9/10 attacks pass in 175C, 10/10 in 174F — the discrepancy is in redaction strictness). The core workflows function. The API is honest. The billing is honest.

But: port conflict causes confirmed silent crash on double-launch. The demo produces a poor first impression. The clipboard noise will confuse beta users and may confuse Claude. "JARVIS shows exactly what..." in studio.js will be noticed by any developer who opens the product studio.

Condition: fix ROI-01 (demo default), ROI-03 (concept duplicate), ROI-07 (investigate placeholder), ROI-08 (port conflict) before the first user installs. These four fixes take under 5 hours total. Without them, the product will lose half of the 5 users in the first session.

The supervised part of "supervised beta" covers the rest. An onboarding call can explain the vocabulary, the trust metadata, the graph health labels. That's what supervision is for.

### 20 supervised users

**NO-GO** in current state.

At 20 users, you need the demo to work. You need the clipboard to be clean. You need the trust metadata invisible. You need the evidence score not to say 118/100. You need the investigate placeholder to make sense. At 20 users, you can no longer personally explain every confusing element on the onboarding call. The product has to make enough sense on its own to generate the "aha" moment.

The current product requires a guide to reach the aha moment. That works for 5 supervised users. It doesn't work for 20.

Estimated additional work for 20-user GO: 2–3 focused days on ROI-01 through ROI-09.

### Public beta (self-serve)

**NO-GO.**

Public beta requires:
- Demo that impresses without explanation
- Clipboard content that makes sense to Claude without explanation
- Plan output that reads as a developer recommendation, not an engineering report
- Installation that works on Mac (35-40% of developer market)
- Port conflict recovery
- Changelog with real entries
- Update notification that works

This is 1–2 weeks of focused UI work, not days. The intelligence engine is production-quality. The product surface is not.

---

## What the previous reports missed

Previous reports were written by people close to the project. They evaluated whether features existed and whether attacks were blocked. They did not evaluate whether the product *felt* like a product.

**The demo is broken for first impressions.** None of the previous reports audited the actual demo output quality — they verified the mechanics (demo loads, scan completes, plan generates). They did not ask: "Is the output impressive?" It isn't.

**The clipboard noise is a UX regression.** Phase 174's trust integrity system is architecturally correct and the 10/10 attack results are real. But the side effect — `scan_id`, `scan_signature`, `replay_warning` appearing in every clipboard copy — was not audited as a UX issue. It was treated as a completeness feature.

**The evidence sections are internal product language, not user product language.** The "Insertion confidence," "Evidence score," "MUST inspect / LIKELY modify" vocabulary was designed to solve an internal problem (making the planning engine's confidence visible). It was never redesigned for end users. Previous reports noted this as "needs polish." It's a blocker for the 20-user tier.

**The medium demo should be the default.** This is the highest-ROI single change available. It has never been recommended in previous reports.
