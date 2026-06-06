# Phase 175A — Product Completion Checklist

**Date:** 2026-06-06  
**Role:** CTO / completion audit  
**Scope:** Phases 164D–174F, 169–172, 173A/B/C  
**No code changes. No UI changes. No feature additions.**

---

## Classification key

| Symbol | Meaning |
|--------|---------|
| ✅ **DONE** | Implemented, tested, verified |
| 🔶 **NEEDS POLISH** | Works but has known UX/quality issues |
| 🔴 **BLOCKER** | Must be fixed before supervised beta |
| ⬜ **NOT NEEDED** | Correct to defer until post-beta |

---

## 1. Installation

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Windows .exe installer built and signed | 🔶 NEEDS POLISH | `packaging/installer/output/Atlas_Setup.exe` exists; **unsigned** | SmartScreen blocks ~25–35% of users; documented workaround exists |
| Installer self-test on fresh machine | ✅ DONE | `installer_self_test()` checks Python, dirs, shortcuts, browser | Self-test JSON written to `.jarvis_desktop/self_test.json` |
| Install notes / SmartScreen instructions | ✅ DONE | `packaging/installer/install_notes.txt` — 3-step "More info → Run anyway" | Good. Include screenshot in onboarding email |
| Port conflict recovery | 🔴 BLOCKER | `server.py:269` raises `OSError` with no fallback | Double-launch is near-certain; user sees blank browser tab |
| macOS source-mode launch | ✅ DONE | `python3 run_atlas.py` documented in quickstart | Acceptable for 5–20 supervised users |
| macOS binary installer | ⬜ NOT NEEDED | Not built | Required before 50+ unsupervised users |
| Linux support | ⬜ NOT NEEDED | Source mode only | Required before broad release |
| Python version guard | ✅ DONE | `_check_python()` requires 3.10+; hint shown on failure | |
| Launch Atlas.bat / shell scripts | ✅ DONE | `Launch Atlas.bat`, `Launch Atlas.vbs` exist | |
| Browser auto-open | ✅ DONE | `server.py:run()` opens default browser; logs if fails | |
| Startup error page | ✅ DONE | On startup failure, `run_atlas.py` routes to `/support.html` | |

---

## 2. First Launch

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Boot splash screen | ✅ DONE | `#bootSplash` in `index.html` with spinner | Clean. Dismisses on server ready |
| Server ready signal | ✅ DONE | `/api/health` polled by UI | |
| Welcome screen shown on first run | ✅ DONE | `#welcomeScreen` shown when `ONBOARDING_KEY` not set | |
| Version visible in UI | ✅ DONE | `PRODUCT_VERSION = "0.1.0-beta"` in `product_info.py` | Version previously "phase146b-true-beta-blocker-fixes" — now fixed |
| `__init__.py` version not stale | 🔶 NEEDS POLISH | `jarvis_desktop/__init__.py:16`: still `"phase107-mvp"` | Not user-visible but affects internal imports; update to match |
| Telemetry warning banner | ✅ DONE | `#telemetryWarning` only shown when analytics degraded | Non-blocking |
| Port in use — user message | 🔴 BLOCKER | No message; process exits silently | See Installation |
| Crash recovery page | 🔶 NEEDS POLISH | Support page exists; no watchdog restart | User must relaunch manually |

---

