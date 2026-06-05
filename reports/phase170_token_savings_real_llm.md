# Phase 170 — Token Savings (Real LLM Path)

**Export reduction:** 79.4% (target ≥ 70%)
**Total token reduction:** 71.0%

## Per-repository export tokens

| Repo | FULL export avg | MINIMAL export avg | Reduction |
| --- | ---: | ---: | ---: |
| FastAPI | 1462 | 272 | 81.4% |
| Django | 1524 | 290 | 80.9% |
| VS Code | 2175 | 506 | 76.7% |
| Home Assistant | 1919 | 388 | 79.8% |

## Session amortization

MINIMAL_EXPORT uses `ATLAS_SESSION v1` once per scan (not per question).
Per-question savings above are in addition to eliminating repeated compact context.

## Total tokens (export + Claude response)

- FULL_EXPORT avg total: **1981** tokens
- MINIMAL_EXPORT avg total: **575** tokens
- Reduction: **71.0%**

## Economics

At 60 tasks/session, minimal exports reduce repeated context by ~70–90% while
keeping Claude response sizes similar (same task, narrower input).
