# Phase 153 - External Beta Readiness Audit

Date: 2026-06-05

Scope: audit only. No Atlas code, intelligence, billing, installer, or UI files
were changed.

## Evidence Used

- `reports/atlas_evidence_package.md` and overnight reports from Phase 138.
- `reports/phase140_reliability.md`.
- `reports/phase146b_true_beta_blocker_fixes.md`.
- `reports/phase147_first_user_experience.md`.
- `reports/phase152_windows_installer.md`.
- `reports/phase152b_cross_repository_validation.md`.
- `reports/phase152b_validation_leaderboard.md`.
- `reports/phase152b_reliability_summary.md`.
- `reports/phase152b_failure_taxonomy.md`.
- `reports/phase152b_token_economics.md`.
- `reports/phase152b_marketing_claims.md`.

## Bottom Line

Atlas is close enough for a tiny, supervised external beta with carefully chosen
Windows developers and clear expectations. It is not ready for a broader
self-serve beta or public waitlist launch.

The strongest evidence is context compression and repository-scale graphing:
Phase 152B attempted 23 repositories, measured 22, and produced compact-context
evidence for 22. The weakest areas are first-run trust, broad language support,
clean-machine installer validation, unresolved import honesty, and whether users
understand that Atlas plans and exports context but does not edit code.

## Final Verdict

| Launch scope | Verdict | Reason |
|---|---|---|
| 5 external developers | **GO, supervised only** | Acceptable if they are Windows users, mostly Python/TypeScript, given an installer, asked to start with the sample repo, and have a direct support channel. |
| 20 external developers | **NO-GO** | Too much support risk: clean VM installer validation is still unproven, first-run UX is dense, graph-health labels are weak, and non-Python/TypeScript repos can produce empty graphs. |
| Public waitlist launch | **NO-GO** | Public positioning would overrun the evidence. Token savings are strong, but claims around universal repo understanding, defect finding, and daily developer workflow are not yet safe. |

## 20 Most Likely Reasons Users Stop

Probability is the estimated chance that at least one of 5 external beta users
hits the issue hard enough to reduce trust or stop using Atlas.

