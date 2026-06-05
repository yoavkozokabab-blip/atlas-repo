# Phase 157A - Trust Score

## Scoring Model

Weighted score used for this audit:

- CORRECT = 1.00
- MOSTLY_CORRECT = 0.80
- PARTIALLY_CORRECT = 0.45
- MISLEADING = 0.10
- WRONG = 0.00

This intentionally gives partial credit for directional usefulness while heavily penalizing misleading or failed outputs.

## Overall Trust

| Metric | Value |
|---|---:|
| Samples | 150 |
| Trust score | 45.8/100 |
| Actionable without major rework (CORRECT + MOSTLY_CORRECT) | 10.0% |
| Usable with careful review | 88.7% |
| Unsafe / misleading | 11.3% |

## Workflow Trust

| Workflow | Trust score | Actionable % | Usable with review % | Unsafe % |
|---|---:|---:|---:|---:|
| build | 42.2 | 0.0 | 92.0 | 8.0 |
| investigation | 40.8 | 0.0 | 88.0 | 12.0 |
| impact | 54.4 | 30.0 | 86.0 | 14.0 |

## Repository Trust

| Repo | Trust score | Actionable % | Unsafe % | Notes |
|---|---:|---:|---:|---|
| home_assistant | 33.3 | 0.0 | 33.3 | Large graph but concept leakage and investigation weaknesses. |
| django | 41.7 | 0.0 | 9.5 | Mostly thin but stable; migration/build and impact had pollution. |
| fastapi | 59.2 | 27.8 | 0.0 | Impact stronger than Build/Investigation. |
| vscode | 45.0 | 0.0 | 0.0 | Directionally useful but thin; partial graph/unresolved imports. |
| airflow | 55.3 | 27.8 | 11.1 | Impact stronger than Build/Investigation. |
| celery | 53.1 | 16.7 | 0.0 | Impact stronger than Build/Investigation. |
| typeorm | 49.2 | 11.1 | 5.6 | Impact stronger than Build/Investigation. |
| kubernetes | 32.5 | 0.0 | 27.8 | Graph health/language support mismatch; Impact mostly failed. |

## Reviewer Guidance

- Treat Atlas outputs as **leads**, not conclusions.
- Require a human to open the named files before acting.
- Do not rely on Investigation root-cause titles without independent proof.
- Treat Impact as strongest on supported Python/TypeScript repos and weakest on unsupported/low-module graphs.
- Any `ok=true` output with `mock=true`, target-not-found, or low graph coverage should be treated as failed, not successful.

## Verdict

**PARTIALLY trusted.** Atlas is useful for narrowing context, but not safe as an autonomous or authoritative answer source.
