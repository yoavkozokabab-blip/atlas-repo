# Phase 146B — True Beta Blocker Fixes

Date: 2026-06-02

Scope: fix the six NO-GO blockers from `reports/phase146a_beta_blocker_revalidation.md`. No new features, intelligence systems, billing changes, or unrelated UI polish.

Product version: `phase146b-true-beta-blocker-fixes`

## Blocker Fixes

| # | Blocker | Status | Evidence |
|---:|---|---|---|
| 1 | Default startup readiness | **RESOLVED** | `install_support.startup_checks().ready=true` without `JARVIS_DESKTOP_DATA`; writable path via `data_paths.resolve_desktop_data_dir()` with `%LOCALAPPDATA%\Atlas\desktop_data` or temp fallback |
| 2 | Demo Impact quick-start (`core/util.py` mock) | **RESOLVED** | UI examples and guided walkthrough use `core/hub.py`; `api.impact('core/hub.py')` returns `mock≠true` with real importers on small demo |
| 3 | Build Plan `add rate limiting` → `intent=general` | **RESOLVED** | `_FEATURE_SPECS['rate_limiting']` + domain concept `rate_limiting`; `plan_change('add rate limiting').intent == rate_limiting` |
| 4 | Investigation duplicate events → EMA/trading | **RESOLVED** | Short-alias word-boundary fix (`ema` no longer matches inside `being`); `duplicate_events` symptom spec; pub/sub investigation override; trading path penalty |
| 5 | Export branding | **RESOLVED** | Context packets use `# ATLAS REPOSITORY CONTEXT` and Atlas preambles; no user-facing `JARVIS REPOSITORY CONTEXT` |
| 6 | Feedback/support implies network send | **RESOLVED** | `feedback.js`: “Save locally”, “Saved locally”; optional `REMOTE_FEEDBACK_URL` hook disabled; support page shows data directory |

## Implementation Summary

- **`jarvis_desktop/data_paths.py`** — shared writable data directory resolution with automatic fallback.
- **`install_support.py`**, **`analytics.py`**, **`usage/store.py`**, **`billing/store.py`** — use shared data path; startup/diagnostics expose `data_dir_info`.
- **`planning_engine.py`** — `rate_limiting` build intent; `duplicate_events` investigation intent; pub/sub evidence override; demo path boosts for `core/hub`.
- **`atlas_knowledge/engine.py`** — word-boundary matching for aliases ≤4 characters (fixes `ema` ⊂ `being`).
- **`api.py`** — Atlas export branding; diagnostics `data_dir` field; version bump.
- **`static/app.js`**, **`atlas_beta.js`**, **`feedback.js`**, **`feedback.html`**, **`support.js`** — demo impact target, local-only feedback copy, data directory in support UI.

## Validation

### Targeted pytest (default data dir, no env override)

```text
31 passed (phase139, phase141, phase143, phase146, phase146b, context export)
```

Includes:

- `test_startup_checks_pass_in_dev`
- `test_startup_status_route`
- `test_phase146b_true_beta_blockers.py` (all cases)

### Manual API smoke (small demo, default paths)

| Check | Result |
|---|---|
| Startup `ready` | `true` |
| Build `add rate limiting` | `intent=rate_limiting`, `concept_id=rate_limiting` |
| Investigate duplicate events | `intent=duplicate_events`, `concept_id=pub_sub`, not trading/EMA |
| Impact `core/hub.py` | `mock` absent/false, direct importers present |
| Export compact | contains `ATLAS REPOSITORY CONTEXT`, no `JARVIS REPOSITORY CONTEXT` |

## Out of Scope (unchanged)

- Installer artifact `Atlas_Setup.exe` still not present in workspace.
- CDN graph scripts (`unpkg`) still on Home.
- Full-repo self-scan timeout evidence not re-run.
- Billing untouched.

## Final Verdict

**GO** for a **5-user private beta** with operator onboarding (Python launcher, sample repo first, support bundle if issues).

**NO-GO** for a **10-user self-serve beta** until installer artifact exists and CDN/offline first impression is addressed (Phase 146A residual items).

Reason: the six critical first-session blockers that caused mock output, failed startup, misleading feedback, and wrong routing are cleared. A small guided cohort can validate workflows; broader self-serve launch still needs installer and offline graph resilience.