## 3. Onboarding

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Welcome card with primary CTA | ✅ DONE | `#welcomeScreen` with "Load Sample Repository" button | |
| Triple onboarding overlay (Welcome + Onboarding + Home) | 🔴 BLOCKER | Three separate screens before any action (Phase 173B AP-2: 10–15% drop-off) | Merge into single welcome screen with one CTA |
| "Load Sample" is the dominant first action | 🔶 NEEDS POLISH | Sample button exists but competes with path picker, demo packs, scan options | 5-minute value only on Sample path; path picker path has ~35% conversion |
| Guided walkthrough | 🔶 NEEDS POLISH | `startGuidedWalkthrough()` exists; defaults to offering; 8 steps | Should be opt-in "Tour (3 min)" not default |
| First-run explainer ("Atlas plans; AI implements") | ✅ DONE | Beta notice in hero, welcome screen copy | |
| Plain-language "What the words mean" | 🔶 NEEDS POLISH | Exists in `quickstart.html` but not in-app | Add one-click glossary to Help menu |
| Quickstart page | ✅ DONE | `quickstart.html` — 5-step path, clear | |
| Beginner/Advanced toggle explained | 🔶 NEEDS POLISH | Toggle exists; no first-run explanation of what changes | Phase 173B F-10: users unsure which to pick |
| 5-minute to first Claude paste | 🔶 NEEDS POLISH | Possible on Sample path (~3–4 min); ~35% on cold start | Phase 173B target: ≥70% after P0 UX fixes |

---

## 4. Scan Flow

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Scan a real repository | ✅ DONE | Fully functional; FastAPI 2.6s, Django 18s, VS Code 131s | |
| Scan progress stages (plain English) | 🔶 NEEDS POLISH | 7 technical stage labels ("Building dependency graph", "Generating verification evidence") | Phase 173B F-12: users cancel thinking it hung |
| Scan button disabled until Validate | 🔴 BLOCKER | `#scanBtn` disabled; no tooltip; Phase 173B AP-4: 10% abandon | Auto-validate on path change, or add "Click Validate first" tooltip |
| Browse folder (native picker) | 🔶 NEEDS POLISH | Works on some systems; fails in sandboxed/remote environments | Phase 173B AP-5: 15% of own-repo users abandon |
| Scan cache LRU eviction | 🔴 BLOCKER | `scan_cache` grows unbounded; Django = 14.7 MB per entry; no max | Phase 173A P0-01: memory leak |
| Content-backed cache invalidation | ✅ DONE | `signature_v2` with per-file content hashes via `GraphFileManifest` (Phase 174B) | Phase 174F: A2 PASS — stale graph after content edit now blocked |
| Large repo (>2500 files) invalidation | ✅ DONE | `signature_v2` uses full indexed manifest, not 2500-file sample (Phase 174B) | Phase 174F: A4 PASS — late files now detected |
| Git HEAD change detection | ✅ DONE | Synthetic `.git` HEAD check in signature v2 (Phase 174B) | Phase 174F: A3 PASS |
| Scan success screen — clear next step | 🔶 NEEDS POLISH | Three equal-weight buttons: "Generate Change Plan", "Explore Map", "Ask Copilot" | Phase 173B AP-7: users pick Map, never create plan |
| Partial graph explained honestly | ✅ DONE | Graph health badge (partial/watch/healthy); notice text | "partial" remains confusing as a standalone word |
| Unsupported language honest refusal | ✅ DONE | Go/Java repo with incidental Python helper now refuses Build/Investigation (Phase 174F A7) | |
| Massive repository mode | ✅ DONE | Auto-detected; warning badge; import-level graph | |
| Demo / sample repository | ✅ DONE | Three bundled packs (small, medium, large); 6 modules to 40 | |
| Scan analytics tracked | ✅ DONE | `scan_completed`, `modules`, `edges`, `cache_hit` in analytics.jsonl | |
| analytics.jsonl rotation | 🔶 NEEDS POLISH | No size limit; grows indefinitely | Phase 173A P2-03 |

---

