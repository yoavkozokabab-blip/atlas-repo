# Phase 93B — Interprocedural Promotion of `inconsistent_return`

**Status:** Implemented and measured. **Outcome: PROMOTED (0 FP).**
**Date:** 2026-05-30
**Scope:** First gated consumer of Phase 93A interprocedural facts. Target:
`inconsistent_return` only. Precision-first; promote only if measurement proves 0 FP.

---

## 0. TL;DR

- `inconsistent_return` is now **promoted per finding** (kind `value_flow`,
  verdict-eligible) **only** when interprocedural evidence is unambiguous:
  ≥1 resolved same-file caller **dereferences** the result **and no** caller
  **null-checks** it. Mixed / no-deref / unresolved → quarantined (`pattern`).
- Measurement: **0 false positives** on QuixBugs correct files and holdout fixed
  files → promotion **ENABLED**.
- **QuixBugs 12 TP / 0 FP and Holdout 2 TP / 0 FP — unchanged** (0 promotions on
  these single-function corpora). The Phase 92B false positive (`next_permutation`)
  is now correctly **quarantined** by the interprocedural gate. Full suite:
  **155 passed**.

---

## 1. The promotion rule (per finding)

A function still triggers the Phase 92B intraprocedural shape
(`has_value_return ∧ ¬has_none_return ∧ can_fall_through`). The Phase 93A
call-site usage facts (`usage_by_callee`) then decide the kind:

| Interprocedural evidence | Decision |
|---|---|
| ≥1 resolved caller **dereferences**, **no** caller null-checks | **PROMOTE** → `value_flow` (verdict-eligible, confidence high) |
| any resolved caller **null-checks** (contract / mixed) | quarantine → `pattern` |
| caller only uses the value (no deref) | quarantine → `pattern` |
| no resolved caller (unresolved / not called in-file) | quarantine → `pattern` |

A global kill-switch `INTERPROC_PROMOTION_ENABLED` (set by this gate) can force
everything back to quarantine; it is currently `True`.

## 2. The required ranker fix (flagged since Phase 92B)

Promotion only takes effect if the promoted `value_flow` finding **survives
dedup** against the legacy `pattern/inconsistent_return` emitted at the same
`(file, line, rule)`. `finding.rank()` previously deduped *before* sorting, so it
kept the insertion-first (legacy) finding. Phase 93B applies the deferred fix:
**sort by weight first, then dedupe**, so the stronger promoted finding survives.
Verified by `test_dedup_keeps_promoted_over_legacy_pattern` (one finding, kind
`value_flow`). The change is a no-op for non-colliding findings and for ties
(stable sort preserves order).

## 3. Promotion-gate measurement (exact)

Promoted `value_flow/inconsistent_return` instances across the corpora:

| Set | Promoted | Interpretation |
|---|---|---|
| QuixBugs buggy (40) | **0** | no in-file deref-caller of a missing-return fn |
| QuixBugs correct (40) | **0** | **0 false positives** |
| Holdout buggy (12) | **0** | — |
| Holdout fixed (12) | **0** | **0 false positives** |
| **Total false positives** | **0** | → **PROMOTE (enabled)** |

The 16 QuixBugs correct files that would have false-fired under naive Phase 92B
promotion — **including `next_permutation.py`** — are now correctly **quarantined**
(`pattern`) because they are single-function algorithm files with no resolved
same-file caller that dereferences-without-null-checking. The interprocedural gate
turns the exact Phase 92B FP into a non-event.

## 4. Benchmark results

| Benchmark | Metric | Result |
|---|---|---|
| QuixBugs (unified) | TP / FP | **12 / 0** (unchanged) |
| Holdout (unified) | TP / FP | **2 / 0** (unchanged) |
| `pytest builder_core/tests/ -q` | — | **155 passed** |
| Security smoke | — | passed (static only) |

Acceptance: ✅ all tests pass · ✅ QuixBugs 0 FP · ✅ Holdout 0 FP · ✅ detector
promoted only because measurement proved 0 FP.

## 5. The mechanism is real (synthetic validation)

Because the corpora happen to contain **0** instances of the promotable shape,
the promotion logic is validated on synthetic cases (`test_phase93b_*`):
- caller derefs + no null-check → **promoted** (`value_flow`, high), enters verdict;
- caller null-checks → quarantined; mixed evidence → quarantined; no caller →
  quarantined; value-only use → quarantined; unresolved (attribute) caller →
  quarantined; kill-switch forces quarantine.

## 6. Honest notes

- **No recall movement on these benchmarks.** Promotion fires on 0 corpus files,
  so QuixBugs/holdout recall is unchanged. The deliverable is a *validated,
  0-FP-gated capability* plus the **elimination of the Phase 92B FP risk** — not a
  benchmark number. That is the correct precision-first outcome.
- **Coverage is intra-file only** (Phase 93A). A missing-return function whose
  only callers live in other files stays quarantined until cross-file resolution
  exists. This is a deliberate recall cost in exchange for never inventing an edge.
- **The gate is sticky.** If a future corpus or real repo surfaces a promoted FP,
  flip `INTERPROC_PROMOTION_ENABLED` to `False` and re-measure.

## 7. Tests

- `test_phase93b_inconsistent_return_promotion.py` (12): promotion on
  deref-without-null-check; quarantine on null-check / mixed / no-caller /
  value-only / unresolved; promoted finding is verdict-eligible; dedup keeps the
  promoted one; kill-switch; QuixBugs/holdout parity; `next_permutation` no longer
  promotes.
- Updated one Phase 92B test to the new gate (the removed
  `INCONSISTENT_RETURN_KIND` constant → `INTERPROC_PROMOTION_ENABLED` + quarantine
  behavior without interproc evidence).

## 8. Next

Cross-file interprocedural resolution (separate, gated) would let promotion reach
functions called only from other files — the main remaining recall lever for this
detector — under the same 0-FP gate.
