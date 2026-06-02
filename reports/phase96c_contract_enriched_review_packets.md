# Phase 96C — Contract-Enriched Review Packets

**Status:** Implemented  
**Date:** 2026-05-31  
**Scope:** Review output enrichment only — no confirmation, no promotion changes  
**Inputs:** Phase 96A contract facts, Phase 96B quality audit  
**Constraints:** no detector promotion, no benchmark behavior change, no confirmed defects

---

## Summary

Phase 96C attaches **contract review packets** to existing `inconsistent_return`
findings after ranking. Packets surface supporting evidence from **explicit type
hints** and **strong caller behavior** only, plus **conflicting signals** and
**why not confirmed** text. Every enriched finding is tagged **`review_lead_only`**.

Detectors, promotion gates (Phase 93B), and benchmark verdicts are **unchanged**.

---

## Implementation

| Component | Location |
|-----------|----------|
| Enrichment logic | `builder_core/bug_intelligence/contract_enrichment.py` |
| Finding field | `Finding.contract_review` + `to_dict()` export |
| Engine wiring | `engine.analyze_source()` post-ranker |
| CLI formatter | `EvidenceFormatterAgent` — per-finding contract lines |
| Review packets | `harness.export_reviewer_packets()` + `review_tool.format_candidate()` |

Feature flag: `contract_enrichment.CONTRACT_ENRICHMENT_ENABLED = True`

---

## Packet schema

Attached on `inconsistent_return` findings only:

```text
contract_review:
  review_packet_status: review_lead_only
  function_qualname: <call-graph qualname>
  return_contract_evidence:   # explicit type_hint only
    - obligation, confidence, sources, subject
  caller_behavior_evidence:   # inferred_strong caller_behavior only
    - obligation, confidence, sources, subject
  conflicting_evidence:
    - optional return signals (type_hint / docstring / weak caller)
    - interprocedural_gate_not_met when kind=pattern
  why_not_confirmed:
    - static bullets (no confirmation evaluators; excluded sources; etc.)
```

Tags: `review_lead_only` added; `confirmed_bug` / `confirmed_defect` explicitly excluded.

---

## Scope boundaries (hard)

| Allowed in packet | Excluded from packet / promotion |
|-------------------|----------------------------------|
| `type_hint` explicit return contracts | `callee_behavior` as proof |
| `caller_behavior` **inferred_strong** | `guard` facts as proof |
| Conflicting optional / weak caller signals | Docstring Returns used for promotion |
| `why_not_confirmed` static text | Confirmed Bug output |

Contract facts **do not** change `kind`, `confidence`, or promotion eligibility.

---

## Before / after (review output)

### Before (Phase 96A)

`inconsistent_return` findings included:

- title, explanation, source_facts (return_summary + interproc summary)
- no structured contract evidence
- no explicit “why not confirmed” block

### After (Phase 96C)

Same finding counts and kinds, plus on each `inconsistent_return`:

| Field | Example content |
|-------|-----------------|
| `return_contract_evidence` | `helper → return.non_none` from `-> str` |
| `caller_behavior_evidence` | `helper → return.non_none` from deref caller (strong) |
| `conflicting_evidence` | `return.optional` from null-checking caller; gate not met |
| `why_not_confirmed` | “review lead only — not a confirmed defect” |

### `local_jarvis` spot check (`brain/router.py`)

Engine analysis produces `inconsistent_return` findings with `contract_review`
attached when the shape fires. Enriched packets include qualname resolution from
the Phase 93A call graph and contract facts from Phase 96A.

---

## Verification

| Criterion | Result |
|-----------|--------|
| Full suite | **317 passed** |
| Phase 96C tests | **14 passed** |
| Promotion unchanged | `kind` / `confidence` same as Phase 93B |
| Grounded verdict unchanged | Quarantined `inconsistent_return` still excluded |
| QuixBugs (mini + full when present) | 12 TP / 0 FP unchanged |
| Holdout (when present) | 2 TP / 0 FP unchanged |
| No confirmed defect labels | Verified in tests |
| Review packets export `contract_review` | Verified via harness test |

---

## Regression tests

**File:** `builder_core/tests/test_phase96c_contract_enriched_review_packets.py`

| Test | Asserts |
|------|---------|
| `test_inconsistent_return_gets_contract_review_packet` | packet + `review_lead_only` tag |
| `test_return_contract_evidence_explicit_type_hint_only` | type_hint explicit only |
| `test_caller_behavior_evidence_strong_only` | inferred_strong caller only |
| `test_conflicting_weak_caller_and_quarantine` | weak caller + pattern gate conflict |
| `test_why_not_confirmed_present` | static blockers listed |
| `test_promotion_unchanged_with_enrichment` | still `value_flow` when promoted |
| `test_other_rules_not_enriched` | non-IR findings untouched |
| `test_finding_record_exports_contract_review` | harness record export |
| `test_reviewer_packet_includes_contract_review` | JSON packets |
| `test_grounded_verdict_unchanged` | benchmark grounding |
| Benchmark parity | mini QuixBugs, full QuixBugs, holdout |

---

## First consumer alignment (Phase 96B recommendation)

Phase 96B recommended **`inconsistent_return` enrichment only** before any
confirmation logic. Phase 96C delivers exactly that:

- Uses audit-safe sources only in evidence sections
- Surfaces conflicts instead of hiding them
- States explicitly why confirmation did not occur

**Next (not in 96C):** confirmation evaluators; guard-aware refutation for
`null_dereference`; extractor fixes for docstring Returns and callee_behavior noise.

---

## Reproducibility

```powershell
cd local_jarvis
py -3 -m pytest builder_core/tests/test_phase96c_contract_enriched_review_packets.py -q
py -3 -c "import sys; sys.path.insert(0,'.'); from builder_core.bug_intelligence import engine; r=engine.analyze_source(open('brain/router.py',encoding='utf-8').read(),'brain/router.py'); f=next(x for x in r.findings if x.rule=='inconsistent_return'); print(f.contract_review)"
```

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Attach explicit contract facts to `inconsistent_return` | Done |
| Show return / caller / conflicting / why not confirmed | Done |
| Never promote from contract facts | Done |
| Mark review leads only | Done |
| Exclude callee_behavior, guard proof, docstring promotion | Done |
| No Confirmed Bug output | Done |
| Tests / QuixBugs / Holdout unchanged | Verified |
| Report | Done |
