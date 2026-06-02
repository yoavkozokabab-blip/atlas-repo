# Phase 99E — Design Compliance Audit

**Status:** Audit complete (read-only)  
**Date:** 2026-05-31  
**Scope:** Compare approved Phase 99 design vs Phase 99A implementation  
**Artifacts reviewed:**
- `reports/phase99_confirmed_defect_gate_design.md` (design)
- `builder_core/bug_intelligence/confirmed_defect_gate.py` (implementation)
- Supporting context: `verification_evidence.py`, `test_phase99a_confirmed_defect_gate.py`, `phase99a_confirmed_defect_gate_infrastructure.md`

**Verdict:** Phase 99A delivers a **useful, default-off classification overlay**, but it is **not design-compliant** as written. The implementation follows the earlier `confirmed_defect_shortest_path.md` confirmation OR-logic more closely than the approved Phase 99 design’s **promotion-candidate ⊂ confirmed** model. Several safety properties hold; several design clauses are missing or inverted.

---

## 1. Executive summary

| Area | Design intent | Implementation reality | Compliance |
|------|---------------|------------------------|:----------:|
| Default-off | `CONFIRMED_DEFECT_GATE_ENABLED = False` | Same | **Match** |
| Rule scope | `inconsistent_return` only | Same | **Match** |
| Confirmation logic | C1–C6 over existing 97A atoms + 94B impact | Custom blocker/heuristic function; bypasses C1/C5/C6; no C4 | **Mismatch** |
| Executable witness | Test or runtime **required** for Confirmed (§2.5, C3) | Test/runtime **or** contract-violation + feasible path | **Mismatch** |
| Double gate | Requires `EVIDENCE_PROMOTION_ENABLED == True` (C6) | Only checks gate flag; promotion always False | **Mismatch** |
| Taxonomy | 4 tiers mapped from 97A status | 5 tiers; status-agnostic heuristics | **Partial** |
| Impact / consequence | C4 + bundle §2.6 required | `impact_context` always `None`; never evaluated | **Missing** |
| 97D calibration | Refutation rules for weak witnesses (§3, §8) | Raw refuting atoms at E2+ | **Missing** |
| Validation gates §6 | 6.1–6.4 before enable | Not enforced in module; partial test analogues only | **Missing** |
| Schema | Output tier only; no finding schema change (§7, §9) | Adds `confirmed_defect_classification` field + tag | **Divergence** |

**Bottom line:** 99A is acceptable as **Phase 99A infrastructure scaffolding** but must not be treated as the approved Phase 99 gate without remediation. Enabling the flag today would **not** enforce the design’s Confirmed Defect contract and could **over-confirm** relative to design (no promotion prerequisite, no impact, alternate executable path).

---

## 2. Exact mismatch table