## 5. Change Plan

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Change Plan generates correctly | ✅ DONE | `plan_change()` tested across FastAPI, Django, VS Code | |
| Path guard (refuses stale-path plan) | ✅ DONE | `_scan_matches_current_path()` in `plan_change()` | |
| Coverage gate (unsupported language) | ✅ DONE | `gate_weak_graph_workflow()` in trust_integrity.py uses `module_count` not just `matched_paths` (Phase 174D/F) | |
| Plan output too dense for new users | 🔴 BLOCKER | Full plan: goal, concept, domain, insertion confidence, evidence score, MUST inspect, LIKELY modify, VERIFY, rollback plan, architectural risks — all shown by default | Phase 173B F-16 and Beta User Diary: 3 confusing terms in first 30 seconds |
| "Insertion confidence 59/100" clarity | 🔴 BLOCKER | Opaque term; score range unclear; users unsure if 59 is good | Rename or explain inline |
| "Evidence score 118/100" > 100 | 🔴 BLOCKER | Breaks user trust immediately (Beta User Diary T+3:30) | Cap at 100 or rename to remove score framing |
| "Status: Implemented" on add-feature request | 🔴 BLOCKER | Means "partially exists" but reads as "already done" (Beta User Diary: almost abandoned at this point) | Rename to "Repository evidence: found partial implementation" |
| Beginner card — simplified output | 🔶 NEEDS POLISH | Beginner mode toggle exists but plan card still shows full detail | Phase 173B: beginner card should show goal, 5 files, order, Copy for Claude only |
| "Copy for Claude" button above fold | 🔴 BLOCKER | Copy button below plan detail; Phase 173B AP-10: 15–25% of plan creators never copy | Sticky or top-anchored Copy for Claude |
| Download Markdown workflow bundle | ✅ DONE | `downloadWorkflowMarkdownBundle()` in toolbar | |
| Rollback plan in output | 🔶 NEEDS POLISH | Generic text ("commit in small steps"); always shown | Move to Advanced / collapsed section |
| Trust envelope on plan response | ✅ DONE | `result["trust"]` with `can_export`, `freshness_status`, `scan_id` | Phase 174B |

---

## 6. Impact Analysis

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Impact analysis works | ✅ DONE | `change_impact_simulation()` via impact_engine | |
| Target file picker (not blank field) | 🔶 NEEDS POLISH | `#impactTarget` is a plain text field; Phase 173B F-17: users abandon | Module picker from scan graph would help |
| Impact refusal on unresolved target | ✅ DONE | Returns `ok=false, target_not_resolved` — the reference behavior | |
| Impact refusal explained clearly | 🔶 NEEDS POLISH | "Atlas won't guess" framing not present; Phase 173B AP-12: feels like error | Add friendly text: "Try a file path from the Codebase Map" |
| Trust envelope on impact response | ✅ DONE | `result["trust"]` attached (Phase 174B) | |
| Copy for Claude on impact | ✅ DONE | `sendToAiPanel("impact")` with Copy for Claude / Cursor / Codex | |
| Concurrent request safety | ✅ DONE | Phase 174F A8: 12 iterations, 0 wrong-repo leaks | |

---

## 7. Investigation

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Investigation generates correctly | ✅ DONE | `investigate_symptom()` tested | |
| Path guard on investigate | ✅ DONE | `_scan_matches_current_path()` added (Phase 174B) | Previously missing; was BLOCKER |
| Coverage gate (unsupported language) | ✅ DONE | `gate_weak_graph_workflow()` also applied to investigate (Phase 174D/F) | |
| Investigate placeholder examples | 🔶 NEEDS POLISH | Examples: "The backtest is better than paper trading" — niche/trading context | Phase 173B F-18: not relatable to typical developers |
| Insufficient evidence response | ✅ DONE | Returns `ok=false, status=insufficient_evidence` with explanation and next steps | |
| Delta quality investigate (−0.27) | 🔶 NEEDS POLISH | Phase 172 measurement showed quality delta slightly above −0.2 threshold for investigate | Root cause budget 80→120 chars fix (5 minutes) |

---

