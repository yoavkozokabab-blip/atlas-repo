# Phase 99A — Confirmed Defect Gate Infrastructure

**Status:** Infrastructure complete  
**Date:** 2026-05-31  
**Scope:** Gated classification only — no detector, benchmark, or promotion changes  
**Design input:** `reports/confirmed_defect_shortest_path.md` (Phase 99 design doc pending at execution time)

---

## Summary

Phase 99A adds a deterministic **confirmed-defect gate** that classifies `inconsistent_return` findings using evidence already attached by Phase 96C (`contract_review`) and Phase 97A (`verification_evidence`). The gate is **disabled by default** (`CONFIRMED_DEFECT_GATE_ENABLED = False`). When disabled, engine output is unchanged.

| Item | Value |
|------|-------|
| Module | `builder_core/bug_intelligence/confirmed_defect_gate.py` |
| Default flag | `CONFIRMED_DEFECT_GATE_ENABLED = False` |
| First rule target | `inconsistent_return` only |
| New finding field | `confirmed_defect_classification` (only when gate enabled) |
| Tests added | 18 (`test_phase99a_confirmed_defect_gate.py`) |
| Full suite | **355 passed** |

---

## Taxonomy

| Classification | Meaning |
|----------------|---------|
| `confirmed_defect` | Zero blockers, no surviving refuting witness ≥ E2, executable supporting proof present |
| `strong_suspect` | Partial supporting evidence and/or blockers prevent confirmation |
| `review_lead` | Default enriched lead without confirmation proof |
| `refuted` | Surviving refuting verification witness at E2+ |
| `unknown` | No verification overlay available |

---

## Inputs consumed (existing evidence only)

| Source | Fields used |
|--------|-------------|
| `contract_review` | `return_contract_evidence`, `conflicting_evidence` |
| `verification_evidence` | `atoms`, `blockers`, `refuting_evidence`, optional `impact_context` |
| Finding | `kind`, `confidence`, `rule` |

No new facts, detectors, or runtime execution were added.

---

## Confirmation rule (`inconsistent_return`)

A finding is **`confirmed_defect`** only when **all** of the following hold:

1. `blockers == []` (gate-derived blockers include verification blockers, weak/missing return contract, `kind=pattern`, non-high confidence, contract conflicts, and attached impact blockers)
2. No refuting atom at strength E2–E4
3. Executable supporting proof via **any** of:
   - `test_evidence` or `runtime_reproduction_evidence` at E2+ (polarity `supports`), or
   - `contract_violation_evidence` at E2+ **paired with** a feasible `path_feasibility_evidence` witness at E3+

Otherwise the gate assigns `refuted`, `strong_suspect`, `review_lead`, or `unknown`.

**Hard rule:** any blocker → never `confirmed_defect`.

---

## Wiring

Post-enrichment hook in `engine.analyze_source` (after contract + verification overlays):

```text
contract_enrichment.enrich_findings
  -> verification_evidence.enrich_findings
  -> confirmed_defect_gate.apply_gate   # no-op when disabled
```

When disabled, `apply_gate` returns the original finding list without copies or new fields.

When enabled (tests only by default), only `inconsistent_return` findings receive `confirmed_defect_classification`. The `confirmed_defect` tag is added **only** for `confirmed_defect` classifications.

---

## Test coverage

| Test | Validates |
|------|-----------|
| Gate disabled | `confirmed_defect_classification` absent; no `confirmed_defect` tags |
| Proven synthetic confirmed | Promoted `helper` + explicit contract + test/path proof → `confirmed_defect` |
| Visible guard blocks | Null-checking caller → `refuted`, not confirmed |
| Weak contract blocks | Missing explicit return contract → not confirmed |
| Unresolved path blocks | Quarantined `pattern` / no caller → not confirmed |
| Refuting evidence blocks | Optional return conflict → not confirmed |
| Phase 95E rejected analogues | Guard / weak contract / no-caller shapes → not confirmed |
| QuixBugs / holdout / grounded | Benchmark behavior unchanged with gate default off |

---

## Constraints honored

- No detector changes
- No benchmark behavior changes (QuixBugs 12/0, holdout FP 0 preserved)
- No default confirmed defects (`CONFIRMED_DEFECT_GATE_ENABLED = False`)
- No promotion (`EVIDENCE_PROMOTION_ENABLED` remains `False`)
- Infrastructure only — classification overlay, not product surfacing

---

## Next steps (out of scope for 99A)

1. Publish `reports/phase99_confirmed_defect_gate_design.md` and align thresholds if design diverges.
2. Apply 97D calibration to verification status logic before widening gate surfacing.
3. Extend gate targets beyond `inconsistent_return` only after labeled validation.
4. Enable gate in controlled pilots; keep external-alpha strict precision on the confirmed tier only.
