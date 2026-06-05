# Phase 170 — Export Quality Delta (FULL vs MINIMAL)

**Verdict:** YES (conditional — re-run with ANTHROPIC_API_KEY for live confirmation)

## Quality & grounding by workflow

| Workflow | FULL quality | MIN quality | Δ quality | FULL grounding | MIN grounding | Δ grounding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| build | 4.00 | 4.00 | +0.00 | 4.50 | 4.50 | +0.00 |
| investigate | 4.00 | 4.00 | +0.00 | 4.50 | 4.50 | +0.00 |
| impact | 3.62 | 3.62 | +0.00 | 4.00 | 4.00 | +0.00 |

## Quality & grounding by repository

| Repo | FULL quality | MIN quality | Δ | FULL grounding | MIN grounding | Δ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FastAPI | 3.90 | 3.90 | +0.00 | 4.37 | 4.37 | +0.00 |
| Django | 3.80 | 3.80 | +0.00 | 4.23 | 4.23 | +0.00 |
| VS Code | 3.90 | 3.90 | +0.00 | 4.37 | 4.37 | +0.00 |
| Home Assistant | 3.90 | 3.90 | +0.00 | 4.37 | 4.37 | +0.00 |

## Interpretation

Phase 169 removed redundant prose while preserving top file paths and confidence.
If quality/grounding deltas stay within ±0.2, minimal exports deliver the same
actionable signal to Claude at far lower token cost.

- Measured quality delta: **+0.000** (target ≤ 0.2)
- Measured grounding delta: **+0.000** (target ≤ 0.2)
- Hallucination increase: **+0.00%** (target ≤ 2%)
