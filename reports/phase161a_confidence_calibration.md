# Phase 161A - Confidence Calibration

Date: 2026-06-05

## Summary

High confidence does **not** mean correctness in this run. No confidence bucket produced a strictly CORRECT result. Low confidence correlates with the worst failures, but high and medium confidence still include many misleading outputs.

| Confidence | Samples | CORRECT | MOSTLY_CORRECT | PARTIAL | MISLEADING | WRONG | Actionable % | Unsafe % | Trust score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high | 103 | 0 | 9 | 70 | 24 | 0 | 8.7 | 23.3 | 39.9 |
| medium | 131 | 0 | 13 | 89 | 29 | 0 | 9.9 | 22.1 | 40.7 |
| low | 66 | 0 | 0 | 42 | 13 | 11 | 0.0 | 36.4 | 30.6 |

## Confidence By Workflow

| Workflow | Confidence | Samples | CORRECT | MOSTLY_CORRECT | PARTIAL | MISLEADING | WRONG | Trust score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| build | high | 28 | 0 | 6 | 17 | 5 | 0 | 46.2 |
| build | medium | 60 | 0 | 8 | 40 | 12 | 0 | 42.7 |
| build | low | 12 | 0 | 0 | 9 | 3 | 0 | 36.3 |
| investigation | high | 23 | 0 | 3 | 14 | 6 | 0 | 40.4 |
| investigation | medium | 65 | 0 | 5 | 45 | 15 | 0 | 39.6 |
| investigation | low | 12 | 0 | 0 | 7 | 5 | 0 | 30.4 |
| impact | high | 52 | 0 | 0 | 39 | 13 | 0 | 36.3 |
| impact | medium | 6 | 0 | 0 | 4 | 2 | 0 | 33.3 |
| impact | low | 42 | 0 | 0 | 26 | 5 | 11 | 29.0 |

## Target Resolution

| Target resolution | Samples | CORRECT | MOSTLY_CORRECT | PARTIAL | MISLEADING | WRONG | Trust score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| failed | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| not_applicable | 200 | 0 | 22 | 132 | 46 | 0 | 40.8 |
| resolved | 89 | 0 | 0 | 69 | 20 | 0 | 37.1 |

## Unknown Mode Usage

| Unknown mode used | Samples | CORRECT | MOSTLY_CORRECT | PARTIAL | MISLEADING | WRONG | Trust score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| true | 179 | 0 | 15 | 131 | 33 | 0 | 41.5 |
| false | 121 | 0 | 7 | 70 | 33 | 11 | 33.4 |

## Graph Health Calibration

| Graph health | Samples | CORRECT | MOSTLY_CORRECT | PARTIAL | MISLEADING | WRONG | Trust score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| healthy | 36 | 0 | 5 | 24 | 7 | 0 | 43.1 |
| partial | 114 | 0 | 6 | 82 | 26 | 0 | 38.9 |
| unsupported | 36 | 0 | 0 | 16 | 9 | 11 | 22.5 |
| watch | 114 | 0 | 11 | 79 | 24 | 0 | 41.0 |

## Answers To Calibration Questions

- Does high confidence mean correctness? **No.** High-confidence results had 0 CORRECT, 9 MOSTLY_CORRECT, 70 PARTIAL, and 24 MISLEADING outputs.
- Do low-confidence outputs correlate with errors? **Partly.** Low confidence contains all 11 WRONG results, but it also contains 42 PARTIAL outputs; it is a warning signal, not a full quality classifier.
- Are wrong outputs now rare? **Yes, but misleading outputs are not.** WRONG was 11/300 (3.7%), while MISLEADING+WRONG was 77/300 (25.7%).
- Is unknown mode being used correctly? **Only partially.** It appears to reduce hard WRONG outputs in some cases, but it is overused and often degrades into generic fallback behavior.

## Calibration Failures

- 53 samples were tagged as confidence mismatches.
- 300/300 samples returned `ok=true`, including 66 MISLEADING and 11 WRONG outputs. This is the clearest remaining fake-success semantic problem.
- Graph-health labels are better than the Phase 157A Kubernetes healthy/unsupported mismatch, but graph health still does not predict output quality reliably.
