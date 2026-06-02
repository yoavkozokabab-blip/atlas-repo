# Phase 120 — Change Planner + Investigation Engine

**Date:** 2026-06-02  
**Product version:** `phase120-change-planner-investigation`  
**Scope:** Desktop planning layer only — no autonomous coding agent, no Builder Core analysis semantics changes.

## Summary

Atlas moves from **repository viewer** to **repository engineer** (planning-first):

| Capability | Endpoint | UI tab |
|------------|----------|--------|
| Change Plan | `POST /api/planning/change` | **Build** |
| Investigation Plan | `POST /api/planning/investigate` | **Investigate** |
| Impact simulation (enriched) | `POST /api/planning/impact` | Build (optional) + existing **Impact** |

Existing tabs unchanged: Command Center (graph), Intelligence, Impact, Bug Hunt, Export, Copilot.

## Architecture

```
User input
    → jarvis_desktop/api.py (plan_change, investigate_symptom, change_impact_simulation)
        → planning_engine.py (evidence from graph + index + risks + summary)
            → formatted markdown + Claude/Codex/Cursor prompts
```

**Trust rules (Part F):**

- Every suggested file path comes from the **production graph** or explicit mention in user text.
- `confidence`, `evidence`, and `limitations` on every plan.
- No code generation; prompts instruct tools to **plan first**.
- Symptom engine uses keyword intent routing — not runtime profiling.

## Part A — Change Plan

`planning_engine.plan_change()` detects feature intents (authentication, billing, caching, audit logging, dark mode, WebSocket, Redis, …), scores production modules by path overlap + risk + fan-in, and returns:

- Likely modules / subsystems / entry points  
- Files to inspect first  
- Outbound/inbound dependencies (resolved import edges only)  
- Architectural risks (from risk ranking + intent notes)  
- Tests likely affected  
- Estimated size: Small / Medium / Large  
- Confidence: low → medium-high  

Markdown formatter: `format_change_plan_markdown()`.

## Part B — Implementation prompts

`build_implementation_prompts()` returns:

- **claude** — structured plan-first brief with context, files, risks, limitations  
- **codex** — compact checklist-style prompt  
- **cursor** — `@workspace` oriented planning prompt  

Copy buttons on **Build** tab.

## Part C — Investigation Engine

`planning_engine.investigate_symptom()` routes natural-language symptoms:

| Symptom class | Example |
|---------------|---------|
| `paper_trading` | "backtest is better than paper trading" |
| `delayed_alerts` | "Telegram alerts are delayed" |
| `memory_growth` | "memory usage keeps increasing" |
| `dashboard_mismatch` | "Dashboard numbers are wrong" |
| `position_close` | "Position closes fail sometimes" |

Returns investigation plan + evidence + suggested questions + export prompts.

**Bug Hunt** (`POST /api/bug-investigation`) remains for stack traces; **Investigate** is symptom-first.

## Part D — Change impact simulation

`change_impact_simulation()` wraps existing `impact()` and adds:

- `simulation.potentially_affected_modules`  
- `simulation.potentially_affected_subsystems`  
- `simulation.risk_level`  
- `simulation.recommended_verification`  
- `simulation.tests_likely_affected`  
- `limitations` (static graph caveats)

## Part E — UX

- Nav: **Build**, **Investigate** (locked until scan, same as other tabs).  
- Build: request textarea → plan → evidence → copy Claude/Codex/Cursor → optional impact simulation.  
- Investigate: symptom textarea → plan → module tags → copy prompts.

## Part G — Tests

`jarvis_desktop/tests/test_phase120_change_planner_and_investigation_engine.py` (13 tests):

- Change: authentication, billing, logging  
- Investigation: paper trading, dashboard, delayed alerts  
- Prompts: Claude/Codex/Cursor content  
- Impact: file + module level  
- Analytics isolation during planning  
- Route registration  
- No hallucinated paths (`_assert_grounded_paths`)

**Suite results:**

| Suite | Result |
|-------|--------|
| Phase 120 tests | 12 passed |
| Full `jarvis_desktop/tests` | 242 passed |

Route count: **30** (`test_phase107`, `test_phase119` updated).

## Manual walkthrough

1. `py -3 run_jarvis_desktop.py` from `local_jarvis`.  
2. Scan a repository (or Demo Mode).  
3. **Build** → enter `Add user authentication` → **Generate Change Plan** → review CHANGE PLAN block → **Copy Claude**.  
4. Optional: simulate impact on first listed file.  
5. **Investigate** → enter `The backtest is better than paper trading` → **Generate Investigation Plan** → **Copy Cursor**.  
6. Paste prompts into Claude/Codex/Cursor — implementation stays in those tools.

## Files added/changed

| File | Role |
|------|------|
| `jarvis_desktop/planning_engine.py` | Core planner + investigator + prompt builders |
| `jarvis_desktop/api.py` | API wrappers + analytics events |
| `jarvis_desktop/server.py` | Three new routes (+ FastAPI) |
| `jarvis_desktop/static/index.html` | Build + Investigate views |
| `jarvis_desktop/static/app.js` | UI handlers |
| `jarvis_desktop/tests/test_phase120_*.py` | Regression tests |

## Success criteria

| Criterion | Status |
|-----------|--------|
| "What should I change?" → grounded plan | ✓ |
| "Where should I look for this bug?" → investigation plan | ✓ |
| Export prompts for Claude/Codex/Cursor | ✓ |
| Local-first, planning-only, no autonomous agent | ✓ |
| Confidence + evidence + limitations | ✓ |
| No hallucinated file names | ✓ (test-enforced) |

## Known limitations (honest)

- Intent routing is **heuristic**, not LLM-based.  
- Unmatched requests return low confidence with explicit limitations.  
- Dependency and impact data are **static import graph** only.  
- Symptom investigation cannot replace logs, profilers, or reproduction steps.
