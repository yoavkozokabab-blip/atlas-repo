# Phase 91 — Benchmark-on-Engine Migration

**Status:** Implemented and verified
**Date:** 2026-05-30
**Goal:** Make `benchmark-quixbugs` measure the unified engine, retire the last
dual-path seam, and prove parity honestly — without chasing recall or hiding the
regression the naive migration would have caused.

---

## 0. TL;DR

- Added `benchmark-quixbugs --engine {unified,legacy}`. **Default is now
  `unified`**; `legacy` is kept only for comparison.
- The unified verdict counts **grounded** findings — algorithm-invariant
  violations (`semantic`) + fact-backed flow/taint defects
  (`data_flow`/`value_flow`/`security`). The noisy `pattern`-kind heuristics
  still run in the product but are excluded from the binary buggy/correct
  verdict (they are diagnostics, not defect assertions).
- **Result: exact parity.** Unified and legacy flag the **same 12 files**, 0 FP.
  QuixBugs P=100% / R=30%; Holdout P=100% / R=16.7%. All gates pass.
- The naive "any bug-class finding" verdict is reported transparently: it would
  reach R=60% but crater precision to 54.5% (20 FPs). That is the failure I
  fixed by detector routing, and it is documented, not hidden.

---

## 1. What changed

- New module `builder_core/bug_intelligence/engine_benchmark.py`:
  `evaluate_quixbugs_engine(project, grounded=True)` reusing the **exact**
  pairing/exclusion helpers of `builder_core/benchmark.py` (so the comparison is
  apples-to-apples), then deciding the verdict from unified-engine findings.
- CLI: `benchmark-quixbugs` gains `--engine`; dispatch routes to the legacy
  semantic evaluation or the unified engine evaluation. Default `unified`.
- No detector behavior changed. No rules added. The fix is **verdict routing**.

---

## 2. Metrics — legacy vs unified

| Path | Decision | Buggy | Correct | TP | FP | Precision | Recall |
|---|---|---|---|---|---|---|---|
| **legacy** (semantic path) | semantic findings | 40 | 40 | 12 | 0 | **100%** | **30%** |
| **unified** (default) | grounded findings | 40 | 40 | 12 | 0 | **100%** | **30%** |
| unified (naive, rejected) | any bug-class finding | 40 | 40 | 24 | 20 | 54.5% | 60% |

Holdout (unchanged by this phase): cases=12, TP=2, FP=0, **precision 100%**,
**recall 16.7%**, zero false positives on fixed code.

### Acceptance gates (unified engine)
| Gate | Target | Result |
|---|---|---|
| QuixBugs precision | ≥ 90% | **100%** ✅ |
| QuixBugs recall | ≥ 25% | **30%** ✅ |
| Holdout precision | ≥ 85% | **100%** ✅ |
| Holdout recall | ≥ 16.7% | **16.7%** ✅ |
| Synthetic security precision | ≥ 85% | **100%** (smoke) ✅ |
| Zero target-repo modification | required | ✅ (test-asserted) |
| No unsafe execution | required | ✅ |

---

## 3. Files where results differ

- **legacy vs unified (grounded, the default):** **none.** The two paths flag
  the identical set of 12 buggy files and 0 correct files — verified at file
  granularity (`identical TP set: True`). The migration is behavior-neutral.
- **legacy vs unified (naive, the rejected decision):** 20 correct files would
  flip to false positives, and 12 extra buggy files would flip to true
  positives. This is the regression that detector routing prevents.

---

## 4. False positives introduced by the unified engine

- **Grounded (default): 0.** No correct file is flagged.
- **Naive (rejected): 20**, all from `pattern`-kind heuristics:

| Detector (kind/rule) | Correct files falsely flagged |
|---|---|
| pattern/inconsistent_return | 16 |
| pattern/recursion_no_termination | 2 |
| pattern/off_by_one | 2 |
| pattern/suspicious_conditional | 1 |
| pattern/mutation_while_iterating | 1 |

