# Phase 99F — Confirmed Defect Gate Remediation

**Status:** Complete  
**Date:** 2026-05-28  
**Scope:** Bring Phase 99A into full compliance with `phase99_confirmed_defect_gate_design.md` per `phase99e_design_compliance_audit.md` remediation plan R1–R5  
**Constraints honored:** No new detectors, no benchmark changes, default-off flags preserved

---

## 1. Executive summary

Phase 99F remediates every blocking mismatch identified in the Phase 99E audit. The confirmed-defect gate now implements the design’s **C1–C6 confirmation predicate**, **status-derived four-tier taxonomy**, **§2 confirmation bundle**, **97D refutation calibration**, **C4 impact consequence hook**, and **§6 enablement governance** (automated subset + shadow mode).

| Flag | Default | Role |
|------|:-------:|------|
| `CONFIRMED_DEFECT_GATE_ENABLED` | `False` | Master gate switch |
| `EVIDENCE_PROMOTION_ENABLED` | `False` | Required for C6; both must be True for Confirmed |
| `CONFIRMED_DEFECT_SHADOW_MODE` | `False` | Compute Confirmed without surfacing tag |

**Verdict:** With default flags, behavior is unchanged (371 tests pass). With both enablement flags on, Confirmed requires promotion-candidate status, empty proof obligations, test/runtime witness, resolved impact, complete bundle, and passing design blockers.

---

## 2. Remediation mapping (R1–R5)

### R1 — Align confirmation predicate (99E-R1)

**Files:** `confirmed_defect_gate.py`, `verification_evidence.py`, `test_phase99a_confirmed_defect_gate.py`

| Requirement | Implementation |
|-------------|----------------|
| **C1** promotion_candidate | `_evaluate_criteria`: requires `promotion_candidate_basis` **and** `status == promotion_candidate`. Overlay exposes `promotion_candidate_basis` via new `promotion_candidate_basis()` helper. |
| **C3** test/runtime only | `_has_executable_witness()` accepts only `EVIDENCE_TEST` or `EVIDENCE_RUNTIME` at E2+ supports. Violation+path alone cannot confirm. |
| **C5** empty obligations | C5 fails when `missing_proof_obligations` is non-empty. |
| **C6** double gate | C6 requires `CONFIRMED_DEFECT_GATE_ENABLED and EVIDENCE_PROMOTION_ENABLED`. Gate-on without promotion never confirms (`test_gate_on_without_promotion_never_confirms`). |
| **C4** impact hook | `_build_impact_context()` in `verification_evidence.py` populates `impact_context` from existing interprocedural caller-usage facts. Gate checks `impact_context.resolved` with no impact blockers. |

**Audit rows closed:** D-03, D-05, D-07, D-08, D-09 (Confirmed ⊂ promotion_candidate).

---

### R2 — Taxonomy and bundle (99E-R2)

**Files:** `confirmed_defect_gate.py`

| Requirement | Implementation |
|-------------|----------------|
| Status-first taxonomy | `_tier_from_overlay()` maps refuted/blocked/unknown → `refuted`; promotion basis → `strong_suspect`; else `review_lead`. Confirmed upgrade only when C1–C6 pass. |
| Four tiers | Removed `CLASS_UNKNOWN`; `CLASSIFICATIONS` = confirmed, strong_suspect, review_lead, refuted. Missing overlay → `refuted`. |
| §2 confirmation bundle | `_build_confirmation_bundle()` emits finding, expected_contract, feasible_path, observable_consequence, executable_witness, refuting_evidence_considered, gate_version. |
| Auto-demote | Incomplete bundle demotes to `strong_suspect` with `confirmation_bundle_incomplete` failure. |
| Tag surfacing | `confirmed_defect` tag only when `classification == confirmed_defect` **and** `surfaced == True`. |

**Audit rows closed:** D-10, D-11, D-12 (partial → full), D-19, D-29.

**99D harness:** `_output_bucket()` maps missing/unknown classifications to `refuted` (design §4 collapse).

---

### R3 — Calibration and blockers (99E-R3)

**Files:** `confirmed_defect_gate.py`

| Requirement | Implementation |
|-------------|----------------|
| 97D calibration | `_is_calibrated_refuting_atom()` ignores `path.no_implicit_none_exit` on `kind=pattern` findings before E2+ refute demotion. |
| Blockers §3.1–3.6 | `_design_blockers()`: unresolved_critical_edge, weak_contract_only, path_feasibility_partial, no_observable_consequence, refuting_evidence. |
| Extra blockers removed | Prior 99A blockers (`kind_pattern_quarantined`, `finding_confidence_not_high`, contract_review heuristics) removed from confirmation path. |

**Audit rows closed:** D-04 (partial → full), D-13–D-18, D-28 (partial).

---

### R4 — Enablement governance (99E-R4)

**Files:** `confirmed_defect_gate.py`, `historical_bug_replay/harness.py`

