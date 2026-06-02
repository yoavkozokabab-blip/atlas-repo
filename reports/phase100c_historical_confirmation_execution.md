# Phase 100C — Historical Confirmation Execution

**Status:** Execution complete
**Date:** 2026-06-01
**Scope:** Phase 100A first batch (cases 21–30) via Phase 99D replay harness
**Constraints:** No detector or benchmark changes

---

## 1. Executive summary

| Item | Value |
|------|-------|
| Corpus | `data/historical_corpus/phase100c/manifest.json` |
| Cases materialized | 10 |
| Replay output | `reports/phase100c_run/` |
| Builder Core commit | `b2871fafeeacbe247117ef4a8d68027580429a68` |
| Elapsed | 0.1s |

This run executes the **first zero-setup slice** of the Phase 100A corpus:
3 in-repo return holdout pairs, 3 distractor pairs, and 4 curated hard negatives.
BugsInPy git-backed positives (cases 1–20) are deferred to a later materialization pass.

---

## 2. Tier distribution (buggy revision, case-level)

Each case receives one tier: the highest gate bucket present among target-rule findings.

| Tier | Cases |
|------|------:|
| `detected` | 0 |
| `strong_suspect` | 0 |
| `review_lead` | 0 |
| `refuted` | 10 |

### Aggregate finding counts (buggy / fixed)

| Bucket | Buggy findings | Fixed findings |
|--------|---------------:|---------------:|
| `detected` | 0 | 0 |
| `strong_suspect` | 0 | 0 |
| `review_lead` | 0 | 0 |
| `refuted` | 8 | 8 |

---

## 3. Confusion matrix (predicted vs expected tier)

Expected tiers are preregistered in `expected_packets.json` (Phase 100A §4.4).

| Predicted \ Expected | `detected` | `strong_suspect` | `review_lead` | `refuted` |
|---|---:|---:|---:|---:|
| `detected` | 0 | 0 | 0 | 0 |
| `strong_suspect` | 0 | 0 | 0 | 0 |
| `review_lead` | 0 | 0 | 0 | 0 |
| `refuted` | 0 | 0 | 3 | 7 |

**Tier accuracy:** 0.7

---

## 4. Confirmed precision and recall

| Metric | Value |
|--------|------:|
| True positives (predicted confirmed ∧ expected confirmed) | 0 |
| False positives (predicted confirmed ∧ expected ≠ confirmed) | 0 |
| False negatives (expected confirmed ∧ not predicted confirmed) | 0 |
| Predicted confirmed (buggy, case-level) | 0 |
| Expected confirmed | 0 |
| Confirmed-eligible positives in batch | 0 |
| **Confirmed precision** | None |
| **Confirmed recall** | None |
| Recall denominator | confirmed_eligible positives (none with expected confirmed in this batch) |
| Confirmed on fixed revision (must be 0) | 0 |
| Directional purity (buggy-only detected cases) | 0 |

**Interpretation:** This first batch contains **no confirmed-eligible positives**
(no bound trigger tests on return holdout pairs). Confirmed recall is therefore
not yet meaningful against the full 100A target (≥12 confirmed-eligible positives).
Precision is reported as `null` when no confirmed predictions occur.

---

## 5. Per-case results

| Case | Slice | Predicted | Expected | Match | Detected buggy | Detected fixed |
|------|-------|-----------|----------|:-----:|:--------------:|:--------------:|
| `hold_black_executor` | return_positive | `refuted` | `review_lead` | no | False | False |
| `hold_pysnooper_encoding` | return_positive | `refuted` | `review_lead` | no | False | False |
| `hold_tqdm_enumerate` | return_positive | `refuted` | `review_lead` | no | False | False |
| `dist_off_by_one` | distractor | `refuted` | `refuted` | yes | False | False |
| `dist_wrong_operator` | distractor | `refuted` | `refuted` | yes | False | False |
| `dist_missing_base_case` | distractor | `refuted` | `refuted` | yes | False | False |
| `neg_optional_by_design` | hard_negative | `refuted` | `refuted` | yes | False | False |
| `neg_dominating_guard` | hard_negative | `refuted` | `refuted` | yes | False | False |
| `neg_raise_only_exit` | hard_negative | `refuted` | `refuted` | yes | False | False |
| `neg_expected_negative_test` | hard_negative | `refuted` | `refuted` | yes | False | False |

---

## 6. Artifacts

| File | Description |
|------|-------------|
| `data/historical_corpus/phase100c/manifest.json` | Replay manifest |
| `data/historical_corpus/phase100c/expected_packets.json` | Preregistered expected tiers |
| `reports/phase100c_run/results.json` | Full replay output |
| `reports/phase100c_run/metrics.json` | 99D aggregate metrics |
| `reports/phase100c_run/evaluation.json` | Confusion matrix + precision/recall |
| `reports/phase100c_run/report.md` | 99D harness report |

---

## 7. Safety and neutrality

- Replay ran with `HISTORICAL_BUG_REPLAY_ENABLED` bypass via explicit enablement only.
- Confirmed-defect gate and evidence promotion were enabled in-session only (99D).
- No detector, benchmark, or finding-schema changes were made.
- QuixBugs / holdout benchmark oracles were not modified.

---

## 8. Next steps

1. Materialize BugsInPy git-backed cases (100A §3.1) with trigger tests for confirmed-eligible recall.
2. Dual-review expected packets before expanding the frozen corpus.
3. Re-run this script after corpus expansion; recall denominator requires ≥1 expected confirmed tier.