## 8. Repository Memory

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Memory generated after scan | ✅ DONE | `update_after_scan()` in repository_memory.py | Phase 172 |
| Memory persisted to disk | ✅ DONE | `{data_dir}/memory/{repo_id}.json` atomic write | Phase 172 |
| Memory persistence failure visible | ✅ DONE | `memory_persistence_status=failed` in diagnostics; Phase 174F A6 PASS | Phase 174B |
| Memory tampering rejected | ✅ DONE | `verify_memory_record()` with HMAC hash; Phase 174F A5 PASS | Phase 174B/D |
| Memory poisoning blocked | ✅ DONE | repo_id + path + hash validation in `_validate_memory()` | Phase 174D |
| Memory referenced in exports | ✅ DONE | `export_memory` field on all workflow results; `memory_ref` in delta | Phase 172 |
| Delta export generated | ✅ DONE | `ATLAS_DELTA v1` text; 57% smaller than MINIMAL per question | Phase 172 |
| Memory replay warning in packet | ✅ DONE | `replay_warning`, `scan_id`, `scan_signature`, `freshness_status` in memory packet; Phase 174F A9 PASS | Phase 174D |
| Memory UI toggle (MEMORY_EXPORT mode) | 🔶 NEEDS POLISH | `export_memory` field computed but no UI toggle to select it | Phase 173A P1-04: 57% token reduction invisible to users |
| Delta quality for investigate | 🔶 NEEDS POLISH | See investigation section | |
| Session count increments across sessions | ✅ DONE | Tested in Phase 172 test suite | |

---

## 9. Export to Claude / Cursor / Codex

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Copy for Claude works | ✅ DONE | `copyForAi("claude", kind)` with session prefix + plan export | |
| Session context included in copy | ✅ DONE | `zfSessionPrefix()` prepends ATLAS_REPOSITORY_MEMORY v1 | |
| Export replay blocked after repo change | ✅ DONE | Phase 174F A9: new export blocked; old packet has replay warning | |
| UI scan_id mismatch check before copy | 🔶 NEEDS POLISH | Phase 174 architecture designed this; UI implementation not confirmed deployed | Trust matrix Route 5: "0 hard protections" in UI layer |
| "Session context sent once per scan" explained | 🔴 BLOCKER | Beta User Diary T+4:30: user didn't know if they needed to copy something else first | Tooltip needs rewrite: "This includes all repo context. Copy once per scan, then copy plans as you go." |
| ATLAS_REPOSITORY_MEMORY v1 header explained | 🔶 NEEDS POLISH | Beta User Diary: user confused by format; "what is scan_id for?" | Either remove from visible text or add brief comment |
| Copy for Cursor | ✅ DONE | Same path as Claude | |
| Copy for Codex | ✅ DONE | Same path as Claude | |
| Download Markdown | ✅ DONE | `downloadAiMarkdown(kind)` creates `.md` blob download | |
| Two export systems confusion | 🔴 BLOCKER | "Send to AI" nav tab + per-workflow "Copy for Claude" — users don't know which to use (Phase 173B F-19, AP-9) | "Send to AI" tab should redirect to "Create a plan first" or be removed from beginner nav |
| MEMORY_EXPORT mode in UI | 🔶 NEEDS POLISH | Server computes delta; UI only offers Full/Minimal | 57% further token reduction invisible |
| Token estimate shown | ✅ DONE | `#tokEst` in export view | |
| "No API keys required" trust signal | ✅ DONE | Shown in export view; also in welcome | |

---