| ID | Design requirement | Design reference | Implementation behavior | Match |
|----|-------------------|------------------|-------------------------|:-----:|
| D-01 | Default-off flag `CONFIRMED_DEFECT_GATE_ENABLED = False` | §7 | `CONFIRMED_DEFECT_GATE_ENABLED = False`; `apply_gate` no-op when False | Yes |
| D-02 | Evaluate `inconsistent_return` only; other rules untouched | §5 | `classify_inconsistent_return` returns `None` for other rules; `apply_gate` passes them through | Yes |
| D-03 | **C1:** overlay `status == promotion_candidate` | §1 C1 | Never reads `verification_evidence.status`; confirms without promotion_candidate | **No** |
| D-04 | **C2:** no E2+ refuting atoms (97D-calibrated) | §1 C2, §3.2/3.6, §8 | Checks E2+ refutes; no 97D pattern-kind calibration | **Partial** |
| D-05 | **C3:** executable witness = test **or** runtime only | §1 C3, §2.5 | `_has_executable_support` also accepts violation+feasible path pair | **No** |
| D-06 | **C4:** resolved consuming context from 94B impact | §1 C4, §2.6, §8 | No impact analysis run; only reads `impact_context.blockers` if pre-set (never is) | **No** |
| D-07 | **C5:** `missing_proof_obligations == ∅` | §1 C5 | Does not read `verification_evidence.missing_proof_obligations` | **No** |
| D-08 | **C6:** requires `EVIDENCE_PROMOTION_ENABLED == True` **and** gate flag | §1 C6, §7 | Ignores `EVIDENCE_PROMOTION_ENABLED` (always False in 97A) | **No** |
| D-09 | Confirmed ⊂ promotion_candidate ⊂ all findings | §1 key property | Can classify `confirmed_defect` when overlay status is `enriched_lead` | **No** |
| D-10 | **Strong Suspect** = promotion_candidate minus executable/consequence | §4 | Assigned when blockers + partial support; not tied to promotion_candidate | **No** |
| D-11 | **Review Lead** = enriched_lead basis | §4 | Default fallback heuristic; not tied to overlay status | **Partial** |
| D-12 | **Refuted** = refuted ∪ blocked ∪ unknown (97A) | §4 | Refuted if E2+ refute; else blockers → strong_suspect/review_lead; separate `unknown` tier | **Partial** |
| D-13 | Blocker 3.1 unresolved critical edge | §3.1 | Partially via VE blockers (`interprocedural_promotion_gate_not_met`); no impact degraded edge | **Partial** |
| D-14 | Blocker 3.2 visible guard → Refuted | §3.2 | Refuted on E2+ refuting path atoms | Yes |
| D-15 | Blocker 3.3 weak contract only → Review Lead | §3.3 | Adds `weak_or_missing_return_contract` blocker; tier depends on partial support | **Partial** |
| D-16 | Blocker 3.4 partial path → Strong Suspect / Review Lead | §3.4 | Not explicit; partial path may still confirm if test present | **Partial** |
| D-17 | Blocker 3.5 no consequence → Review Lead | §3.5 | Not implemented (no impact) | **No** |
| D-18 | Blocker 3.6 refuting evidence → Refuted | §3.6 | Same as D-04 refute branch | Yes |
| D-19 | Complete evidence bundle on every Confirmed candidate | §2, §10.2 | Gate packet has classification/blockers/atom IDs only; no bundle sections | **No** |
| D-20 | No finding schema change | §7, §9 | Adds `Finding.confirmed_defect_classification` + `confirmed_defect` tag | **No** |
| D-21 | Validation gate 6.1 QuixBugs correct 0 Confirmed | §6.1 | Not enforced; benchmark tests run with gate off | N/A (not run) |
| D-22 | Validation gate 6.2 holdout fixed 0 Confirmed | §6.2 | Not enforced | N/A |
| D-23 | Validation gate 6.3 95E rejected 0 Confirmed | §6.3 | Analogue fixtures in tests only; not full 95E set | **Partial** |
| D-24 | Validation gate 6.4 human review before enable | §6.4 | Not implemented | **No** |
| D-25 | Staged enablement: shadow → review → on | §7 | Binary on/off only | **No** |
| D-26 | Rollback behavior-neutral when off | §7 | `apply_gate` returns original list unchanged | Yes |
| D-27 | Never confirm if any blocker | §3 intro (implicit in C1) | Explicit: `blockers` non-empty prevents `confirmed_defect` | Yes |
| D-28 | Consumes contract_review | §2 (via atoms); design emphasizes 97A atoms | Uses `return_contract_evidence`, `conflicting_evidence` as extra blockers | **Partial** |
| D-29 | Four mutually exclusive tiers | §4 | Five tiers (`unknown` added) | **Partial** |
| D-30 | Expected 0 Confirmed on test-less corpora | §0, §6 | Likely true in practice, but not guaranteed by C1/C6 logic | **Partial** |

---

## 3. Missing requirements

Requirements present in design but **not implemented** in `confirmed_defect_gate.py`:

1. **C1 / promotion_candidate prerequisite** — Confirmation never requires overlay status `promotion_candidate`. With current 97A settings, `promotion_candidate` is never emitted anyway (`EVIDENCE_PROMOTION_ENABLED = False`), so design-compliant Confirmed would be **impossible** until promotion is enabled; 99A sidesteps this entirely.

2. **C6 double gate** — No check of `EVIDENCE_PROMOTION_ENABLED`. Design requires both flags True for any Confirmed output.

3. **C5 missing_proof_obligations** — Overlay always includes obligations such as `"evidence promotion gate disabled"` and `"repository test or runtime reproduction"` when promotion is off; design requires empty obligations for Confirmed.

4. **C4 / §2.6 impact scope** — No integration with Phase 94B impact analysis; `verification_evidence.impact_context` is hard-coded `None` in 97A. Observable consequence is never resolved.

5. **§2 evidence bundle** — Confirmed candidates do not carry `expected_contract`, `feasible_path`, `observable_consequence`, `runtime_or_test_evidence`, etc. (Phase 99B packet shape).

6. **§6 validation gates** — No built-in enforcement of 6.1–6.4 before enablement; no shadow mode.

7. **§8 97D calibration dependency** — No special handling for over-refuting `path.no_implicit_none_exit` on `kind=pattern` findings.

8. **§4 status-derived taxonomy** — Classification does not map from 97A `status` (`enriched_lead`, `blocked`, etc.).

---

## 4. Weaker implementations

Places where implementation is **less strict or less complete** than design:

