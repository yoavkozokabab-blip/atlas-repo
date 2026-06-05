# Phase 156 — Private Beta Launch Readiness Plan

**Date:** 2026-06-05  
**Author:** Product Manager  
**Role:** Planning only. No code changes.  
**Evidence base:** Phase 113, 118, 132, 139, 140, 146B, 147, 152, 152B, 153, 154, 155  

---

## Executive Summary

Atlas is a Windows-only local repository intelligence tool. It compresses AI context
by ~99.89%, maps Python/TypeScript dependency graphs at production scale, and generates
Change Plans, Impact analyses, and AI-ready export packets. Phase 155 closed the worst
first-run UX gaps. The product is ready for a **5-user supervised beta** today.

It is **not** ready for a 20-user semi-self-serve beta or public waitlist:
the installer has not been validated on a clean machine under normal user permissions,
the binary is unsigned, and Investigation/Build Plan outputs still contain plausible-
looking but unreliable details for real repos.

**Summary verdict:**

| Scope | Status | Gate |
|---|---|---|
| 5 supervised Windows users | **GO** | Operator-assisted, sample-first, direct support channel |
| 20 semi-self-serve users | **NOT YET** | Needs: signed installer + clean-VM pass + investigation quality |
| Public waitlist / download | **NOT YET** | Needs: all of above + language breadth + Mac/Linux |

---

## Section 1 — Blocker Register

### Critical Blockers
*Definition: blocks the launch scope indicated; a single hit can permanently lose a beta user.*

| ID | Blocker | Affects | Evidence | Probability | Severity | Est. Fix |
|---|---|---|---|---|---|---|
| C1 | **Installer fails on locked-down Windows profiles** | 5-user, 20-user | Phase 154: exit code 4, registry permission error during silent install. Phase 152: clean-machine never tested. | **High (60%)** | Stops install completely | 1–2 days |
| C2 | **SmartScreen / unsigned binary** | 5-user, 20-user | Phase 152, 153: code signing not applied; SmartScreen will warn on first launch for any unsigned PyInstaller build. | **High (70%)** | Users abort install or click away | 0.5–1 day (process) |
| C3 | **Clean Windows VM install never validated** | 20-user | Phase 152: "treat as pre-beta QA gate"; Phase 154: hostile local test failed. | **High (35% unknown, could be total)** | Unknown failure modes on real machines | 0.5 day (QA task) |
| C4 | **Browser auto-open not visually confirmed** | 5-user | Phase 154: server confirmed reachable but no visual browser evidence on fresh profile. | **Medium (25%)** | User sees nothing; walks away | 0.5 day (QA task) |

### Major Blockers
*Definition: affects trust, understanding, or workflow quality enough to cause abandonment within the first session.*

| ID | Blocker | Affects | Evidence | Probability | Severity | Est. Fix |
|---|---|---|---|---|---|---|
| M1 | **Investigation produces nonsensical root-cause lines** | 5-user | Phase 154: `__future__.annotations` and `re` surfaced as top root causes for FastAPI. | **High (50%)** — hits on any mid-size real repo | Destroys trust in the core product | 1–2 days |
| M2 | **Build Plan scope pollution** | 5-user | Phase 154: FastAPI "add rate limiting" plan included `scripts/playwright/.../image02.py`. | **High (40%)** — present in FastAPI; likely in other multi-folder repos | User concludes output is wrong | 1–2 days |
| M3 | **Non-Python/TypeScript repos produce empty or weak graphs** | 5-user | Phase 152B: Go=66%, Java=61%, C#=72%. Language support gap confirmed for gin, spring, aspnet. | **High (35%)** if users try Go/Java/C#/Rust repos | Embarrassing empty result first session | 3–5 days or scope restriction |
| M4 | **Unresolved import explosion undermines impact trust** | 5-user | Phase 152B: 6/23 repos hit; vscode, pydantic, airflow, langchain, kubernetes, qdrant. Phase 140: OpenBB/SQLModel. | **High (35%)** on large real repos | User sees "99% unresolved" and loses confidence | 2–3 days or better labelling |
| M5 | **CDN dependencies (Three.js, Google Fonts, 3d-force-graph)** | 20-user | Phase 152, 154: unchanged; `index.html` fetches from unpkg and Google CDN. | **Medium (25%)** on corporate networks | Graph blank; fonts degraded; looks broken | 0.5–1 day |
| M6 | **Data directory falls back to temp storage** | 5-user | Phase 154: startup status showed `fallback=temp`; data lost on reboot. | **Medium (20%)** | User data, history, settings disappear | 0.5–1 day |
| M7 | **No clear support destination** | 5-user | Phase 154: support bundle generated but user not told where to send it. | **Medium (20%)** | Beta feedback loop broken | 0.5 day |
| M8 | **Large repo scan expectations not set** | 5-user | Phase 140: Home Assistant 494s. Phase 152B: Atlas self timeout. | **Medium (25%)** if users try monorepos | User thinks it hung; closes the app | 0.5–1 day |
| M9 | **Product version string is stale** | 5-user | Phase 154: build reports `phase146b-true-beta-blocker-fixes` in diagnostics. | **Low (15%)** on this user cohort | Looks unpolished; confuses support | 0.5 day |
| M10 | **Mac/Linux users excluded** | 20-user, public | Phase 152: Windows installer only. Phase 153: known. | **Certain** for non-Windows users | Entire cohort blocked | 1–3 weeks (packaging) |