| Requirement | Implementation |
|-------------|----------------|
| §6.1 QuixBugs correct | `evaluate_enablement_gates()` counts surfaced Confirmed on correct variants; gate passes at 0. |
| §6.2 holdout fixed | Same on holdout `fixed.py` variants. |
| §6.3 95E rejected | Manual gate stub (`passed: None`) — full corpus replay deferred. |
| §6.4 98A human review | Manual gate stub. |
| Shadow mode | `CONFIRMED_DEFECT_SHADOW_MODE`: computes Confirmed + bundle but `surfaced=False`, no tag. |
| Replay harness | `_confirmation_pipeline_enabled()` enables **both** gate and promotion flags during 99D measurement. |

**Audit rows closed:** D-21–D-24 (6.1–6.2 automated; 6.3–6.4 documented manual), D-25 (shadow mode).

---

### R5 — Schema policy (99E-R5)

**Decision:** Keep `Finding.confirmed_defect_classification` as an **internal audit/export overlay** (schema_version 2). It does not change finding kind, promotion, or detector output. The product-facing Confirmed signal is the optional `confirmed_defect` tag, gated by `surfaced`.

**Audit row:** D-20 documented as intentional export-only overlay; not a finding-kind change.

---

## 3. Mandatory requirements checklist

| User requirement | Status | Evidence |
|------------------|:------:|----------|
| promotion_candidate requirement | ✅ | C1 + `promotion_candidate_basis` on overlay |
| EVIDENCE_PROMOTION_ENABLED requirement | ✅ | C6 double gate |
| mandatory test/runtime witness | ✅ | C3 `_has_executable_witness` |
| impact consequence requirement | ✅ | C4 + `_build_impact_context` |
| missing_proof_obligations requirement | ✅ | C5 empty obligations |
| confirmation bundle emission | ✅ | `_build_confirmation_bundle` on Confirmed path |

---

## 4. Files changed

| File | Change |
|------|--------|
| `builder_core/bug_intelligence/confirmed_defect_gate.py` | Full rewrite: C1–C6, bundle, taxonomy, calibration, shadow mode, `evaluate_enablement_gates()` |
| `builder_core/bug_intelligence/verification_evidence.py` | `promotion_candidate_basis()`, `_build_impact_context()`, overlay fields populated |
| `builder_core/historical_bug_replay/harness.py` | Both flags during replay; four-tier bucket map; VE import |
| `builder_core/tests/test_phase99a_confirmed_defect_gate.py` | Rewritten for design compliance |
| `builder_core/tests/test_phase99d_historical_bug_replay.py` | Restore both flags after analyze; syntax fix parity |

**Not changed:** Detectors, `engine_benchmark` scoring, QuixBugs/holdout oracle expectations.

---

## 5. Test evidence

```
371 passed in ~19s
```

Key behavioral oracles:

| Test | Asserts |
|------|---------|
| `test_gate_disabled_preserves_current_behavior` | Default-off neutral |
| `test_gate_on_without_promotion_never_confirms` | C6 blocks Confirmed |
| `test_proven_synthetic_confirmed` | Both flags + full C1–C6 + bundle + tag |
| `test_confirmed_emits_complete_bundle` | §2 bundle sections present |
| `test_shadow_mode_computes_without_surfacing` | Shadow mode |
| `test_promotion_candidate_without_test_is_strong_suspect` | C3 without test → strong_suspect |
| `test_unresolved_consequence_not_confirmed` | C4 blocker |
| `test_visible_guard_blocks_confirmation` | Refuted on guard |
| `test_phase95e_rejected_shapes_do_not_confirm` | 95E analogue shapes |
| `test_enablement_gates_unavailable_when_flags_off` | §6 runner gated |
| `test_quixbugs_unchanged` / `test_holdout_unchanged` | Benchmark neutrality |

---

## 6. Residual / manual gates

These remain **manual** per design §6.3–6.4 and are stubbed in `evaluate_enablement_gates()`:

1. **Phase 95E rejected corpus** — labeled replay with adjudicated outcomes  
2. **Phase 98A human review** — blinded review before production enablement  

Recommended enablement sequence (unchanged from design §7):

1. Pass automated §6.1–6.2 with both flags on  
2. Run 95E + 98A manual gates  
3. Enable shadow mode → validate bundles in logs  
4. Enable production surfacing (`CONFIRMED_DEFECT_SHADOW_MODE = False`)

---

## 7. Conclusion

Phase 99F closes all blocking audit items from Phase 99E R1–R5. The gate is now design-compliant: **Confirmed ⟺ C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5 ∧ C6 ∧ complete bundle ∧ no design blockers**, with Confirmed impossible under default flags (C6). No detector or benchmark regressions were introduced.

---

## 8. References

| Document | Role |
|----------|------|
| `reports/phase99_confirmed_defect_gate_design.md` | Approved design baseline |
| `reports/phase99e_design_compliance_audit.md` | Audit + R1–R5 plan |
| `reports/phase99a_confirmed_defect_gate_infrastructure.md` | Pre-remediation 99A report |
| `builder_core/bug_intelligence/confirmed_defect_gate.py` | Remediated implementation |
| `builder_core/tests/test_phase99a_confirmed_defect_gate.py` | Design-compliant test oracle |
