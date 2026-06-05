# Phase 161A - Trust Score

Date: 2026-06-05

## Scoring Model

- CORRECT = 1.00
- MOSTLY_CORRECT = 0.80
- PARTIAL = 0.45
- MISLEADING = 0.10
- WRONG = 0.00

The model matches the Phase 157A scoring weights, with `PARTIAL` equivalent to the old `PARTIALLY_CORRECT` bucket.

## Overall Trust

| Metric | Value |
| --- | --- |
| Samples | 300 |
| Trust score | 38.2/100 |
| Phase 157A trust score | 45.8/100 |
| Delta | -7.6 |
| Actionable without major rework (CORRECT + MOSTLY_CORRECT) | 7.3% |
| Usable with careful review | 74.3% |
| Unsafe / misleading | 25.7% |
| Final verdict | NOT TRUSTED |

## Workflow Trust

| Workflow | Trust score | Actionable % | Usable with review % | Unsafe % | Strict CORRECT |
| --- | --- | --- | --- | --- | --- |
| build | 42.9 | 14.0 | 80.0 | 20.0 | 0 |
| investigation | 38.7 | 8.0 | 74.0 | 26.0 | 0 |
| impact | 33.1 | 0.0 | 69.0 | 31.0 | 0 |

## Repository Trust

| Repo | Trust score | Actionable % | Unsafe % | Graph health | Language |
| --- | --- | --- | --- | --- | --- |
| home_assistant | 32.4 | 2.6 | 38.5 | partial | python |
| django | 41.4 | 12.8 | 23.1 | watch | python |
| fastapi | 44.1 | 12.8 | 15.4 | watch | python |
| vscode | 45.9 | 7.7 | 5.1 | partial | typescript |
| airflow | 38.2 | 5.6 | 25.0 | partial | python |
| celery | 43.1 | 13.9 | 19.4 | healthy | python |
| typeorm | 37.2 | 2.8 | 25.0 | watch | typescript |
| kubernetes | 22.5 | 0.0 | 55.6 | unsupported | go |

## Old/New Correctness Targets

| Metric | Old | New | Result |
| --- | --- | --- | --- |
| Trust score | 45.8/100 | 38.2/100 | -7.6 |
| Impact CORRECT | 12/50 | 0/100 | strict correct count did not reproduce |
| Build CORRECT | 0/50 | 0/100 | no strict correct output |
| Investigation CORRECT | 0/50 | 0/100 | no strict correct output |

## Reviewer Guidance

- Treat Atlas results as leads, not conclusions.
- Do not act on Build Plans without opening the named boundaries and checking whether the selected files match the request.
- Do not trust Investigation root causes without concrete code evidence and path-level proof.
- Do not trust Impact when target resolution failed or when the graph is unsupported/very small.
- Treat any `ok=true` output that is target-not-found, unknown-mode, generic fallback, or low-evidence as not actually successful.

## Verdict

**NOT TRUSTED.** The measured trust score went down from 45.8 to 38.2, and strict correctness did not reproduce for Impact, Build, or Investigation. Atlas is still useful for narrowing context, but it is not ready to be trusted as an authoritative developer answer system.