### Minor Blockers
*Definition: causes friction or reduces perceived quality but is unlikely to stop a motivated user.*

| ID | Blocker | Affects | Evidence | Fix |
|---|---|---|---|---|
| m1 | Graph health labels inconsistent (health=None vs failure lists) | 5-user | Phase 154: `unresolved_internal` discrepancy in diagnostics | 0.5 day |
| m2 | Locked nav is visual-only (dim but clicks through) | 5-user | Phase 147: `data-lock="1"` dims but does not block | 0.5 day |
| m3 | Evidence quality dim 56.0 — weakest internal score | 20-user | Phase 132: explicitly noted as "real headroom" | 3–5 days |
| m4 | File-list precision in investigation is noisy (recall=0.97, precision=0.30) | 5-user | Phase 132: benchmark rewards recall; demo shows noise | 2–3 days |
| m5 | Support page may still have Python/BAT instructions despite Phase 155 update | 5-user | Phase 154: confirmed stale; Phase 155: addressed but not independently verified | 0.5 day |
| m6 | Root launch scripts still fall back to `py -3 run_atlas.py` | all | Phase 154: `Launch Atlas.bat` fallback in packaged context | 0.5 day |
| m7 | About.html opens marketing-style page out of app context | 5-user | Phase 147 | 0.5 day |
| m8 | Atlas self-scan times out (cannot demonstrate scanning itself) | 5-user | Phase 152B: timeout | 2–4 days |
| m9 | Toast instruction disappears in 2.4s | 5-user | Phase 147 | 0.5 day |
| m10 | Copilot quality depends on external LLM key | 5-user | Phase 139 | user expectation setting |

---

## Section 2 — Probability / Severity / ROI Matrix

### Scoring methodology
- **Probability**: chance at least 1 of 5 beta users hits it hard enough to damage trust or abandon  
- **Severity**: 1=cosmetic → 5=launch-blocking  
- **Fix time**: engineering days  
- **ROI score**: (Probability × Severity) / Fix Days — higher is better

