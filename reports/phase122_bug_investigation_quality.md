# Phase 122 — Bug Investigation Quality

## Format

Investigation output uses **`BUG INVESTIGATION PLAN`** with:

1. Symptom  
2. Most likely source (top grounded file or explicit)  
3. Likely files  
4. Likely symbols (filename stems only — no AST hallucination)  
5. Why  
6. Possible logical cause (intent-specific hypothesis)  
7. Evidence (graph scores, import neighborhood)  
8. What to inspect first  
9. Verification steps  
10. Confidence + limitations  

## Symptom coverage (intent specs)

| Example symptom | Intent | Expected grounding |
|-----------------|--------|-------------------|
| backtest better than paper | `paper_trading` | `services/backtest`, `paper_trading`, etc. |
| dashboard pnl wrong | `dashboard_pnl` | `ui/dashboard`, metrics paths |
| telegram alerts delayed | `delayed_alerts` | notify/telegram paths |
| position close fails | `position_close` | execution/order paths |
| scan graph wrong module count | `graph_module_count` | graph/scan/index paths |

## Quality rules enforced

- **No hallucinated paths** — only `production` graph module paths in `likely_modules`.
- **Explicit paths in text** — boosted to top of results.
- **Low confidence** when no modules match; limitations stated.
- Stack traces — paste into Investigate textarea (path substring match via index).

## API

- Primary: `POST /api/planning/investigate`  
- Legacy: `POST /api/bug-investigation` (trace-oriented; UI no longer separate)

## Remaining gaps

- No log ingestion or runtime profiling  
- No semantic code search beyond path keywords  
- Class/function names are filename stems only unless user names them in symptom

## Sample acceptance (planner fixture repo)

Symptom: *"dashboard pnl is wrong"* → likely includes `ui/dashboard.py` when present in graph.
