# Phase 92A — Holdout Validation on the Unified Engine

**Status:** Implemented and verified
**Date:** 2026-05-30
**Scope:** Migrate the external holdout benchmark onto the unified engine. No new
detectors, no `inconsistent_return` work, no recall expansion, no broad refactor.

---

## 0. TL;DR

- Added `evaluate_holdout_engine()` + `format_holdout_report()` to
  `engine_benchmark.py`: the out-of-domain holdout is now measured through the
  unified engine, with the same grounded-kind verdict as the QuixBugs engine path.
- Switched `scripts/run_phase84_holdout_benchmark.py` to the **unified engine as
  the primary, pass/fail-driving path**; the legacy semantic numbers remain only
  as a clearly labeled comparison and never drive pass/fail.
- **QuixBugs unified: 12 TP / 0 FP (unchanged).** **Holdout unified: 2 TP / 0 FP**
  (exact parity with the legacy holdout). Full suite: 108 passed.

---

## 1. What changed and why

### Engine-based holdout evaluator (`engine_benchmark.py`)
`evaluate_holdout_engine()` discovers the holdout pairs
(`builder_core/benchmarks/holdout/pairs/<case>/{buggy,fixed}.py` + `manifest.json`)
— **discovery replicated locally so the engine path has zero dependency on the
legacy `external_benchmark` module** — runs each file through
`engine.analyze_source`, and applies the grounded verdict. A case is a true
positive if `buggy.py` yields ≥1 grounded finding, a false positive if `fixed.py`
does. Read-only; no analyzed code is executed.

### Verdict routing fix (the one judgment call)
Routing the holdout through the engine initially produced **1 false positive**:
the engine's **security** taint detector flagged `path_traversal` on the
`bugsinpy_pysnooper_encoding` **fixed** file (a file-open review lead present on
*both* buggy and fixed). That is a category error: the QuixBugs/holdout corpora
measure **logic/algorithm** bugs, while security taint findings are a separate
capability with their **own** benchmark (`smoke_phase89`). A medium-confidence
review lead that fires identically on buggy and fixed is non-discriminative here.

Fix (the same "count the signal relevant to the measurement" routing as Phase 91):
the benchmark verdict counts `BENCHMARK_VERDICT_KINDS = {semantic, data_flow,
value_flow}` and excludes the `security` kind. This is:
- a **no-op for QuixBugs** (security never fires there → still 12 TP / 0 FP), and
- the removal of the single holdout FP → **2 TP / 0 FP**, exact parity with legacy.

The excluded security finding is **shown, not hidden** (it still appears in
`analyze-file` / `security-scan` and in this report). No detector behavior was
changed; only the verdict kind-set.

### Script (`run_phase84_holdout_benchmark.py`)
Primary output = unified engine (QuixBugs + holdout). Legacy semantic numbers are
printed under a `[comparison only]` label, wrapped in `try/except`, and explicitly
do **not** affect the return code. Pass/fail is driven solely by the unified-engine
holdout availability.

---

## 2. Results

### QuixBugs (in-domain) — unified engine
```
true positives: 12   false positives: 0   precision: 1.0000   recall: 0.3000
```
Unchanged from Phase 91 (the security exclusion is a no-op on this corpus).

### External holdout (out-of-domain) — unified engine
```
cases analyzed: 12
true positives: 2    false positives: 0   precision: 1.0000   recall: 0.1667
CASES WITH GROUNDED FINDINGS ON BUGGY
- transfer_bfs_empty_queue : semantic/bfs_queue_exhaustion, data_flow/unguarded_container_consumption
- transfer_gcd_no_rotate   : semantic/recursive_euclidean_state_not_rotated
FALSE POSITIVES ON FIXED: (none)
```

### Legacy comparison (labeled only, non-authoritative)
```
cases analyzed: 12   true positives: 2   false positives: 0   precision: 1.0000   recall: 0.1667
```
Engine and legacy agree exactly on the holdout (2 TP / 0 FP). The migration is
behavior-neutral at the verdict level.

### Acceptance gates
| Gate | Target | Result |
|---|---|---|
| `pytest builder_core/tests/ -q` | pass | **108 passed** ✅ |
| QuixBugs unified | ≥ 12 TP / 0 FP | **12 TP / 0 FP** ✅ |
| Holdout unified | 0 FP | **0 FP** ✅ |
| No new detector behavior | required | ✅ (only verdict routing) |
| No unrelated file changes | required | ✅ (4 files, all in scope) |

---

## 3. Tests added (`test_phase92a_holdout_on_engine.py`, 9)

- holdout engine evaluator runs and is **0 FP** with ≥2 TP (skips if corpus absent);
- missing-corpus handled gracefully;
- **pattern-only** finding does **not** count toward the verdict;
- **security** kind excluded from the algorithm-bug verdict;
- the three grounded kinds (`semantic`/`data_flow`/`value_flow`) **do** count;
- naive decision still includes pattern (comparison path intact);
- **holdout corpus is not modified** (sha1 snapshot before == after);
- **QuixBugs engine path unchanged** (12 TP / 0 FP / precision 1.0);
- synthetic BFS pair: buggy flagged, fixed not (engine grounded verdict).

---

## 4. Limitations / honest notes

- **Holdout recall stays 16.7%** (2/12). This phase does **not** expand recall by
  design; it only migrates the measurement. The 10 unflagged buggy cases
  (off-by-one, wrong-operator, mutable-default, etc.) are out of reach of the
  current grounded detectors and are the target of later, carefully-gated work.
- The `security` kind is excluded from the **algorithm-bug** verdict only; it
  remains fully active in the product and in its own security benchmark.
- The legacy `external_benchmark.py` / `benchmark.py` modules are retained solely
  for the labeled comparison; nothing new depends on them.

## 5. Next (Phase 92B — separate, not in this phase)

Add the fact-backed `inconsistent_return` detector under its own promote/quarantine
measurement gate, per the approved Phase 92 plan. Not started here.