| ID | Issue | Prob | Sev | Days | ROI Score | Priority |
|---|---|---:|---:|---:|---:|---|
| M7 | Add clear support destination (email/Discord) | 0.90 | 4 | 0.1 | **36.0** | Do now |
| m9 | Extend/pin toast instruction | 0.70 | 2 | 0.1 | **14.0** | Do now |
| M9 | Update product version string | 0.70 | 2 | 0.1 | **14.0** | Do now |
| C2 | Code-sign installer / SmartScreen trust | 0.70 | 5 | 0.5 | **7.0** | This week |
| C1 | Fix installer on locked-down Windows profiles | 0.60 | 5 | 1.5 | **2.0** | This week |
| C3 | Clean Windows VM install validation (QA task) | 0.90 | 5 | 0.5 | **9.0** | This week |
| C4 | Visually confirm browser auto-open (QA task) | 0.60 | 4 | 0.5 | **4.8** | This week |
| M5 | Vendor Three.js + fonts locally | 0.25 | 3 | 0.5 | **1.5** | Before 20-user |
| M6 | Fix data directory persistence (avoid temp fallback) | 0.20 | 3 | 0.5 | **1.2** | Before 20-user |
| M1 | Filter nonsensical investigation root-cause lines | 0.50 | 4 | 1.5 | **1.3** | Before 20-user |
| M2 | Filter Build Plan scope pollution (docs/scripts) | 0.40 | 4 | 1.5 | **1.1** | Before 20-user |
| M8 | Large-repo scan ETA / warning improvements | 0.25 | 3 | 1.0 | **0.75** | Before 20-user |
| M4 | Unresolved import honest labelling | 0.35 | 3 | 2.0 | **0.53** | Before 20-user |
| M3 | Non-Python/TS language support (Go/Java/C#) | 0.35 | 3 | 5.0 | **0.21** | Before public |

---

## Section 3 — Top 10 Highest ROI Fixes

> Ordered by ROI score. These are the 10 changes with the greatest trust/retention impact
> per engineering-day invested, based on cross-phase evidence.

| Rank | Fix | ROI Score | Effort | Impact |
|---:|---|---:|---|---|
| 1 | **Add a support destination** — add an email address or Discord invite to support.html and the "Send support bundle" flow; costs 15 minutes | 36.0 | 0.1 day | Every beta user knows where to get help; feedback loop works |
| 2 | **Pin the toast instruction** — extend "Describe your change, then click Generate Change Plan" from 2.4s to persistent until first interaction | 14.0 | 0.1 day | Stops first-session dead ends where user does not know what to type |
| 3 | **Update version string** — bump `PRODUCT_VERSION` to `beta-phase155` or a real semver | 14.0 | 0.1 day | Removes stale build label from diagnostics; tells support which build it is |
| 4 | **Clean Windows VM QA pass** — install Atlas_Setup.exe on a standard Windows 10/11 VM with no Python, standard user permissions, no dev tools; record every step | 9.0 | 0.5 day | Converts the biggest unknown into a known; potentially uncovers C1 |
| 5 | **Code-sign Atlas.exe and Atlas_Setup.exe** — obtain an OV cert or use Windows attestation signing; re-package | 7.0 | 0.5 day | Removes SmartScreen warning for 70% of first-time Windows installers |
| 6 | **Visually confirm browser auto-open** — run Atlas.exe on a clean profile; screenshot or screencast that a browser window opens | 4.8 | 0.5 day | Validates or disproves the riskiest unconfirmed assumption before inviting users |
| 7 | **Fix installer on restricted profiles** — investigate exit code 4 (registry `HKCU` shortcut/uninstall permissions); test with `PrivilegesRequired=lowest` adjusted for Start Menu path | 2.0 | 1.5 days | Unblocks the entire installer distribution channel |
| 8 | **Filter investigation root-cause noise** — demote or hide lines that are stdlib modules, type annotations, or `import *` results from the "top root cause" list | 1.3 | 1.5 days | Stops the single-worst trust killer in Phase 154 (FastAPI: `re`, `__future__` as root cause) |
| 9 | **Filter Build Plan scope** — add an explicit exclusion list for `docs/`, `scripts/`, fixture, example, and generated files from "likely affected files" unless directly imported | 1.1 | 1.5 days | Stops Playwright screenshot helper appearing in a "add rate limiting" plan |
| 10 | **Vendor Three.js and Google Fonts** — download `three@0.157.js` and `3d-force-graph.min.js` and serve from `_internal/`; replace Google Fonts with a bundled Inter/JetBrains Mono | 1.5 | 0.5 day | Removes CDN dependency; graph works on corporate/air-gapped machines |

---

## Section 4 — Beta Plans

### A. 5-User Supervised Beta Plan

**Goal:** Validate the core workflow (Install → Scan → Change Plan → Export to AI) with
real developers. Collect structured feedback. Do not let any user get stuck silently.

**Criteria for admission:**
- Windows 10 or Windows 11 (64-bit, standard user account)
- Uses Python or TypeScript as their primary language
- Has at least one repository between 500 and 100,000 LOC
- Direct contact channel (Discord DM, email, or Slack)
- Comfortable reporting issues without a ticket system

**Preparation checklist (before inviting user 1):**
- [ ] C3: Complete clean-VM install validation
- [ ] C4: Visually confirm browser auto-open
- [ ] M7: Support destination added (email / Discord channel)
- [ ] Rank 3: Version string updated
- [ ] Rank 2: Toast pinned
- [ ] Prepare a one-page "Getting started" note (not docs — one paragraph: install, run, load sample, generate plan, copy to Claude/Cursor/Codex)
- [ ] Designate a support owner (one person, available within 4 hours during beta)

**Onboarding sequence per user:**
1. Send Atlas_Setup.exe directly — no download page yet
2. Send the one-page "Getting started" note
3. Ask them to start with **Load Sample Repository** before their own code
4. Join them for first 20 minutes via screenshare or async video
5. After first session, send the 3-question survey (see Section H)

**Scope for users to test:**
- Load sample repository → Generate Change Plan → Copy to Claude/Cursor/Codex
- Scan their own Python/TypeScript repo (under 100k LOC)
- Export context packet for a real change they are planning
- Report any confusion or broken moment

**Scope explicitly excluded:**
- Go, Java, C#, Rust repos — tell users these are "experimental, may produce empty graphs"
- Repositories over 500k LOC without scoped scan
- Billing, account management, Copilot (LLM-keyed)

**Expected support volume (Phase 139 estimate):** ~1–2 touches per user in week 1.

**Exit criteria (move to 20-user):**
- 4/5 users complete sample repo → Change Plan → Export without human intervention
- Zero reports of installer crash or blank browser on first run
- At least 1 user successfully scans their own repo and trusts the output enough to share with their AI tool

---

### B. 20-User Semi-Self-Serve Beta Plan

**Goal:** Validate that Atlas can onboard developers without operator assistance.

**Blockers that must be resolved first (all from register above):**

| ID | Fix required |
|---|---|
| C1 | Installer works on locked-down Windows profiles |
| C2 | Installer is code-signed |
| C3 | Clean-VM validation completed |
| C4 | Browser auto-open verified |
| M1 | Investigation root-cause noise filtered |
| M2 | Build Plan scope pollution filtered |
| M5 | Three.js and fonts vendored locally |
| M6 | Data directory fallback to temp eliminated |
| M7 | Support destination published clearly |

**Estimated time to open 20-user beta (from today):** 7–12 engineering days + QA pass

**Admission criteria (20-user):**
- Windows 10/11, standard user profile
- Python or TypeScript primary repo
- Self-selects via waitlist, responds to basic screening question
- No operator-assisted onboarding — must succeed independently

**Distribution channel:**
- Waitlist form on jarvis_landing/ sends Atlas_Setup.exe download link to approved users
- No public URL; link shared 1-1 via email
- SmartScreen resolved before this cohort opens

**Monitoring requirements:**
- Usage events JSONL available for daily review
- Analytics page shows session count, scan count, plan count, export count
- Support bundle link circulated at signup; 48-hour response SLA

**Support staffing:** 1 person, responsive within 24 hours for this cohort.

---

### C. Public Waitlist Plan

**Goal:** Capture developer interest at scale. Not a product download yet — a signup only.

**What the public waitlist offers now:**
- jarvis_landing/index.html is live and functional (Phase 118)
- Atlas branding, honest partial-graph caveats, verified Phase 116G metrics
- Email capture with waitlist form
- No download link

**What must change before linking the waitlist to a download:**
- [ ] Mac/Linux packaging or an explicit "Windows only, other platforms coming" message
- [ ] Signed installer validated on three Windows profiles (standard, locked-down, Windows 10)
- [ ] Language support page: clearly state Python/TypeScript as supported, Go/Java/C#/Rust as experimental
- [ ] Privacy statement covering what Atlas logs locally (analytics.jsonl, usage_events.jsonl)
- [ ] "What Atlas does and does not do" page — planning only, not an autonomous coder

**Waitlist growth tactics (no spend needed yet):**
- Post to Hacker News "Show HN" on 20-user beta launch day
- One Reddit post to r/LocalLLaMA or r/ClaudeAI describing the context compression claim
- GitHub README with benchmark table (from Phase 152B leaderboard)

**Waitlist-to-download conversion gate:**
- Open download to waitlist only after 20-user beta passes exit criteria
- Batch invites in groups of 25, not all at once

---

### D. Exact Launch Sequence

```
Phase 156 Launch Sequence
══════════════════════════════════════════════════════════════════════

DAY 1 (Today — before user 1 is invited)
  ├── Do: Add support destination to support.html (30 min) [Rank 1]
  ├── Do: Pin toast instruction (30 min) [Rank 2]
  ├── Do: Update version string to beta-155 (30 min) [Rank 3]
  └── QA: Book a Windows 11 VM for clean-machine validation

DAY 2
  ├── QA: Run clean-VM install test — record every step; pass or document failure
  ├── QA: Confirm browser auto-open on clean profile
  └── Decision: If clean-VM passes → proceed to 5-user invite
             If clean-VM fails → fix C1 first (est. 1.5 days)

DAY 3 (if clean-VM passed)
  ├── Invite: Send Atlas_Setup.exe + one-page note to User 1
  └── Monitor: Check analytics.jsonl every 4 hours on day 1 of User 1

DAY 4–5
  ├── Invite: Users 2–3 staggered by 1 day
  └── Triage: Any blockers from User 1 → fix before User 3 onboards

DAY 6–7
  ├── Invite: Users 4–5
  ├── Collect: 3-question survey after each first successful plan
  └── Begin: Code signing process (OV cert or attestation)

DAY 8–9
  ├── Review: 5-user feedback; classify by blocker tier
  └── Begin: M1/M2 fixes (investigation noise, scope pollution) for 20-user

DAY 10–12
  ├── Code signing completed and installer re-packaged
  ├── Three.js and fonts vendored locally
  ├── Data directory persistence fixed
  └── QA: Second clean-VM pass on signed installer

DAY 13 (5-user exit criteria check)
  ├── If passed: open 20-user cohort
  └── If failed: extend 5-user to 10 users, fix remaining blockers

DAY 21 (target 20-user open)
  ├── Waitlist form live on jarvis_landing/
  └── First batch of 20 invites sent

WEEK 6 (target public download open)
  └── Gate: signed installer + clean-VM + language disclaimers + privacy statement
```

---

### E. Daily Monitoring Checklist

Run this check each morning during active beta cohort:

**Installation health (check once per 48h)**
- [ ] Download link is live and returns the current signed installer
- [ ] installer version in `build_info.json` matches the file sent to users
- [ ] SmartScreen status: any new reports from users in support channel?

**Usage signal (check daily)**
- [ ] `analytics.jsonl`: at least 1 `scan_completed` event per active user this week
- [ ] `usage_events.jsonl`: `export_created` events present (users reaching the value moment)
- [ ] `analytics.jsonl`: any `scan_failed` or `startup_failed` events? Triage immediately
- [ ] Session gap > 48h for any user who started? → proactive check-in

**Support queue**
- [ ] Support channel messages responded to within 4 hours (5-user), 24 hours (20-user)
- [ ] Any support bundle received? Download and check `startup_checks.json` for `ready=false`
- [ ] Common issues log: are 2+ users hitting the same thing? → escalate to fix

**Quality signal**
- [ ] Build Plan export events: are users reaching `export_created` after `build_plan_created`?
- [ ] Conversion rate: scans → plans → exports (target: >50% of scans lead to an export)
- [ ] Any user feedback about investigation root causes, scope, or trust?

**Infrastructure**
- [ ] `launcher.log` on support bundles: any ERROR lines?
- [ ] `startup_checks.json`: all `ready=true`?
- [ ] Data directory: `fallback=temp` reports? (indicates M6 not fixed)

---

### F. Failure Response Playbook

#### P0: Installer fails on clean Windows machine
- **Signal:** User reports "install didn't work" or sends an install error screenshot
- **Immediate:** Ask for a screenshot of the error and whether they are on a work machine
- **Response:** Send them `Atlas.exe` (the folder, zipped) directly as a workaround; do not ask them to "try again"
- **Fix track:** Check error code (if 0x80070005 = registry permission, adjust `PrivilegesRequired` in Inno Setup)
- **Gate:** Do not expand to the next user until cause confirmed and patched

#### P1: SmartScreen blocks install
- **Signal:** User says "Windows says it's unsafe" or sends SmartScreen screenshot
- **Immediate:** Send the exact "More info → Run anyway" steps in plain language; note that this is expected pre-signing
- **Response:** Accelerate code-signing timeline; add instruction to the one-page note
- **Gate:** Signed installer must ship before cohort exceeds 10 users

#### P2: Browser does not open
- **Signal:** User says "nothing happened" after installing
- **Immediate:** Ask if they can go to `http://127.0.0.1:8777` in a browser
- **Response:** If server is running → browser issue (tell them to open it manually); if server is not running → ask for `launcher.log` from support bundle
- **Fix track:** Check `atlas_desktop_entry.py` `webbrowser.open()` logic on clean profile

#### P3: Investigation or Build Plan output looks wrong
- **Signal:** User says "it recommended a test file for a backend change" or "the root cause makes no sense"
- **Immediate:** Acknowledge as a known quality issue; ask what repo and what symptom
- **Response:** Thank for the specific case; log to investigation quality backlog; offer to rescan with scoped folder to verify
- **Gate:** M1/M2 fixes must ship before user 6 onboards

#### P4: App crashes silently
- **Signal:** Browser shows connection refused; user says app stopped working
- **Immediate:** Ask user to download support bundle from support.html before closing Atlas; if they already closed it, point to `%LOCALAPPDATA%\Atlas\desktop_data\launcher.log`
- **Response:** Review log for traceback or OOM; if OOM → known large-repo issue; if unexpected → triage as P0

#### P5: User scans a monorepo and scan takes > 5 minutes
- **Signal:** User reports hang or no progress bar movement
- **Immediate:** Tell them Atlas is still working; ask repo size; if > 500k LOC, suggest narrowing scan scope to a subfolder
- **Gate:** Large-repo ETA warning must ship before cohort > 10 users

#### P6: User completes the workflow but finds no value
- **Signal:** Feedback: "The plan was too vague" or "I already knew all this"
- **Response:** Ask what they tried to plan and which repo; understand whether the gap is evidence quality, vocabulary, or wrong expectation
- **Insight:** This is the most important feedback signal; log verbatim and review against Phase 132 evidence quality dimension (56.0)

---

### G. Success Metrics

**5-User Beta — Week 1 Success Criteria**

| Metric | Target | Measure |
|---|---|---|
| Install success rate | ≥ 4/5 (80%) | Users confirm browser opened after install |
| First scan completed | ≥ 4/5 (80%) | `scan_completed` in analytics.jsonl |
| First Change Plan generated | ≥ 3/5 (60%) | `build_plan_created` or user confirmation |
| First export created | ≥ 3/5 (60%) | `export_created` in usage_events.jsonl |
| Support touches | ≤ 2 per user in week 1 | Support log count |
| Zero lost-user incidents | 0 users stuck with no response | Support queue response time |

**5-User Beta — End of Beta Success Criteria (opens 20-user gate)**

| Metric | Target |
|---|---|
| User-confirmed value: "I used this to plan a real change" | ≥ 3/5 |
| Net Promoter Score (would recommend to a colleague?) | ≥ 7/10 average |
| Zero P0 install blockers unresolved | All P0s fixed or worked around before user 3 |
| At least 1 real-repo export used in a real AI coding session | Confirmed by user |

**20-User Beta — Success Criteria (opens public waitlist download)**

| Metric | Target |
|---|---|
| Self-serve install success (no operator help) | ≥ 80% |
| Scan → Export completion without help | ≥ 60% |
| Support tickets per user per week | ≤ 1 |
| Users who scan their own repo (not just sample) | ≥ 60% |
| Trust score: "I trust the output enough to act on it" | ≥ 6/10 average |

**Lagging success indicators (month 2+)**

| Metric | Target | Why it matters |
|---|---|---|
| Weekly active users (at least 1 scan/week) | ≥ 50% of beta cohort | Validates daily-driver value |
| Waitlist conversion to install | ≥ 30% | Validates messaging |
| Organic referrals (user-invited a peer) | ≥ 1 in 5-user, ≥ 3 in 20-user | Growth signal |

---

### H. Launch Decision Matrix

Use this matrix before each expansion decision.

```
┌─────────────────────────────────────────────────────────────────────┐
│ EXPANSION GATE: Before inviting next cohort, confirm each row       │
├─────────────────┬──────────────┬─────────────────────────────────────┤
│ Gate            │ Required     │ How to verify                        │
├─────────────────┼──────────────┼─────────────────────────────────────┤
│ INSTALLER       │ PASS         │ Clean-VM test log shows 0 errors     │
│ SIGNING         │ PASS         │ Installer signed; SmartScreen absent │
│ BROWSER OPEN    │ PASS         │ Video/screenshot of auto-open        │
│ SUPPORT DEST    │ LIVE         │ Email/Discord link in support.html   │
│ VERSION STRING  │ CURRENT      │ `api/health` returns beta-155+       │
│ 5-USER EXIT     │ ≥3/5 value   │ Survey results                       │
│ P0 CLEAR        │ 0 unresolved │ Support log                          │
│ M1 FIX (20-user)│ SHIPPED      │ FastAPI investigation test passes    │
│ M2 FIX (20-user)│ SHIPPED      │ Build Plan scope filter in prod      │
│ CDN VENDORED    │ SHIPPED      │ index.html uses local Three.js path  │
│ DATA DIR FIXED  │ SHIPPED      │ fallback=temp absent in analytics    │
├─────────────────┴──────────────┴─────────────────────────────────────┤
│ ALL GREEN → advance to next cohort                                  │
│ ANY RED   → do not advance; fix and re-verify                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Additional public-launch gates (beyond 20-user):**

- [ ] Signed installer: yes
- [ ] Mac or explicit "Windows only" messaging: yes
- [ ] Language support page (Python/TS supported, others experimental): yes
- [ ] Privacy statement (what data stays local): yes
- [ ] "Atlas plans, not implements" clear before download: yes
- [ ] Support SLA published: yes

---

## Section 5 — Top 10 Highest ROI Fixes (Summary)

Ordered by estimated impact-per-day. These are the changes that will most improve
launch success probability and reduce beta support burden.

| Rank | Fix | Category | Days | Unblocks | Evidence |
|---:|---|---|---:|---|---|
| 1 | **Add support email/Discord to support.html** | Support | 0.1 | Feedback loop, user trust | Phase 154 finding M7 |
| 2 | **Pin the "Describe your change" instruction** until first interaction | UX | 0.1 | First-session guidance | Phase 147 m3 |
| 3 | **Update version string to beta-155** | Credibility | 0.1 | Support triage, user trust | Phase 154 finding 18 |
| 4 | **Clean-VM install validation** (QA task, not code) | Quality gate | 0.5 | 5-user launch safety | Phase 152/153/154 C3 |
| 5 | **Code-sign Atlas.exe + Atlas_Setup.exe** | Trust / install | 0.5–1 | SmartScreen warning, C2 | Phase 152/153 C2 |
| 6 | **Visually confirm browser auto-open** (QA task) | Quality gate | 0.5 | 5-user launch safety | Phase 154 C4 |
| 7 | **Vendor Three.js + Google Fonts locally** | Reliability | 0.5 | Corporate/offline machines | Phase 152/154 M5 |
| 8 | **Filter stdlib/annotation noise from investigation root causes** | Quality | 1.5 | Trust in core feature, M1 | Phase 154 finding 12 |
| 9 | **Exclude docs/scripts/examples from Build Plan affected-files** | Quality | 1.5 | Trust in core feature, M2 | Phase 154 finding 13 |
| 10 | **Fix data directory to avoid temp fallback** | Data reliability | 0.5 | User data persistence, M6 | Phase 154 finding 5 |

---

## Appendix — Evidence Quality Snapshot

| Dimension | Score | Source |
|---|---|---|
| Mean Atlas benchmark score | 86.3 | Phase 132 |
| Impact Analysis score | 94.0 | Phase 132 |
| Investigation (bug) score | 86.0 | Phase 132 |
| Feature addition score | 82.8 | Phase 132 |
| Evidence quality dimension | **56.0** (weakest) | Phase 132 |
| Scan success rate (18 repos) | 95.8% | Phase 140 |
| Graph build success rate | 75.0% | Phase 140 |
| Token compression (22 repos) | 99.89% avg | Phase 152B |
| Python avg overall score | 78.31 | Phase 152B |
| TypeScript avg overall score | 85.75 | Phase 152B |
| Go avg overall score | 66.0 | Phase 152B |
| Java avg overall score | 61.0 | Phase 152B |
| First-user success rate estimate | ~55–65% | Phase 147 |
| First-user success rate after Phase 155 | estimate ~70–75% | Phase 155 |
| Repos producing empty/weak graphs | 5/23 (22%) | Phase 152B |
| Unresolved import explosion repos | 6/23 (26%) | Phase 152B |

---

*Report generated 2026-06-05. No code was changed during this phase.*