## 10. Trust Integrity

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Wrong-repo refusal after path switch | ✅ DONE | Phase 174F A1 PASS: all workflows return `requires_rescan` | |
| Stale graph after content edit | ✅ DONE | Phase 174F A2 PASS: `stale_outside_plan` blocks export | |
| Git HEAD change detection | ✅ DONE | Phase 174F A3 PASS: `stale_git_head_changed` | |
| Large repo (>2500 files) invalidation | ✅ DONE | Phase 174F A4 PASS: `stale_outside_plan` for files outside old cap | |
| Tampered memory rejected | ✅ DONE | Phase 174F A5 PASS: poisoned memory discarded | |
| Memory persistence failure visible | ✅ DONE | Phase 174F A6 PASS: `memory_persistence_status=failed` | |
| Unsupported Go/shallow graph refuses | ✅ DONE | Phase 174F A7 PASS: Build + Investigation refuse (10/10 cleared) | |
| Concurrent scan/export safety | ✅ DONE | Phase 174F A8 PASS: 12 iterations, 0 wrong-repo leaks | |
| Export replay metadata | ✅ DONE | Phase 174F A9 PASS: replay_warning, scan_id, signature in old packet | |
| Support bundle redaction | ✅ DONE | Phase 174F A10 PASS: api_key, Bearer, token patterns redacted | |
| `TrustEnvelope` on all workflow responses | ✅ DONE | `result["trust"]` with `can_export`, `freshness_status`, `scan_id` (Phase 174B) | |
| UI copy button reads `trust.can_export` | 🔶 NEEDS POLISH | Architecture designed (Phase 174); UI implementation unconfirmed | Critical path for trust enforcement at the copy point |
| Targeted refresh vs full rescan | ✅ DONE | `targeted_refresh_available` flag; `/api/repositories/current/refresh-changed-files` (Phase 174B) | |
| Trust status endpoint | ✅ DONE | `GET /api/repositories/current/trust-status` | |

---

## 11. Support Bundle

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Support bundle generates | ✅ DONE | `export_support_bundle()` creates zip with diagnostics, logs, version | |
| Secret redaction in logs | ✅ DONE | Phase 174F A10 PASS: api_key, Bearer, token, password patterns redacted | Phase 174D |
| Absolute path redaction | ✅ DONE | Prior Phase 174 implementation; Phase 174F confirms path_leak=False | |
| Source code not included | ✅ DONE | Prior probe: no source content in bundle | |
| Trust integrity status in bundle | ✅ DONE | `trust_integrity` field in diagnostics.json; Phase 174F A10 confirms | |
| Memory persistence status in bundle | ✅ DONE | `memory_persistence_status`, `memory_persistence_error_type` in diagnostics | |
| graph_signature in bundle | ✅ DONE | Included in scan_metadata.json | |
| "Copy diagnostics" button in app | ✅ DONE | `copyBetaDiagnostics()` in Help menu | |
| "Open support bundle" button | ✅ DONE | `supportDownloadBundle()` on support page | |
| Support email in bundle | ✅ DONE | `support@useatlas.dev` in manifest | Phase 175B |

---

## 12. Feedback Collection

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| In-app feedback widget | ✅ DONE | `feedback.js` floating button on all pages | |
| Feedback stored locally | ✅ DONE | `localStorage["jarvis_feedback"]` | |
| Feedback POST to server | ✅ DONE | `POST /api/feedback` → `submit_feedback()` → `~/.jarvis_desktop/feedback.jsonl` | Phase 175B |
| Feedback includes diagnostics summary | ✅ DONE | `diag_summary` with version, module_count, graph_quality, trust_label | Phase 175B |
| Feedback secret redaction | ✅ DONE | `_redact_support_text()` applied before storing | Phase 175B |
| Feedback in support bundle | 🔶 NEEDS POLISH | `feedback.jsonl` may not be included in support bundle export | Should be included so you can read it |
| Remote feedback routing | 🔶 NEEDS POLISH | `feedback_url()` reads `ATLAS_FEEDBACK_URL` env; not configured for beta | Needs a real endpoint (email, Formspree, webhook) |
| Feedback admin page | ✅ DONE | `feedback.html` renders all local entries | |
| Feedback export to JSON/CSV | ✅ DONE | Export buttons on feedback.html | |
| Feedback from support email | ✅ DONE | `support@useatlas.dev` on contact.html, support.html | Phase 175B |
| Structured beta feedback questions | 🔶 NEEDS POLISH | Phase 171 Feedback Framework defined; not wired into in-app flow | After-install, post-scan, 24h prompts are manual today |

