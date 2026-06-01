# Phase 104A — Token Accounting Instrumentation Foundation

**Status:** Implemented and verified.
**Date:** 2026-06-01
**Goal:** Add deterministic token accounting to the Phase 103 offline benchmark
framework **without changing JARVIS behavior or scoring logic**.

---

## 1. Reused estimator

`builder_core/benchmark_framework/tokens.py` (chars/4 heuristic, manual override)
now also exposes:

| Symbol | Role |
|---|---|
| `TokenBreakdown` | Structured breakdown dataclass |
| `build_token_breakdown()` | raw / JARVIS / final / optional answer |
| `prompt_metadata_comment()` | HTML comment for `.prompt.md` files |
| `attach_answer_to_breakdown()` | Fill answer tokens on `record-run` |
| `INSTRUMENTATION_VERSION` | `phase104a-v1` |

---

## 2. Instrumented surfaces

### Generated run packages

Per task / mode:

- `token_breakdown.{mode}.json` — full breakdown
- `run_log.{mode}.json` — includes `token_breakdown` + `estimated_input_tokens` aligned to `final_prompt_package`
- `{mode}.prompt.md` — leading `<!-- token_estimate metadata ... -->` comment (task prose unchanged)

### `manifest.json`

```json
"token_instrumentation": {
  "version": "phase104a-v1",
  "estimator": "chars_per_4_estimate",
  "fields": ["raw_prompt", "jarvis_context", "final_prompt_package", "answer_text"]
}
```

### `record-run`

- Estimates **output** tokens from answer text (override supported).
- Updates `token_breakdown.answer_text` when a breakdown exists.
- Does **not** change input estimate unless `--estimated-input-tokens` is passed.

### `summary`

Per-mode aggregates (unchanged scoring):

- `average_estimated_input_tokens`
- `average_estimated_output_tokens`
- `average_estimated_token_reduction_percent` (pairwise Codex vs JARVIS)

`summary.md` table now lists separate input/output averages.

---

## 3. Backward compatibility

- Older `run_log.*.json` files **without** `token_breakdown` still validate and load.
- Empty breakdowns are omitted on serialize (`RunLog.to_dict()`).
- Benchmark task prompts in `benchmark_tasks_v1.json` are untouched.

---

## 4. Verification

| Suite | Result |
|---|---|
| `test_phase104a_token_accounting.py` | 6 passed |
| `test_phase103_benchmark_framework.py` | 10 passed |
| Full `builder_core/tests` | **416 passed** |

---

## 5. Files

| File | Change |
|---|---|
| `benchmark_framework/tokens.py` | Breakdown + metadata helpers |
| `benchmark_framework/schema.py` | Optional `token_breakdown` on `RunLog` |
| `benchmark_framework/runner.py` | Package generation instrumentation |
| `benchmark_framework/cli.py` | Answer token attachment on record |
| `benchmark_framework/summary.py` | Input/output rows in markdown |
| `tests/test_phase104a_token_accounting.py` | New regressions |

---

## 6. Notes

- All numbers are **estimates** (`token_numbers_are_estimates: true`).
- JARVIS `ask` / `indexer` paths are not invoked differently; only benchmark packaging is instrumented.
- `codex_alone` breakdowns record `jarvis_context_tokens: 0` (context not injected for that arm).
