# Phase 93D — Cross-file Consumer Mechanism (Implementation, Disabled by Default)

**Status:** Implemented and verified. **Shipped DISABLED.**
**Date:** 2026-05-30
**Design:** `reports/phase93d_cross_file_consumer_gate_design.md`
**Scope:** Add gated cross-file consumption for `inconsistent_return` only.
No default behavior change; no benchmark change; no real-repo enablement.

---

## 0. TL;DR

- Added `fact_detectors.CROSS_FILE_CONSUMPTION_ENABLED = False` (default).
- When `False`, `inconsistent_return` behaves **exactly as Phase 93B** (intra-file
  evidence only). When `True`, it merges `interproc.cross_file.usage_by_callee`
  into the promotion decision — **only** in project mode where those facts exist.
- The promotion rule is unchanged in spirit: promote iff ≥1 caller (intra **or**
  enabled cross-file) dereferences and **no** caller null-checks; any null-check /
  unresolved-only evidence vetoes.
- **The only file changed is `fact_detectors.py`.** QuixBugs 12/0, Holdout 2/0
  unchanged. Full suite: **183 passed.** No real-repo enablement was done.

---

## 1. What changed (one detector, gated)

`builder_core/bug_intelligence/fact_detectors.py`:
- New module flag `CROSS_FILE_CONSUMPTION_ENABLED = False`.
- The 93B `_promote(...)` is generalised to two pure helpers:
  - `_merge_usage(qual, intra, cross)` — OR-merges the intra-file usage with the
    cross-file usage (`cross` is `None` unless the flag is on **and** the facts are
    present), returning `None` when no resolved caller exists anywhere.
  - `_promote_from_usage(merged)` — promote iff `dereferenced ∧ ¬null_checked`.
- `detect_inconsistent_return` reads cross-file usage **only** under
  `CROSS_FILE_CONSUMPTION_ENABLED`, defensively (`interproc.cross_file` absent →
  `None`). The promotion gate (`INTERPROC_PROMOTION_ENABLED`) and the missing-
  return shape trigger are unchanged.

No other module was touched — not `engine.py`, `cross_file.py`, `callgraph.py`,
`summaries.py`, `imports.py`, `module_map.py`, `finding.py`, or
`engine_benchmark.py`.

## 2. Why default-off is exact 93B and the benchmark is immune

- **Flag off → `cross = None`** in `_merge_usage`, so the merged evidence is the
  intra-file usage only — byte-for-byte the 93B decision. Proven by
  `test_flag_off_is_exact_93b`.
- **The benchmark is single-file.** `engine_benchmark` calls `analyze_source` per
  file with no project context, so `interproc.cross_file` is never produced.
  Therefore the benchmark is unchanged **even with the flag on** — proven by
  `test_quixbugs_unchanged_even_with_flag_on`.

## 3. Behavior with the flag ON (project mode only)

| Cross-file caller evidence | Result |
|---|---|
| dereferences, no null-check | **promoted** → `value_flow` |
| null-checks (or mixed deref+null-check) | quarantined → `pattern` |
| value-only use (no deref) | quarantined |
| UNRESOLVED caller (e.g. star import) | ignored → quarantined |

All four are test-asserted on tiny multi-file fixtures. The same `helper` that
quarantines under the flag-off run promotes under the flag-on run only when a
resolved cross-file caller dereferences it without a null-check.

## 4. Results

| Check | Result |
|---|---|
| `pytest builder_core/tests/ -q` | **183 passed** (171 + 12 new) |
| Default `CROSS_FILE_CONSUMPTION_ENABLED` | **False** |
| QuixBugs (unified) | **12 TP / 0 FP** |
| Holdout (unified) | **2 TP / 0 FP** |
| QuixBugs with flag forced on | **12 TP / 0 FP** (single-file immune) |
| `engine_benchmark.BENCHMARK_VERDICT_KINDS` | `{semantic, data_flow, value_flow}` (unchanged) |
| Security smoke | passed (static only) |

Acceptance: ✅ no default behavior change · ✅ no benchmark change · ✅ no
auto-promotion from cross-file unless the flag is on · ✅ no real-repo validation
done · ✅ only gated cross-file consumption changed · ✅ no engine/callgraph/
cross_file refactor · ✅ no new findings/rules.

## 5. Tests (`test_phase93d_cross_file_consumer.py`, 12)

flag default is False; flag-off == 93B; flag-on promotes on cross-file deref;
flag-on quarantines on cross-file null-check / mixed / value-only; flag-on ignores
UNRESOLVED (star-import) callers; `analyze_source` unchanged with the flag on (no
`cross_file` key in single-file); QuixBugs 12/0 with flag off **and** forced on;
Holdout 2/0; `engine_benchmark` verdict kinds unchanged.

## 6. Honest notes

- **No recall movement in default operation.** The flag is off; nothing changes
  until a human enables it after the gates pass. This phase ships the *mechanism*,
  not the *enablement*.
- **Enabling is deliberately NOT done.** Per the design, flipping the flag to
  `True` requires a resolution-precision (100% sampled) and a 0-FP real-repo
  measurement, which are a separate, human-reviewed phase. None of that was
  performed here.
- **Instant rollback:** set the flag back to `False` (default) → exact 93B.

## 7. Next

The enablement phase: assemble a real-repo correct corpus, run the
resolution-precision audit and the 0-FP multi-file + real-repo measurement, and —
only if both pass — flip `CROSS_FILE_CONSUMPTION_ENABLED` to `True`.