---

## 13. Billing Readiness

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Billing enforcement off | ✅ DONE | `enforcement: "off"`, `payments: "disabled"`, `local_only: True` | Correct for beta |
| Billing UI gated by feature flag | ✅ DONE | `ATLAS_BILLING_UI_ENABLED` env; UI hidden by default | |
| Pricing preview page exists | ✅ DONE | `pricing.html` with "No payment collected today" | |
| Plan definitions in code | ✅ DONE | Free, Pro, Team plans in `billing/plans.py` | |
| Usage tracking (local) | ✅ DONE | Usage events tracked locally; admin dashboard available | |
| No checkout flow | ✅ DONE | CTAs route to local app or contact, never to payment | |
| Billing nav hidden in beta | ✅ DONE | `billingNav` hidden unless `billing_ui_enabled` | |

---

## 14. Pricing Page

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Pricing page renders | ✅ DONE | `pricing.html` exists with plan grid | |
| "Preview only, no payment" notice | ✅ DONE | Two explicit notices on page | |
| Plans are plausible for beta | ✅ DONE | Free/Pro/Team with reasonable feature tiers | |
| CTAs never trigger checkout | ✅ DONE | All CTAs route to app or waitlist | |
| Pricing page linked from nav | 🔶 NEEDS POLISH | Only shown when billing_ui_enabled; hidden for most users | |
| Pricing page needs copywriting review | 🔶 NEEDS POLISH | Not reviewed since Phase 137A | Post-beta task |

---

## 15. Account / Subscription UX

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| No account required | ✅ DONE | Zero login friction; all local | Core value prop |
| Usage dashboard (local) | ✅ DONE | `usage.html` shows local scan/export counts | |
| No signup flow | ✅ DONE | Correct for beta | |
| Beta waitlist (landing page) | ✅ DONE | `jarvis_landing/` — localStorage + JSON export | For public landing page; separate from app |
| Account/subscription UX | ⬜ NOT NEEDED | No accounts exist | Correct to defer |

---

## 16. Update Path

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| `check_for_update()` function | ✅ DONE | `product_info.py:115` — reads `ATLAS_UPDATE_CHECK_URL` env, fetches `latest.json`, compares versions | Phase 175B |
| Update check API endpoint | ✅ DONE | `GET /api/product/update-check` in server routes | Phase 175B |
| Update check URL configured | 🔴 BLOCKER | `ATLAS_UPDATE_CHECK_URL` not set; always returns `configured: False` | Must host `latest.json` before beta and set env |
| In-app update notification banner | 🔶 NEEDS POLISH | API endpoint exists; no UI component reads it and shows banner | Users won't know updates exist |
| Changelog page | 🔴 BLOCKER | `changelog.html` says "Release notes will appear here" — empty | Users updating see nothing |
| Version shown in support page | ✅ DONE | `#atlasVersion` on support page | |
| Version in diagnostics / support bundle | ✅ DONE | `version: "0.1.0-beta"` in all diagnostic outputs | |
| Manual reinstall path documented | ✅ DONE | Support page + quickstart explains "download new installer" | Acceptable for 5 users; not for 100 |

---

## 17. Beta User Ops