| Item | Risk |
|------|------|
| Confirms without `promotion_candidate` (D-03, D-09) | Can upgrade findings the overlay explicitly did not promote |
| Confirms without `EVIDENCE_PROMOTION_ENABLED` (D-08) | Violates designed two-switch safety model |
| Accepts violation+path as “executable” (D-05) | Confirms without test/runtime witness design requires |
| Ignores `missing_proof_obligations` (D-07) | Confirms while overlay lists explicit missing proof |
| No impact / consequence check (D-06, D-17) | Confirms without proving observable breakage at a consumer |
| No bundle attachment (D-19) | Product cannot ship design’s minimal defect packet |
| Taxonomy not status-aligned (D-10–D-12) | Tier labels may mislead reviewers vs overlay semantics |
| No 97D refutation calibration (D-04) | More refuted than necessary (safe) but tier mapping wrong vs design |
| No enablement validation (D-21–D-24) | Flag can be turned on without oracle passage |

---

## 5. Stronger implementations

Places where implementation is **more conservative or more explicit** than design (not necessarily wrong for safety, but divergent):

| Item | Effect |
|------|--------|
| Extra blockers: `kind_pattern_quarantined`, `finding_confidence_not_high` | Blocks confirmation on quarantined/low-confidence findings design might still tier via overlay status |
| Extra blockers from `contract_review.conflicting_evidence` | Demotes on contract conflict beyond atom-only rules |
| Extra blocker `weak_or_missing_return_contract` from 96C packet | Stricter than design C1 alone (uses enrichment packet, not only violation atom) |
| Hard rule: any blocker → never confirm (D-27) | Aligns with design spirit; explicit in code |
| Structured `confirmed_defect_classification` packet + atom ID lists | Richer audit trail than design minimum (but not the full §2 bundle) |
| Explicit `unknown` tier when overlay missing | Clearer than folding into Refuted/Not actionable |
| Tests for guard / weak contract / unresolved path / 95E analogues | Partial safety coverage design assigns to §6.3 |

---

## 6. Behavioral divergences

### 6.1 Confirmed path: design vs tests

**Design:** `Confirmed ⟺ C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5 ∧ C6` — with today’s flags, **no finding should ever be Confirmed** in production (C6 fails).

**Implementation + tests:** `test_proven_synthetic_confirmed` passes with only `CONFIRMED_DEFECT_GATE_ENABLED = True`, proving a synthetic fixture reaches `confirmed_defect` while `EVIDENCE_PROMOTION_ENABLED` remains False and overlay status remains `enriched_lead`.

This is the **largest behavioral divergence**: 99A tests validate a **different confirmation contract** than the approved design.

### 6.2 Executable witness definition

| Source | Rule |
|--------|------|
| Design §2.5 / C3 | Test or runtime **required**; assertion-only → Strong Suspect |
| 99A `_has_executable_support` | Test/runtime **or** contract_violation (E2+) + feasible path (E3+) |

A finding with static violation+path but **no** bound failing test can be **Confirmed** in 99A but **Strong Suspect** in design.

### 6.3 Tier assignment order

Implementation priority:

```text
refuting (E2+) → refuted
else blockers → strong_suspect (if partial support) else review_lead
else executable support → confirmed_defect
else partial support → strong_suspect
else review_lead
```

Design priority is **status-first**:

```text
promotion_candidate + executable + impact → confirmed
promotion_candidate − executable/consequence → strong_suspect
enriched_lead → review_lead
refuted/blocked/unknown → refuted/not actionable
```

Findings with overlay `status: blocked` but no E2+ refute may classify as `strong_suspect` or `review_lead` in 99A instead of design’s Refuted tier.

### 6.4 Schema and product surface

Design §7: tier is an **output classification**, not a finding schema change.

99A adds:

- `Finding.confirmed_defect_classification: Optional[Dict]`
- `confirmed_defect` tag on confirmed findings

This is a **persistent schema extension** when the gate is enabled.

### 6.5 Interaction with 97A overlay today

Because `EVIDENCE_PROMOTION_ENABLED = False`:

- Overlay never exposes `promotion_candidate` to consumers
- `missing_proof_obligations` is never empty
- Design-compliant Confirmed count is **zero by construction**

99A reimplements a parallel confirmation path that **does not require** the overlay’s promotion machinery, defeating the designed layering `Confirmed ⊂ promotion_candidate`.

---

## 7. Risk assessment

