# Phase 144 — Private Beta Execution Plan

Operational plan for the first **10–20 external beta users** of **Atlas** (local-first
repository intelligence). Pairs with `reports/phase142_beta_breakage_audit.md` (the
predicted failure modes this plan is built to absorb). Documentation only — no code,
features, branding, or billing changes.

**Product reality this plan assumes:** Windows-first desktop app, Python 3.10+,
stdlib-only runtime (`py -3 run_jarvis_desktop.py`), local-only analysis (no cloud
upload), planning/analysis — *not* code generation. Strongest on Python and
TypeScript repos.

---

## 1. Ideal first beta users (ranked by fit × risk)

Fit = how much value Atlas delivers to them. Risk = likelihood they hit friction or
churn before reaching value.

| Rank | Persona | Fit | Risk | Why / notes |
|---:|---|---|---|---|
| 1 | **Open-source maintainers** (Python/TS) | High | Low | Large, real, public repos; already think in architecture/impact; tolerant of rough edges; give precise feedback. **Best first cohort.** |
| 2 | **Startup engineers** (small teams) | High | Low-Med | Onboard onto unfamiliar code constantly; value "what breaks if I change X"; already pair with AI tools. |
| 3 | **Staff / senior engineers** | High | Medium | Ideal evaluators of correctness, but the harshest critics — only invite once scan reliability is proven; their negative word-of-mouth carries weight. |
| 4 | **Solo developers / indie hackers** | Medium | Low | Friendly, forgiving, vocal; repos may be small (less impact signal) but great for install/UX feedback. |
| 5 | **Technical students** | Medium | Medium | Enthusiastic and available, but more install-environment problems (no `py` launcher, old Python) and weaker architecture vocabulary → more support load and noisier signal. |

**Recommended week-1 mix (12 users):** 5 OSS maintainers, 4 startup engineers, 2 solo
devs, 1 student. Hold staff engineers for week 2 once metrics look good.

---

## 2. Beta onboarding flow

Target path and the checkpoint at each step (where to watch for drop-off):

| Step | What the user does | Success checkpoint | Watch for |
|---|---|---|---|
| 1. Download | Get the installer / clone + `py -3` | File obtained | SmartScreen/AV block; no Mac/Linux installer |
| 2. Launch | Run app; browser opens to `localhost:8777` | App UI loads | Python <3.10; `py` missing; port in use |
| 3. Load **sample repo** | Open a bundled demo pack (no path needed) | Demo graph renders | — (this is the safe "instant value" path; lead with it) |
| 4. Scan **own repo** | Paste repo path, scan | Summary + graph appear | Scanning `node_modules`/`.git`/vendored; long scan; 0-module/0-edge |
| 5. **Build Plan** | Ask "add rate limiting" etc. | Plan with affected modules + steps | Empty plan on edge-sparse repos |
| 6. **Investigation** | Describe a symptom | Grounded files + hypothesis | "no module matched" on sparse repos |
| 7. **Impact** | "what breaks if I remove X" | Direct/indirect importers + blast radius | concept not resolved → fallback |
| 8. **Export / feedback** | Copy context packet; submit feedback | Packet copied; feedback sent | "now what do I do with this?" |

**Design rule:** *demo-first* (step 3 before step 4) so every user sees value within
60 seconds even if their own scan is slow.

---

## 3. Beta success metrics

Measured from the local analytics/usage events already emitted (scan_started/completed,
build/investigate/impact/export events). Aggregate via the admin usage view.

| Metric | Definition | Target (private beta) |
|---|---|---|
| Install success rate | users who reach a loaded app / users who tried | **≥ 80%** |
| First scan success rate | users with ≥1 non-degraded scan / installed users | **≥ 70%** |
| Time to first value (TTFV) | install → first rendered graph (demo or own) | **< 5 min** |
| First Build Plan completion | users who ran ≥1 build plan with modules | **≥ 50%** |
| First Impact completion | users who ran ≥1 resolved impact query | **≥ 50%** |
| Feedback rate | users who submitted ≥1 structured feedback | **≥ 60%** |
| Crash / support rate | support tickets per active user | **< 1.0** |

---

## 4. Feedback collection (what to ask, when)

Short, milestone-triggered prompts (1–3 questions each; never a wall of forms).

- **After first scan:** "Did the architecture summary match your mental model? (Yes /
  Mostly / No)" · "Was anything missing or wrong?" · "How long did the scan feel?"
- **After first Build Plan:** "Were the affected modules the right ones? (1–5)" · "What
  would you have added/removed from the plan?"
- **After first Investigation:** "Did the suggested files include the real culprit?
  (Yes / Partly / No)" · "Was the hypothesis useful or generic?"
- **After first Impact:** "Did 'what breaks' look correct and complete? (1–5)" · "Any
  obvious importer it missed?"
- **After first 24 hours:** "Would you be disappointed if Atlas disappeared? (Very /
  Somewhat / Not)" (the PMF question) · "What did you use it for?" · "One thing to fix
  first?" · "Would you recommend it to a teammate? (NPS 0–10)"

---

## 5. Support workflow (runbook)

First response < 4 business hours. Always request: OS, Python version
(`py -3 --version`), repo size/language, and `~/.jarvis_desktop/launcher.log`.