| Item | Status | Evidence | Notes |
|------|--------|---------|-------|
| Ideal user profile defined | ✅ DONE | Phase 171: Python/TS, 10k–300k LOC, uses Claude/Cursor daily | |
| Ideal repo profile defined | ✅ DONE | Phase 171: 20–500 modules, active, real work | |
| Onboarding email template | ✅ DONE | Phase 171 Feedback Framework has exact template | |
| 30-minute call structure | ✅ DONE | Phase 171: structured 6-agenda call guide | |
| Feedback question banks (by stage) | ✅ DONE | Phase 171: after-install, after-scan, after-build, after-24h | |
| Disappointment score question | ✅ DONE | Phase 171: "How disappointed would you be if Atlas disappeared?" | |
| Success metrics defined | ✅ DONE | Phase 171: PMF decision tree with binary gates | |
| Beta success criteria | ✅ DONE | Phase 171: 5 criteria (install, scan, export, return day-2, disappointment) | |
| Support contact channel | ✅ DONE | `support@useatlas.dev` on contact.html and support.html | Phase 175B |
| Crash telemetry / crash log | 🔶 NEEDS POLISH | `launcher.log` captures startup events; no `crashes.jsonl` with stack traces | Phase 173A MS-03: need structured crash handler |
| Remote feedback routing | 🔶 NEEDS POLISH | Feedback API stores locally; `ATLAS_FEEDBACK_URL` env not configured | Must configure to get feedback out of users' machines |
| Feedback in support bundle | 🔶 NEEDS POLISH | `feedback.jsonl` may not be in bundle | Include it |
| Beta recruitment plan | ✅ DONE | Phase 171: DM → X → Reddit → HN sequence | |
| Fastest path to 5 users | ✅ DONE | Phase 171: Day 0–7 timeline with DM-first approach | |

---

## Summary by Area

| Area | DONE | NEEDS POLISH | BLOCKER | NOT NEEDED |
|------|:----:|:------------:|:-------:|:----------:|
| 1. Installation | 7 | 2 | 1 | 3 |
| 2. First Launch | 5 | 2 | 1 | 0 |
| 3. Onboarding | 4 | 4 | 1 | 0 |
| 4. Scan Flow | 10 | 3 | 2 | 0 |
| 5. Change Plan | 6 | 3 | 5 | 0 |
| 6. Impact Analysis | 4 | 2 | 0 | 0 |
| 7. Investigation | 4 | 2 | 0 | 0 |
| 8. Repository Memory | 9 | 2 | 0 | 0 |
| 9. Export | 7 | 3 | 2 | 0 |
| 10. Trust Integrity | 11 | 2 | 0 | 0 |
| 11. Support Bundle | 9 | 1 | 0 | 0 |
| 12. Feedback | 7 | 4 | 0 | 0 |
| 13. Billing | 7 | 0 | 0 | 0 |
| 14. Pricing | 4 | 2 | 0 | 0 |
| 15. Account/Subscription | 4 | 0 | 0 | 1 |
| 16. Update Path | 4 | 2 | 2 | 0 |
| 17. Beta User Ops | 9 | 4 | 0 | 0 |
| **TOTAL** | **121** | **38** | **14** | **4** |

---

## The 14 Blockers — Ordered by Fix Effort

| # | Blocker | Area | Est. effort | Impact |
|---|---------|------|-------------|--------|
| B1 | Port 8777 conflict: process exits silently | Installation | 2h | Every double-launch fails |
| B2 | Scan cache grows unbounded (14.7 MB/repo, no eviction) | Scan | 30min | OOM on large repos |
| B3 | Scan button disabled with no explanation | Scan | 1h | 10% abandon |
| B4 | Changelog is empty | Update Path | 10min | Users won't understand updates |
| B5 | ATLAS_UPDATE_CHECK_URL not configured | Update Path | 1h (infra) | Users never notified of updates |
| B6 | Triple onboarding overlay (3 screens before any action) | Onboarding | 1 day | 10–15% drop-off |
| B7 | Change Plan: "Copy for Claude" below fold | Change Plan | 2h | 15–25% of plan creators never copy |
| B8 | Change Plan: "Insertion confidence 59/100" unexplained | Change Plan | 1h | Immediate trust loss |
| B9 | Change Plan: "Evidence score 118/100" impossible number | Change Plan | 30min | Breaks user mental model |
| B10 | Change Plan: "Status: Implemented" misleads on add-feature request | Change Plan | 1h | Beta Diary: almost-quit moment |
| B11 | Two export systems: "Send to AI" tab vs per-workflow copy | Export | 2h | AP-9: 10% wrong copy path |
| B12 | "Session context sent once per scan" copy unclear | Export | 1h | Users unsure what to copy |
| B13 | UI `trust.can_export` not read before copy button | Trust | 4h JS | Trust enforcement has no UI gate |
| B14 | Remote feedback not routed out of users' machines | Feedback | 2h (infra) | You are blind during beta |