Correct files affected (naive): depth_first_search, detect_cycle,
find_in_sorted, flatten, gcd, get_factors, hanoi, is_valid_parenthesization,
knapsack, kth, levenshtein, longest_common_subsequence, mergesort,
next_permutation, possible_change, powerset, quicksort, shortest_path_length,
subsequences, topological_ordering.

## 5. False negatives introduced by the unified engine

- **Grounded (default): 0.** Every file the legacy path caught, the unified path
  catches (identical TP set).
- The unified engine does not lose any in-domain recall relative to legacy.

## 6. Which migrated detectors caused the differences

The differences are **entirely** from the `pattern`-kind logic detectors, led by
`inconsistent_return`. The root cause is diagnostic, not a bug in the engine:

> `inconsistent_return` fires on a function that returns a value on one path and
> a different shape on another. In QuixBugs, the *buggy* and *correct* versions
> of an algorithm usually share the same return structure, so the heuristic
> fires on **both** — it is non-discriminative for a buggy/correct verdict. It is
> a useful review aid (it shows in `analyze-file`), but it cannot serve as a
> binary defect verdict.

The fact-backed detectors behave correctly: `unguarded_container_consumption`
(data_flow) and the security/value detectors fire on the buggy BFS and **not**
on the correct one, exactly as in Phases 87 and 89.

---

## 7. The fix (and why it is not a QuixBugs hack)

The verdict counts findings whose **provenance is grounded**:
`kind ∈ {semantic, data_flow, value_flow, security}`. It excludes
`kind == pattern`. This rule:

- is defined by **detector family/provenance**, not by file names, function
  names, or QuixBugs structure;
- mirrors the legacy semantics (legacy only ever counted the semantic signal);
- keeps every pattern detector running and visible in the product
  (`analyze-file` / `bug-scan`), where diagnostics are valuable;
- is exactly the "tighten engine detector routing" remedy the phase allows.

No new rules, no benchmark-shaped rules, no per-file special cases.

Dedupe was also verified: `unguarded_container_consumption` is emitted by both
the data-flow detector and the semantic layer; the engine collapses them by
`(file, line, rule)` to a single finding, so duplicate sources cannot inflate a
file's result (test: `test_duplicate_rule_from_two_sources_counts_once`).

---

## 8. Default + remaining legacy modules

- **Default benchmark engine: `unified`.** `--engine legacy` is retained solely
  for comparison/audit.
- **Remaining legacy modules** (compatibility/measurement only, no longer the
  product path):
  - `builder_core/benchmark.py` — legacy QuixBugs evaluation (now `--engine legacy`).
  - `builder_core/python_analysis.py` — used by the legacy evaluation and by the
    indexer; not on the unified product path.
  - `builder_core/semantic_reasoning.py` — wrapped by the engine's
    `AlgorithmAgent`; also used directly by the legacy evaluation.
  - `builder_core/external_benchmark.py` — holdout harness (unchanged this phase;
    next candidate for the same migration).

---

## 9. Limitations / honest notes

- The unified default reproduces legacy recall (30%) because the only grounded
  algorithm signal is still the (quarantined, name-bound) semantic rules. The
  pattern heuristics carry real extra recall (naive R=60%) but are too imprecise
  to count. Converting them to fact-backed, discriminative detectors is the path
  to lifting recall **with** precision — not loosening the verdict.
- The holdout harness (`external_benchmark.py`) still uses the legacy path; it
  was out of scope here and is the next seam to migrate the same way.

## 10. Next recommended phase

**Phase 92 — Migrate the holdout harness to the engine + make `inconsistent_return`
fact-backed.** (1) Apply the identical `--engine` treatment to the external
holdout so both benchmarks measure one engine. (2) Re-express `inconsistent_return`
using value-flow return facts so it distinguishes a genuine missing-return bug
from a benign value-or-None contract — turning the biggest naive-FP source into a
grounded, recall-positive detector.