| Risk | Severity | Likelihood | Description |
|------|:--------:|:----------:|-------------|
| **Over-confirmation vs design** | **High** | Medium (if flag enabled) | Confirms without promotion, impact, or mandatory test/runtime |
| **False product claim** | **High** | Medium | Surfacing `confirmed_defect` tag implies design §2 bundle; packet incomplete |
| **Tier label confusion** | Medium | High | `strong_suspect` / `review_lead` not aligned with 97A status semantics |
| **Enablement without oracles** | Medium | Medium | No §6 gates block turning flag on in production |
| **Under-refutation (97D)** | Low | Low | Uncalibrated refutes → more `refuted`, fewer Confirmed (conservative) |
| **Extra blockers** | Low | Medium | May under-confirm vs design Strong Suspect path (conservative) |
| **Default-off regression** | Low | Very low | Off path verified by tests; benchmarks unchanged |
| **Detector/benchmark drift** | Low | Very low | Gate is downstream; no detector edits in 99A |

**Overall risk if `CONFIRMED_DEFECT_GATE_ENABLED` is enabled without remediation:** **High** — confirmed tier would not mean what Phase 99 design defines.

**Overall risk with flag left False (current default):** **Low** — behavior-neutral; audit concern is **latent misalignment** when enablement is attempted.

---

## 8. Remediation plan

Recommended sequence (design-compliant; no work performed in 99E):

### Phase 99E-R1 — Align confirmation predicate (blocking)

1. Implement **C1–C6 literally** in `classify_inconsistent_return`:
   - Require `verification_evidence.status == promotion_candidate`
   - Require `EVIDENCE_PROMOTION_ENABLED and CONFIRMED_DEFECT_GATE_ENABLED`
   - Require `missing_proof_obligations == []`
   - Require C3 test/runtime atom (remove violation+path as Confirmed shortcut, or reclassify that path as Strong Suspect only)
2. Add **C4 impact hook**: populate `verification_evidence.impact_context` from 94B (read-only) or fail C4 until wired.
3. Update tests: synthetic Confirmed must enable **both** flags and satisfy empty obligations; expect **0 Confirmed** with promotion off.

### Phase 99E-R2 — Taxonomy and bundle (blocking for product)

4. Map tiers from 97A `status` first, then apply Confirmed upgrade only on promotion_candidate branch (§4).
5. Emit **§2 / 99B proof packet** fields on every `confirmed_defect` candidate; auto-demote if any section missing.
6. Collapse or map `unknown` → design’s Refuted/Not actionable per §4.

### Phase 99E-R3 — Calibration and blockers

7. Apply **97D refutation calibration** before E2+ refute demotion (pattern + weak `path.no_implicit_none_exit`).
8. Encode blockers **3.1–3.6** explicitly; remove or justify extra blockers (`finding_confidence_not_high`) vs design.

### Phase 99E-R4 — Enablement governance

9. Implement **§6 validation runner** (QuixBugs correct, holdout fixed, 95E label replay, 98A review gate).
10. Add **shadow mode** (compute/log Confirmed without surfacing tag) per §7 staged enablement.
11. Document expected **0 Confirmed on test-less corpora** as passing state until executable witnesses exist.

### Phase 99E-R5 — Schema policy

12. Decide: keep `confirmed_defect_classification` as internal audit field vs design “no schema change” — if kept, document as **export-only** overlay, not a finding kind/promotion change.

### Acceptance for remediation complete

- Every row marked **No** or **Partial** in §2 addressed or explicitly waived with design amendment.
- With default flags, behavior remains neutral.
- With both flags on, **no** Confirmed unless §6 oracles pass and §2 bundle complete.
- `test_proven_synthetic_confirmed` updated to reflect design C1–C6, not shortest-path OR logic.

---

## 9. Conclusion

Phase 99A successfully delivered **default-off, read-only classification infrastructure** for `inconsistent_return` and preserved detector/benchmark neutrality. It does **not** implement the approved Phase 99 design’s confirmation contract.

Treat 99A as **pre-compliance scaffolding**. Do not enable the gate for product claims until **99E-R1–R4** are complete and §6 validation gates pass. The current implementation is **stronger than design in some blocker cases** but **weaker on the core Confirmed predicate** (promotion, double gate, impact, test-only executable witness, obligations, and bundle).

---

## 10. References

| Document | Role |
|----------|------|
| `reports/phase99_confirmed_defect_gate_design.md` | Approved design (audit baseline) |
| `builder_core/bug_intelligence/confirmed_defect_gate.py` | Implementation under audit |
| `reports/phase99a_confirmed_defect_gate_infrastructure.md` | 99A self-report (documents intentional divergences from design) |
| `reports/confirmed_defect_shortest_path.md` | Prior sequencing doc (OR-logic source of 99A behavior) |
| `builder_core/tests/test_phase99a_confirmed_defect_gate.py` | Behavioral oracle for 99A (not design C1–C6) |
