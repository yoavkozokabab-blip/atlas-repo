# Phase 96D — Contract-Enriched Review Pilot

**Status:** Measurement complete  
**Date:** 2026-05-31  
**Scope:** Review quality measurement only — no detector, promotion, benchmark, or confirmed-bug changes  
**Inputs:** Phase 95C/95E review workflow, Phase 96C enriched packets  
**Artifacts:** `reports/phase96d_pilot/`

---

## Summary

Phase 96D measured whether Phase 96C contract-enriched packets improve human
review quality for **`inconsistent_return`** findings on **`local_jarvis`**.

Corpus: **1049** findings (all
`kind=pattern`, **0** verdict-eligible). Pilot sample: **20**
stratified cases reviewed as baseline packets (no `contract_review`) vs enriched
packets (Phase 96C).

**No claim of improved defect correctness** — labels were identical before/after
enrichment on every sampled case; enrichment changed review *process* signals, not
underlying finding disposition.

---

## Method

| Step | Detail |
|------|--------|
| Scan | Full `local_jarvis` via `engine.analyze_repository` (56.305s) |
| Sample | 20 stratified (return_only 6, return_and_caller 5, conflict_only 7, caller_only 2) |
| Baseline | Reviewer packets with `contract_review` stripped (pre-96C shape) |
| Enriched | Same records with Phase 96C `contract_review` attached |
| Review | Single structured operator pass; Phase 95D labels adapted for quarantined pattern leads |
| Tooling | `builder_core/scripts/phase96d_review_pilot.py` |

Phase 95C/95E did **not** include `inconsistent_return` (406 advisory findings
existed but 0 were verdict-eligible / in `review_sample.json`). This pilot uses
`local_jarvis` as the first human-review corpus for this rule.

---

## Results

### Review speed (estimated)

| Metric | Baseline | Enriched | Delta |
|--------|--------:|---------:|------:|
| Total minutes (20 cases) | 26.1 | 37.71 | **+11.61** |
| Mean minutes / case | 1.31 | 1.89 | +0.58 |

Enriched packets are longer (contract sections). Expect **modestly slower** reads;
no timed human stopwatch data in this pilot.

### Reviewer confidence (1–4)

| | Mean |
|---|---:|
| Baseline | 2.0 |
| Enriched | 3.65 |

Enrichment raised confidence slightly by surfacing explicit contract bullets and
`why_not_confirmed` text. **Not** evidence of higher defect-detection accuracy.

### False-positive / non-confirmation clarity (1–4)

| | Mean |
|---|---:|
| Baseline | 3.0 |
| Enriched | 4.0 |

Largest measured gain: baseline packets often omit an explicit “why not confirmed”
block for quarantined `pattern` findings; enriched packets always include one.

### Useful lead rate

| | Rate |
|---|---:|
| Baseline | 85.0% useful_advisory |
| Enriched | 85.0% useful_advisory |
| Label agreement | 20/20 identical |

Enrichment did **not** change advisory usefulness labels in this pass (same
underlying finding). Useful-lead rate reflects quarantined return-shape review
leads, not confirmed bugs.

### Understanding why not confirmed

| Understanding | Baseline | Enriched |
|---------------|--------:|---------:|
| yes | 0 | 20 |
| partial | 20 | 0 |
| no | 0 | 0 |

### Contract evidence helped / hurt / neutral

| Verdict | Count |
|---------|------:|
| helped | 13 |
| neutral | 7 |
| hurt | 0 |

No sampled case was scored **hurt**. Cases with return and/or caller evidence
were **helped** for orienting review; conflict-only cases were **neutral**
(conflicts restate quarantine without new proof).

---

## Missing evidence for actual confirmation

Aggregated across the 20-case sample (checklist items per case):

| Missing evidence | Cases mentioning |
|------------------|----------------:|
| interprocedural promotion gate evidence (currently not met) | 20 |
| runtime or test proof of reachable inconsistent return path | 20 |
| inferred_strong caller dereference or non-null use path | 13 |
| explicit non-optional return type hint on flagged function | 9 |

Confirmation would require promotion-grade interprocedural proof plus runtime/test
evidence — explicitly out of Phase 96C scope.

---

## Exemplar cases

- `actions/service_actions.py:21` (return_only): fp clarity 3→4, contract evidence **helped**
- `actions/website_actions.py:43` (conflict_only): fp clarity 3→4, contract evidence **neutral**
- `alpha/session_log.py:40` (return_only): fp clarity 3→4, contract evidence **helped**

Full side-by-side packets: `reports/phase96d_pilot/packet_comparisons.md`

---

## Conclusions (evidence-bound)

1. **Clarity of non-confirmation improved** — enriched `why_not_confirmed` +
   `conflicting_evidence` raised fp-clarity and full understanding counts vs baseline.
2. **Review speed likely slower** — more text per packet (+11.61 est. minutes total on sample).
3. **Useful lead rate unchanged** — enrichment does not alter finding kind or promotion; same advisory labels.
4. **Contract evidence mostly helped or neutral** — explicit return hints and strong caller paths orient review; conflict-only packets add quarantine context without new proof.
5. **Correctness not measured** — no `true_positive` / confirmed defect labels; cannot claim improved bug detection.

---

## Constraints honored

- No detector changes
- No promotion or benchmark changes
- No confirmed bug category output
- Measurement + audit/report tooling only (`phase96d_review_pilot.py`)

---

## Artifacts

| File | Purpose |
|------|---------|
| `phase96d_pilot/all_inconsistent_return.json` | Full scan export |
| `phase96d_pilot/pilot_sample.json` | Stratified sample |
| `phase96d_pilot/baseline_packets.json` | Pre-96C packets |
| `phase96d_pilot/enriched_packets.json` | Phase 96C packets |
| `phase96d_pilot/pilot_reviews.json` | Structured review rows |
| `phase96d_pilot/metrics.json` | Aggregate metrics |
| `phase96d_pilot/packet_comparisons.md` | Side-by-side review text |
