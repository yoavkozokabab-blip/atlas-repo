# Result explanation quality — format change report

## Summary

Atlas workflow results (Debug, Change Plan, What Breaks, Repository Understanding) now use a shared structured report format instead of raw internal dumps or beginner-only **Files / Order** lists.

**New module:** `jarvis_desktop/result_reports.py` — presentation-only formatters; engine outputs unchanged.

## New result structure (all supported workflows)

1. **Executive Summary** — 2–4 plain-English sentences; paraphrases the request instead of echoing typos verbatim.
2. **Direction block** — workflow-specific (likely cause / implementation strategy / affected systems).
3. **Evidence** — each item explains *why it matters*.
4. **Confidence** — Low/Medium/High + Weak/Moderate/Strong evidence + reason (no fake percentages).
5. **Ranked files** — path, why selected, risk, recommended action.
6. **Verification steps** — what / where / confirms / rules out (when derivable).
7. **Copy prompt** — polished Claude/Cursor/Codex prompt with goal, files, evidence, verification, constraints.

## Before / after — Debug

**Before (beginner card):**
```
Symptom: live paper fills diverge from backtest
Files
- services/live_paper_engine.py
How to confirm
- Compare fill timestamps...
```

**After (excerpt):**
```
## Executive Summary
Atlas analyzed the reported symptom and identified 1 grounded hypothesis...
The strongest lead points to `services/live_paper_engine.py`...

## Most likely cause
- Likely cause: Fill price logic may differ between live and backtest paths.

## Ranked files
1. `services/live_paper_engine.py`
   Why: Live and backtest share symbols but may use different fee logic.
   Risk: Medium
   Action: Inspect call paths and data flow here.
```

## Before / after — Change Plan

**Before (markdown export):**
```
CHANGE PLAN
Goal: Add structured logging...
Files to inspect first:
- api/handlers.py
Implementation order (static heuristic):
- api/handlers.py
```

**After (excerpt):**
```
## Executive Summary
Atlas mapped the requested change to 2 primary file(s) in api, starting at `api/handlers.py`...

## Recommended implementation direction
- Strategy: api/handlers.py → core/logging.py
- Safest first change: Begin with `api/handlers.py` — confirm current behavior before broad edits.
- Expected risk: Medium — estimated size Small.
```

## Files changed

| File | Change |
|------|--------|
| `jarvis_desktop/result_reports.py` | **New** shared report builders + markdown formatters |
| `jarvis_desktop/planning_engine.py` | Delegate `format_*_markdown` to `result_reports` |
| `jarvis_desktop/api.py` | Attach `report` + `formatted` to build/investigate/impact; repository understanding copilot |
| `jarvis_desktop/static/atlas_zero_friction.js` | Structured beginner result cards; copy prompts from report |
| `jarvis_desktop/static/app.js` | Copilot renders structured repository report |
| `jarvis_desktop/static/atlas_beta.js` | Impact export uses `formatted` when present |
| `jarvis_desktop/tests/test_result_explanation_quality.py` | **New** unit tests |
| `jarvis_desktop/tests/test_phase120_*.py`, `test_phase129_*.py` | Updated header assertions |

## Tests run

```
py -3 -m pytest jarvis_desktop/tests/test_result_explanation_quality.py \
  jarvis_desktop/tests/test_phase120_change_planner_and_investigation_engine.py \
  jarvis_desktop/tests/test_phase176_first_impression.py \
  jarvis_desktop/tests/test_phase129_evidence_engine.py \
  jarvis_desktop/tests/test_phase122_product_hardening.py -q
```

**Result:** 52 passed
