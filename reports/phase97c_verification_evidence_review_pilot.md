# Phase 97C — Verification Evidence Review Pilot

**Status:** Measurement complete  
**Date:** 2026-05-31  
**Scope:** Review quality measurement only — no detector, promotion, benchmark, or confirmed-bug changes  
**Inputs:** Phase 96D review process, Phase 97A verification evidence packets  
**Artifacts:** `reports/phase97c_pilot/`

---

## Summary

Phase 97C measured whether Phase 97A verification evidence improves human
review quality on top of Phase 96C contract-enriched packets for
**`inconsistent_return`** findings on **`local_jarvis`**. 

Corpus: **1053** findings 
(**1053** with verification overlay). 
Pilot sample: **20** cases (cohort: **phase96d_record_ids**).

**Baseline:** contract review only (Phase 96C shape).  
**Enriched:** contract review + verification evidence (Phase 97A).

**No claim of improved defect correctness** — enrichment can change advisory
labels when refuting verification evidence is visible (6/20 unchanged).

---

## Method

| Step | Detail |
|------|--------|
| Scan | Full `local_jarvis` via `engine.analyze_repository` (66.162s) |
| Sample | 20 cases; blocked 4, refuted 16, other 0 |
| Baseline | Reviewer packets with `contract_review`, no `verification_evidence` |
| Enriched | Same records with Phase 97A `verification_evidence` attached |
| Review | Structured single-reviewer pass (same rubric family as Phase 96D) |
| Tooling | `builder_core/scripts/phase97c_review_pilot.py` |

---

## Results

### Review confidence (1–4)

| | Mean |
|---|---:|
| Contract-only (baseline) | 4.0 |
| + Verification evidence | 4.0 |

Verification overlay adds proof-gap structure at an already-high contract baseline.
**Not** evidence of higher defect accuracy.

### Usefulness (0–4 scale from Phase 95D labels)

| | Mean | Useful advisory rate |
|---|---:|---:|
| Baseline | 2.65 | 85.0% |
| Enriched | 0.6 | 20.0% |

Label agreement: **6/20** identical.

Contract-only labels match the Phase 96D rubric. Verification-visible review
surfaces refuting path evidence, reclassifying many optional-return leads as misleading.

### Misleading rate (false_positive labels)

| | Rate | Count |
|---|---:|---:|
| Baseline | 10.0% | 2 |
| Enriched | 80.0% | 16 |

Refuting path evidence clarifies optional-return and blocked-path noise;
enrichment may increase false-positive clarity without changing underlying finding kind.

### Verification evidence usefulness

| Verdict | Count |
|---------|------:|
| helped | 20 |
| neutral | 0 |
| hurt | 0 |

Mean atoms per case: **1.0**. 
Status mix: blocked 4, 
refuted 16.

### Confirmation clarity (1–4)

| | Mean |
|---|---:|
| Contract-only | 3.0 |
| + Verification evidence | 4.0 |

Largest gain: explicit `missing_proof_obligations`, `blockers`, and verification
`why_not_confirmed` bullets make the proof gap legible beyond contract context alone.

### Review speed (estimated)

| Total minutes (20 cases) | 37.71 → 48.34 (**+10.63**) |

---

## Exemplar cases

- `actions/service_actions.py:21` (refuted): confirmation clarity 3→4, verification evidence **helped**
- `actions/website_actions.py:43` (refuted): confirmation clarity 3→4, verification evidence **helped**
- `alpha/session_log.py:40` (refuted): confirmation clarity 3→4, verification evidence **helped**

Full side-by-side packets: `reports/phase97c_pilot/packet_comparisons.md`

---

## Conclusions (evidence-bound)

1. **Confirmation clarity improved** — missing-proof and blocker sections raise clarity vs contract-only packets.
2. **Review confidence** (4.0 → 4.0) — contract baseline already high; verification adds proof-gap structure.
3. **Usefulness fell when refutation visible** (2.65 → 0.6) on 14 relabeled cases.
4. **Misleading rate rose with verification context** (10.0% → 80.0%) — refuted-path clarity, not detector promotion.
5. **Verification evidence helped orient review** (20/20 cases scored helped).
6. **Correctness not measured** — no confirmed-defect labels; cannot claim improved bug detection.

---

## Constraints honored

- No detector changes
- No promotion or benchmark changes
- No confirmed bug category output
- Measurement + audit/report tooling only

---

## Artifacts

| File | Purpose |
|------|---------|
| `phase97c_pilot/pilot_sample.json` | Sample cohort |
| `phase97c_pilot/baseline_packets.json` | Contract-only packets |
| `phase97c_pilot/enriched_packets.json` | Verification-enriched packets |
| `phase97c_pilot/pilot_reviews.json` | Structured review rows |
| `phase97c_pilot/metrics.json` | Aggregate metrics |
| `phase97c_pilot/packet_comparisons.md` | Side-by-side review text |