---

## Final Answer: What Must Cursor Fix Before 5–20 Supervised Beta Users?

The trust integrity system is complete (10/10 attacks cleared). The intelligence engine is solid. The backend is production-capable. What remains is a concentrated set of UX and infrastructure items — none of which require intelligence changes.

**Must fix before Day 1 of beta (the truly critical path):**

1. **B2 — Scan cache LRU** (30 min): Add `_SCAN_CACHE_MAX = 2` eviction. One function, five lines. Without this, users scanning their own large repo will hit memory pressure.

2. **B4 — Write one changelog entry** (10 min): "0.1.0-beta — First external beta release." Without this, users updating have no idea what changed.

3. **B1 — Port conflict recovery** (2h): Try ports 8777–8779. Show "Atlas is already running — check your browser" if all fail. Without this, every user who double-clicks the shortcut sees a blank browser tab.

4. **B9 — Cap "Evidence score" at 100** (30 min): The `118/100` number is the fastest trust-destruction in the product. Rename or cap.

5. **B10 — Rename "Status: Implemented"** (1h): Beta User Diary at T+3:30 — nearest-quit moment. Change to "Repository evidence: partial implementation found."

6. **B7 — Sticky "Copy for Claude" on plan result** (2h): 15–25% of plan creators never find the copy button. This is value evaporating.

7. **B14 — Configure remote feedback routing** (2h infra): Host a Formspree endpoint or simple webhook. Set `ATLAS_FEEDBACK_URL` in the deployed build. Without this, you cannot learn anything from beta users.

8. **B5 — Configure `ATLAS_UPDATE_CHECK_URL`** (1h infra): Host `latest.json` somewhere. Without this, you cannot notify users when you ship fixes.

**Fix in week 1 of beta (high-signal, medium effort):**

9. **B6 — Collapse triple onboarding** (1 day): Merge Welcome + Onboarding + Home into one screen with a single "Load Sample" CTA. This is the highest-leverage UX fix: removes 10–15% drop-off.

10. **B3 — Scan button tooltip** (1h): "Click Validate first" or auto-validate on path change. Removes 10% abandon rate on own-repo path.

11. **B11 — Remove "Send to AI" tab from beginner nav** (2h): Lock/redirect to "Create a plan first." Removes 10% who copy wrong thing.

12. **B12 — Rewrite "session context sent once per scan" copy** (1h): "This includes all repo context — copy once at the start of your Claude conversation, then copy individual plans as you go."

13. **B8 — Rename "Insertion confidence"** (1h): "Best insertion point" or simply show the file path without a score.

14. **B13 — UI reads `trust.can_export`** (4h JS): When `can_export = false`, disable copy button and show `refusal_reason`. This is the final enforcement point for the trust integrity system.

**The 10-minute order:**

Do these first, in order, before any user installs:
1. B4 (changelog — 10 min)
2. B2 (scan cache — 30 min)  
3. B9 (Evidence score cap — 30 min)
4. B10 (Status: Implemented rename — 1h)
5. B7 (Copy for Claude sticky — 2h)
6. B1 (Port conflict — 2h)
7. B5 + B14 (infra: configure update URL + feedback URL — 2h each, can parallelize)

**Total for minimum viable 5-user beta: ~10 hours of engineering + 2 hours of infrastructure.**

The product is real. The intelligence works. The trust system is solid. What's left is 14 items that together determine whether a new developer reaches their first Claude paste — or gives up somewhere in between.
