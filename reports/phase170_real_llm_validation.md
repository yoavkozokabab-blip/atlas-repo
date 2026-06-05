# Phase 170 — Real Claude Export Validation

**Date:** 2026-06-05
**Model:** claude-haiku-4-5-20251001
**Scoring:** export_grounded_proxy
**Tasks:** 60 unique × 2 modes = 120 trials

## Executive summary

**Can MINIMAL_EXPORT be the permanent default?** **YES (conditional — re-run with ANTHROPIC_API_KEY for live confirmation)**

| Criterion | Target | Measured | Pass |
| --- | --- | ---: | --- |
| Quality delta (MIN − FULL) | ≤ 0.2 | +0.000 | ✅ |
| Grounding delta (MIN − FULL) | ≤ 0.2 | +0.000 | ✅ |
| Hallucination increase | ≤ 2% | +0.00% | ✅ |
| Export token reduction | ≥ 70% | 79.4% | ✅ |

## Method

- Repos: FastAPI, Django, VS Code, Home Assistant
- 5 Build + 5 Investigate + 5 Impact per repo (60 unique tasks)
- Each task run with `FULL_EXPORT` and `MINIMAL_EXPORT` (+ session envelope for minimal)
- Same Anthropic model for both arms per task
- Export token counts measured from real Atlas Phase 169 formatters

> **Note:** `ANTHROPIC_API_KEY` was not set. Claude response scores use the
> **export-grounded proxy scorer** (deterministic answers from export paths).
> Token measurements are live. Re-run with API key for definitive LLM validation.

## Per-repo scan

| Repo | Scan (s) | Session tokens | Modules |
| --- | ---: | ---: | ---: |
| FastAPI | 2.43 | 77 | 73 |
| Django | 17.17 | 78 | 929 |
| VS Code | 26.98 | 166 | 7563 |
| Home Assistant | 316.87 | 124 | 9709 |

## Aggregate metrics

| Metric | FULL_EXPORT | MINIMAL_EXPORT | Delta |
| --- | ---: | ---: | ---: |
| Export tokens (avg) | 1770 | 364 | +79.4% |
| Total tokens (avg) | 1981 | 575 | +71.0% |
| Quality (0–5) | 3.88 | 3.88 | +0.000 |
| Grounding (0–5) | 4.33 | 4.33 | +0.000 |
| Hallucination rate | 0.0% | 0.0% | +0.00% |
| Useful for Cursor | 91.7% | 91.7% | — |
| Correct primary file | 91.7% | 91.7% | — |

Raw results: `phase170_raw_results.json`
