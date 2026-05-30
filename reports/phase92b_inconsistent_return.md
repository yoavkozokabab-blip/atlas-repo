# Phase 92B — Fact-Backed `inconsistent_return` (promote/quarantine gate)

**Status:** Implemented and measured. **Outcome: QUARANTINED.**
**Date:** 2026-05-30
**Scope:** One fact-backed detector behind a precision gate. No interprocedural
work, no call graph, no knowledge graph, no product/UX, no legacy-benchmark
changes.

---

## 0. TL;DR

- Added `return_summary` value-flow facts (`has_value_return`, `has_none_return`,
  `can_fall_through`) and a name-agnostic fact-backed `inconsistent_return`
  detector that fires only on a genuine missing-return.
- The promotion gate measured **1 false positive** (QuixBugs correct
  `next_permutation.py`). Per precision-first policy, the detector is
  **QUARANTINED**: `kind=pattern`, excluded from the benchmark verdict, kept as a
  diagnostic only.
- Parity preserved: **QuixBugs 12 TP / 0 FP**, **Holdout 2 TP / 0 FP**. Full
  suite: **122 passed**.

---

## 1. What was built

### `return_summary` facts (`valueflow.py` → `facts.py`)
Per function, computed from the AST/CFG that valueflow already builds:
- `has_value_return` — ≥1 explicit non-None value return.
- `has_none_return` — ≥1 explicit `return None` or bare `return`.
- `can_fall_through` — a conservative control-flow check: can control reach the
  end of the body without returning/raising? Handles `if/else` (both-return →
  no fall-through), `while True` without `break` (no fall-through), `with`,
  `try/finally`, and `match` with a wildcard. Generators are treated as
  non-falling-through. When uncertain it favors **not** firing.

### Fact-backed detector (`fact_detectors.py`, wired via `agents.FactLogicAgent`)
Fires iff `has_value_return and not has_none_return and can_fall_through`. This
is the genuine missing-return shape; it deliberately does **not** fire on
value-or-None / value-or-False contracts (those acknowledge a non-value return)
or on functions where every path returns. It reads facts only — **no function
name, variable name, or corpus-specific name** is used (a renamed copy produces
the identical result, test: `test_renamed_function_and_vars_same_result`).

---

## 2. Promotion gate — exact measurement

Ran the detector over every QuixBugs correct file and every holdout fixed file:

| Set | False positives | Files |
|---|---|---|
| QuixBugs correct (40) | **1** | `next_permutation.py` |
| Holdout fixed (12) | 0 | — |
| **Total** | **1** | → **QUARANTINE** |

(Informational: the detector also fires on the *buggy* `next_permutation.py`, so
it is **non-discriminative** on that pair — it fires on both versions.)

### Why `next_permutation` is a false positive
The correct `next_permutation` returns the rearranged permutation on the success
path and **intentionally falls through to an implicit `None`** when no next
permutation exists. The detector's assumption — "value return + no explicit
`None` ⇒ a forgotten return" — is wrong here: the implicit `None` is the intended
"no next permutation" signal. This is exactly the ambiguity the gate exists to
catch, and it is why the conservative `can_fall_through` analysis alone is not
sufficient to promote.

### Decision
`INCONSISTENT_RETURN_KIND = "pattern"` (quarantined). The finding is emitted as a
`pattern`-kind diagnostic (visible in `analyze-file`) but is **excluded from the
grounded benchmark verdict** (`BENCHMARK_VERDICT_KINDS = {semantic, data_flow,
value_flow}`), so it cannot add a false positive to QuixBugs or the holdout.

---

## 3. Results

| Benchmark | Metric | Result |
|---|---|---|
| QuixBugs (unified) | TP / FP | **12 / 0** (parity; quarantine prevents the non-discriminative 13th) |
| Holdout (unified) | TP / FP | **2 / 0** (parity) |
| Synthetic security smoke | — | unchanged |
| `pytest builder_core/tests/ -q` | — | **122 passed** |

Acceptance gates: ✅ suite passes · ✅ QuixBugs ≥ 12 TP / 0 FP · ✅ Holdout 0 FP ·
✅ no legacy-benchmark behavior changed · ✅ no unrelated files.

---

## 4. Tests added (`test_phase92b_inconsistent_return.py`, 14)

Intrinsic: genuine missing-return fires; value-or-False / value-or-None / bare
`return` / all-paths-return / `while True` (no fall-through) do **not** fire;
renamed function+vars give the same result; `return_summary` fact shape pinned.
Integration: engine dedup yields exactly one `inconsistent_return` (no
inflation); detector is `kind=pattern`; quarantined finding is excluded from the
grounded verdict. Gate: QuixBugs verdict 0 FP / 12 TP, holdout verdict 0 FP, and
a test that documents the `next_permutation` false-positive as the quarantine
reason.

---

## 5. Honest notes / deferred work

- **The detector is real but not yet safe to promote.** To promote later it must
  distinguish "forgot a return" from "implicit None is the intended sentinel."
  Candidate refinements (future phase): treat implicit-None-as-sentinel functions
  (e.g. the value-return is a search "found" case, or the fall-through returns the
  unchanged input) as non-bugs; or require a stronger signal (a value return on a
  branch whose negation has no handling at all).
- **Deferred ranker fix.** While validating, I found that `finding.rank()` dedupes
  *before* sorting, so on a `(file, line, rule)` collision it keeps the
  insertion-first finding rather than the strongest one. This is harmless while
  `inconsistent_return` is quarantined (both sources are `pattern`, both excluded
  from the verdict), so I **reverted** the change to keep this phase's surface
  minimal. When a fact-backed detector is eventually *promoted*, `rank()` must be
  changed to sort-then-dedupe so the promoted (higher-weight) finding survives the
  collision. Flagged here so it is not forgotten.

## 6. Next

Phase 93 (separate): interprocedural facts — out of scope here.