| Problem | First triage | Resolution path |
|---|---|---|
| **Install problems** | Confirm Python 3.10+ and launcher (`py` vs `python3`); check they did NOT `pip install -r requirements.txt` | Point to the stdlib run command; for Windows AV, "More info → Run anyway" + checksum; for Mac/Linux, the manual `python3` path |
| **Scan failures** | Read the scan's `reliability.category` + `health_warnings`; check the diagnostics endpoint | If `zero_module_scan`: confirm it retried; if persistent, check path/permissions; reproduce with the diagnostics scan |
| **Huge-repo slowdown** | Ask file count; check if vendored dirs were included | Advise the scope picker / ignore `node_modules`/`.git`/`.venv`; set expectations (≈10 min at HA scale); offer cancel + rescan scoped |
| **Confusing outputs** | Identify the term (packet/blast radius/fan-in) | Send the plain-language explainer; capture as a UX issue (recurring → onboarding copy) |
| **Wrong file recommendations** | Get the repo type + the query | Likely edge-sparse / unsupported language or concept fallback; explain the limitation honestly, log the example for the lexicon/graph backlog (do **not** over-promise a fix) |

Escalation: anything touching data/privacy → **critical, stop-the-line** (see exit
criteria).

---

## 6. Beta risk register

| Risk | Likelihood | Impact | Mitigation (non-feature) | Owner |
|---|---|---|---|---|
| Installer friction (unsigned / AV) | High | High | Signed build or clear "Run anyway" + checksums; manual run docs | Operator |
| Python dependency confusion (heavy `requirements.txt`) | High | Critical | Document stdlib-only run; do not point users at the monorepo requirements | Operator |
| Huge-repo scans (slow / degenerate) | Medium-High | High | Scope guidance + default-ignore docs; set time expectations; Phase 140 warnings | Operator |
| Partial-graph / degraded warnings misread | Medium | Medium | Explain warnings in onboarding; pre-write canned responses | Support |
| Expectation mismatch ("plans but doesn't write code") | Very High | Medium | Lead onboarding + invite copy with the framing; repeat in-app | Operator |
| Windows-only installer perception | High (non-Win) | High | State supported platforms up front; provide the cross-platform manual path | Operator |
| Mixed/unsupported languages (Go/Rust/Java) | Medium | Medium | Document supported languages; honest "partial coverage" messaging | Support |

---

## 7. Beta invite strategy (where to find the first users)

Low-volume, high-trust outreach. Quality over quantity — 12 engaged users beat 100
tire-kickers.

- **GitHub OSS maintainers:** identify active Python/TS repos (1k–20k files); personal
  outreach offering to map *their* repo; ask for 30 min + feedback. *Highest yield.*
- **Reddit:** r/programming, r/Python, r/typescript, r/devtools — *do not spam*; post a
  genuine "I built a local repo-intelligence tool, looking for 10 beta testers" with a
  demo GIF and the honest "it plans, it doesn't write code" framing.
- **X/Twitter dev community:** short demo clip (scan → impact → export to Claude);
  reply to "understanding large codebases / onboarding" threads.
- **LinkedIn engineers:** target staff/senior engineers at small startups; DM with the
  value prop + a screenshot.
- **Friends-of-friends:** warmest channel; ask 5 trusted devs to each refer 1 person who
  onboards onto unfamiliar code often.

**Outreach template (one line):** "Local-first tool that maps any repo's architecture,
dependencies and change-impact, then exports grounded context for your AI assistant —
your code never leaves your machine. Want to try it on your repo and tell me where it's
wrong?"

---

## 8. Beta exit criteria (private → public beta)

Promote only when **all** hold over a ≥2-week window with ≥12 active users:

- [ ] **Install success ≥ 80%**
- [ ] **≥ 70% of installed users complete a first scan**
- [ ] **≥ 50% run at least one Build Plan, Investigation, or Impact**
- [ ] Support tickets are **manageable** (< 1 per active user; no recurring unresolved blocker)
- [ ] **No critical data/privacy issues** (confirmed local-only; no unexpected egress)
- [ ] Median **TTFV < 5 min** and no Critical-severity bug open

If install success or first-scan rate misses, **fix packaging/docs and re-run the same
cohort** before widening — do not add users on top of a broken funnel.

---

## 9. One-page beta operator checklist (before inviting anyone)

**Packaging & docs**
- [ ] A clear, single "How to run" doc: Windows (installer) **and** macOS/Linux (`python3 run_jarvis_desktop.py`).
- [ ] Prominent "**Python 3.10+ required**" and the stdlib-only note ("do not `pip install -r requirements.txt`").
- [ ] Installer signed *or* a documented SmartScreen/AV "Run anyway" + checksums.
- [ ] Default scan ignores documented (`node_modules`, `.git`, `.venv`, vendored dirs) + how to use the scope picker.

**Product readiness**
- [ ] Demo pack loads instantly on a clean machine.
- [ ] A 5k-, 50k-, and (optional) 200k-file repo each scanned end-to-end recently; durations recorded for expectation-setting.
- [ ] Reliability warnings (`health_warnings`) render visibly in the UI, not just in payloads.
- [ ] Onboarding states up front: "**Atlas maps your code and feeds your AI — it does not write code.**"
- [ ] Export screen tells users exactly what to do with the packet (paste into Claude/Codex/Cursor).

**Operations**
- [ ] Feedback channel live (form or shared doc) with the milestone questions from §4.
- [ ] Support inbox + first-response SLA (< 4 h) and the §5 runbook printed.
- [ ] Metrics dashboard (admin usage view) reachable; baseline at zero.
- [ ] Canned responses written for the top-7 Phase 142 tickets.
- [ ] A named operator owns the cohort for the full 2 weeks.

**Go/No-go:** invite only when every box above is checked. Start with **5 users**, watch
for 48 h, then add the rest.