| Rank | Reason they stop using it | Probability | Severity | Evidence | Mitigation | Already solved? |
|---:|---|---:|---|---|---|---|
| 1 | Windows SmartScreen or antivirus makes the installer feel unsafe | 50% | Critical | Phase 152 lists unsigned PyInstaller binaries and SmartScreen as known limitations. | Sign the installer/exe, publish hash, add a plain-language install note, and pre-test with Defender. | **No** |
| 2 | Clean-machine install fails or behaves differently | 35% | Critical | Phase 152 built `Atlas_Setup.exe`, but explicitly says full "no Python on PATH" VM validation was not executed. | Run VM validation with no Python, standard user permissions, fresh profile, and blocked internet. | **Partial** |
| 3 | First real repo scan takes too long or looks frozen | 45% | High | Home Assistant scan was 494.804s; Atlas self timed out in overnight/Phase 152B. | Set expectations before scan, show ETA/degraded partial output, and start beta with smaller repos. | **Partial** |
| 4 | User expects Atlas to edit code, but it only plans and exports context | 40% | High | Phase 147 says planning-only messaging is correct but users may expect implementation. | Position as "repo intelligence for Codex/Cursor/Claude", not an autonomous coder. Make the next action "copy/use this plan". | **Partial** |
| 5 | Build Plan output feels like an internal debug report, not a clear success | 40% | High | Phase 147 says success is weak and expert-heavy; overnight build score was often 60. | Add a plain "what to do next" summary before technical details. | **No** |
| 6 | User does not know what to click first | 35% | High | Phase 147 found stacked modals, duplicate sample entry points, repo form noise, and many nav choices. | Single first-run path: Load sample -> Generate Build Plan -> Copy result. | **Partial** |
| 7 | Non-Python/TypeScript repository produces a weak or empty graph | 35% | High | Phase 152B: Java and Go examples scored 61, C# 72.25; `gin` and Spring example had graph/language gaps. | Restrict beta positioning to Python/TypeScript first; label other languages experimental. | **No** |
| 8 | Unresolved import explosion undermines trust in impact results | 35% | High | Phase 152B flags unresolved import explosion in VS Code, Pydantic, Airflow, LangChain, Kubernetes, Qdrant. Phase 140 flagged OpenBB/SQLModel/LangChain. | Show resolved/unresolved ratios prominently and gate strong claims when coverage is partial. | **Partial** |
| 9 | Graph health looks healthier than the evidence supports | 30% | High | Phase 152B leaderboard shows graph health as `None` while failures include unresolved import explosions and language gaps. | Require explicit health labels: healthy, partial, degraded, unsupported language. | **Partial** |
| 10 | Impact answer is technically plausible but not trusted | 30% | High | Impact scores are proxy metrics; evidence package states no human-reviewed correctness and no separate no-Atlas answer-quality run. | Add proof snippets, direct files, confidence caveats, and reviewer notes for every impact answer. | **Partial** |
| 11 | Investigation gives generic leads rather than confirmed root cause | 30% | Medium | Phase 147 and prior reports frame investigation as planning/evidence, not confirmed defect proof. Phase 152B uses structural proxy scoring. | Rename as "investigation leads"; require verification steps and confidence levels. | **Partial** |
| 12 | User scans a very large monorepo and hits timeout or memory pressure | 25% | High | Atlas self timed out; Home Assistant needed about 8 minutes; Phase 140 added taxonomy but not elimination. | Default to scoped scan for huge repos, warn before full scan, and preserve useful partial graph results. | **Partial** |
| 13 | Browser does not open, localhost port conflicts, or support fallback is missed | 25% | High | Phase 147 listed port 8777 and browser/local server failures as dead ends; Phase 152 says packaged fallback exists but clean VM not tested. | Validate alternate port flow, support page auto-open, and one-click diagnostics on clean Windows. | **Partial** |
| 14 | Corporate network blocks CDN graph assets | 25% | Medium | Phase 152 lists CDN scripts/Three.js from unpkg as unchanged. | Vendor graph assets locally before wider beta. | **No** |
| 15 | Native folder picker or Browse flow fails on a beta machine | 20% | Medium | Earlier beta blockers required native Browse verification; Phase 152 notes Tcl/Tk path issues remain a packaging risk. | Manual matrix: Windows 10/11, standard user, OneDrive folders, long paths, denied folders. | **Partial** |
| 16 | User is privacy-sensitive and cannot tell what leaves the machine | 20% | High | Phase 146B fixed local feedback copy, but first-run trust still depends on users understanding local-first behavior. | Add short local-first trust copy: no source upload, local scans, exports only when user copies them. | **Partial** |
| 17 | Results feel benchmark-optimized or too good to be true | 20% | Medium | Phase 152B token reductions round to 99-100%; marketing report now caveats estimates. | Use conservative claims only, show raw packet sizes, and avoid "understands every codebase". | **Partial** |
| 18 | User wants defect confirmation, but Atlas mostly gives leads/plans | 20% | High | Evidence package says strongest evidence is context compression and graph construction, not confirmed defect finding. | Position beta around repository understanding, impact, and planning; do not promise bug finding. | **No** |
| 19 | Support page/diagnostics feels like a developer tool | 20% | Medium | Phase 147 says Support, Diagnostics, tokens, and system health increase technical feel. | Keep support accessible but simplify beta-facing copy and direct users to one support channel. | **Partial** |
| 20 | Mac/Linux developers cannot use the packaged path | 15% | Medium | Phase 152 is Windows installer only. | Recruit only Windows beta users or provide explicit "Windows-only private beta" language. | **No** |

## What Is Already Solved

- The six Phase 146B true beta blockers are resolved for the sample/happy path:
  startup readiness, demo Impact target, rate-limiting Build Plan intent,
  duplicate-events investigation routing, Atlas export branding, and local-only
  feedback copy.
- Phase 152 packaging materially improves the largest Phase 147 blocker:
  self-contained `Atlas.exe`, no console subsystem, installer output, bundled
  Python runtime, support page bundled.
- Phase 140 reliability means bad scans are categorized instead of silently
  treated as healthy.
- Phase 152B gives credible breadth evidence across 23 requested repositories.

## What Is Not Solved Enough

- Clean external Windows VM validation is still the biggest launch gate.
- Signed installer / SmartScreen trust is not solved.
- Broad language support is not solved; Go/Java/C#/Rust results are mixed or weak.
- Graph health labels and coverage honesty need to be obvious in product output,
  not just in reports.
- The product still feels too technical for a self-serve first session.
- Atlas still does not prove confirmed defects; it should not be marketed as a
  bug confirmer.

## Recommended External Beta Shape

If sent tomorrow, use this exact constraint set:

1. Recruit 5 Windows developers only.
2. Prefer Python/TypeScript repositories under 500k LOC for the first session.
3. Start every user on the sample repository before their own repo.
4. Tell them Atlas is a local repository intelligence and planning tool, not an
   autonomous code editor.
5. Provide one support contact and ask for screenshots/support bundles.
6. Ask them to evaluate three workflows only: Build Plan, Impact, Export.
7. Treat other language scans as experimental.

## Go / No-Go Rationale

**5 users: GO, supervised only.** The product has enough evidence to learn from
real developers, especially around context compression and impact planning.
However, the beta must be curated and support-heavy.

**20 users: NO-GO.** The probability that multiple users hit installer trust,
first-run confusion, long scans, or graph coverage issues is too high.

**Public waitlist launch: NO-GO.** Public launch would invite expectations
around universal repository understanding, daily autonomous coding, and defect
finding that the current evidence does not support.
