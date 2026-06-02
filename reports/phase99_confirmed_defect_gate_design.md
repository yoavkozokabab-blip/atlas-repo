# Phase 99 Design — Confirmed Defect Gate

**Status:** Design only. No code, no implementation, no detector changes.
**Date:** 2026-05-31
**Core principle:** *A finding is confirmed only if evidence proves breakage. No
evidence = review lead, not bug.*
**Scope of first gate:** `inconsistent_return` only, default-off.
**Inputs:** `confirmed_defect_shortest_path.md`, `phase95e_pilot_human_review_results.md`,
`phase97c_verification_evidence_review_pilot.md`, `phase97d_verification_calibration_analysis.md`,
`phase98a_real_repository_validation_execution.md`.

---

## 0. Why this is the safe first gate

This gate **consumes** the existing verification-evidence overlay (97A) — it adds
**no analysis**. It defines one new output tier, `Confirmed Defect`, strictly
above the overlay's existing `promotion_candidate` status, and applies it to a
single rule.

`inconsistent_return` is the correct first target because:

- It is the **most-studied** rule for verification evidence (97C/97D are entirely
  about it). The atoms, blockers, and failure modes are already characterized.
- It is currently an **advisory `pattern` finding** (98A: `pattern` excluded from
  grounded precision; 92B/93B quarantined the fact-backed variant). A confirmed
  subset therefore **cannot disturb any existing grounded precision claim**.
- The overlay on `inconsistent_return` is **predominantly refuting/blocking**
  (97C: 16/20 refuted, 4/20 blocked, **0 supported**). A confirmation gate over it
  starts **near-empty**, which is exactly the conservative behavior wanted for a
  first gate.

The honest near-term outcome is **0 confirmed on test-less repositories** (95E/97C
had no bound `test_evidence`). That is success, not failure: "correctly tell what
is broken" includes correctly confirming **nothing** when proof is absent.

---

## 1. Exact Confirmed Defect criteria

A finding `F` (rule `inconsistent_return`) is **`Confirmed Defect`** iff **all** of
the following hold over the **already-emitted** 97A overlay for `F`:

```
C1  base_status == promotion_candidate
       (i.e. ∃ contract_violation atom  AND
             ∃ path_feasibility atom with provenance.path_status == "feasible"  AND
             no blockers)                                  [existing _evaluate_status]
C2  no surviving refuting guard:
       no atom with polarity == "refutes" and strength ∈ {E2,E3,E4}
       AFTER 97D calibration (see §8 dependency)           [existing + calibrated]
C3  executable witness present:
       ∃ atom with evidence_type ∈ {test_evidence (failing, bound to F),
                                     runtime_reproduction_evidence}
C4  observable consequence resolved:
       ∃ a resolved consuming context for F's value
       (a caller/return-site that uses the optional value without a guard),
       sourced from impact scope (§2.6), not assumed
C5  missing_proof_obligations == ∅                          [existing helper]
C6  both safety flags enabled:
       EVIDENCE_PROMOTION_ENABLED == True
       AND CONFIRMED_DEFECT_GATE_ENABLED == True            [new flag, default False]
```

`Confirmed Defect ⟺ C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5 ∧ C6`.

Each clause maps to a field that already exists (`STATUS_PROMOTION_CANDIDATE`,
`POLARITY_REFUTES` + `STRENGTH_LEVELS`, `EVIDENCE_TEST`/`EVIDENCE_RUNTIME`,
`_missing_proof_obligations`). The gate is a **pure boolean function of existing
atoms** plus impact scope. It computes nothing new.

**Key property:** `Confirmed ⊂ promotion_candidate ⊂ all findings`. The gate can
only ever *upgrade* a finding that the overlay already rates as a promotion
candidate. It never reaches `enriched_lead`, `refuted`, `blocked`, or `unknown`
findings, and never touches finding generation.

---

## 2. Required evidence bundle

A `Confirmed Defect` must carry a complete bundle. Each element is an existing
artifact; if any is absent, the finding is **not** confirmed (it falls to a lower
tier per §4).

| # | Bundle element | Existing source | Requirement for Confirmed |
|---|---|---|---|
| 2.1 | **Finding** | the `inconsistent_return` `Finding` (file, line, function, rule, id) | present |
| 2.2 | **Contract / expected behavior** | `EVIDENCE_CONTRACT_VIOLATION` atom from `contract_facts` (96A) — the return/nullability contract the function is required to satisfy | present, strength ≥ **E2**; a mere type hint or weak signal is **not** a contract violation (see blocker §3.3) |
| 2.3 | **Feasible violation path** | `EVIDENCE_PATH_FEASIBILITY` atom with `provenance.path_status == "feasible"` (E3 supports) — a reachable path where the function falls through / returns the optional value | present and **feasible** (not `partial`) |
| 2.4 | **No refuting guard** | absence of a surviving `POLARITY_REFUTES` atom at E2+ | the violating path is **not** excluded by an `is None` / truthiness / early-return guard |
| 2.5 | **Test / runtime / assertion witness** | `EVIDENCE_TEST` (failing, bound) or `EVIDENCE_RUNTIME`; `EVIDENCE_ASSERTION` as supporting context | **executable witness (test or runtime) REQUIRED for Confirmed**; assertion-only ⇒ Strong Suspect, not Confirmed |
| 2.6 | **Impact scope** | Phase 94B impact analysis for `F`'s function — the resolved consuming callers/return-sites | direct impact **resolved** (not degraded/unresolved on the consuming edge); supplies the observable consequence (2.4/C4) |

The bundle is exactly the `confirmed_defect_shortest_path.md` §3 minimal packet
(contract → feasible path → consequence → verification) instantiated for one rule.

---

## 3. Hard blockers (any one ⇒ NOT Confirmed)

A blocker forces the finding **out** of `Confirmed Defect` (down to the tier named
in §4). Each maps to an existing overlay signal.

| # | Blocker | Existing signal | Resulting tier |
|---|---|---|---|
| 3.1 | **Unresolved critical edge** | `interprocedural_promotion_gate_not_met` blocker, or an unresolved call on the violating path, or **degraded** impact scope on the consuming edge | Strong Suspect or Review Lead |
| 3.2 | **Visible guard** | surviving `POLARITY_REFUTES` path_feasibility atom (E2+) that excludes the None path | **Refuted / Not actionable** |
| 3.3 | **Weak contract only** | no `EVIDENCE_CONTRACT_VIOLATION` atom (only a type hint / optional-return signal, strength ≤ E1) | Review Lead |
| 3.4 | **Path feasibility unknown** | path_feasibility `provenance.path_status == "partial"` (not `feasible`) | Strong Suspect (if other support) / Review Lead |
| 3.5 | **No consequence** | no resolved consuming context for the value (no caller obligation; return is unused or only locally consumed safely) | Review Lead |
| 3.6 | **Refuting evidence** | any surviving `POLARITY_REFUTES` atom at E2+ (`_evaluate_status` → `refuted`) | **Refuted / Not actionable** |

**97D guard (over-refutation):** 3.2/3.6 must use a **97D-calibrated** overlay — a
single weak `path.no_implicit_none_exit` witness on a `kind=pattern` finding must
**not** be treated as a genuine refuting guard (it is the over-refutation driver,
12/14 of 97D reclassifications). Until calibration lands, that witness over-refutes,
which only makes the gate **more** conservative (fewer Confirmed) — safe, lower
recall. See §8.

---

## 4. Output taxonomy

Four mutually exclusive tiers. Each maps onto the existing 97A status set plus the
one new top tier; the gate is the only thing that assigns `Confirmed Defect`.

| Tier | Definition (over existing atoms) | Existing status basis | Product meaning |
|---|---|---|---|
| **Confirmed Defect** | §1 C1–C6 all true (executable witness + feasible path + contract violation + no refute + resolved consequence + flags on) | `promotion_candidate` **+** executable witness **+** resolved impact | "This is broken — here is the proof." |
| **Strong Suspect** | `promotion_candidate` (contract violation + feasible path + no blockers + no E2+ refute) **but missing an executable witness** (C3) or unresolved consequence (C4) | `promotion_candidate` | "Statically strong, unverified by execution. Inspect." |
| **Review Lead** | some support; ≤1 blocker; weak/partial evidence | `enriched_lead` | "Worth inspecting." (the 95E ~73% bucket) |
| **Refuted / Not actionable** | surviving E2+ refute, or ≥2 blockers, or no atoms | `refuted` / `blocked` / `unknown` | "Guard present / disproven / no evidence — not a bug." |

Mapping summary: `Confirmed Defect` is new; `Strong Suspect` = `promotion_candidate`;
`Review Lead` = `enriched_lead`; `Refuted/Not actionable` = `refuted ∪ blocked ∪ unknown`.

---

## 5. First target rule — `inconsistent_return` only

- The gate evaluates **only** findings with `rule == "inconsistent_return"`.
  Every other rule passes through **unchanged** with its current status and is
  **never** eligible for `Confirmed Defect` in Phase 99.
- Rationale: richest verification evidence (97C/97D), currently advisory/quarantined
  (no grounded-precision exposure), overlay predominantly refuting (gate starts
  near-empty).
- Explicitly **excluded** from this gate: `null_dereference`, `command_injection`,
  `path_traversal` (the 95E families), and the other 14 rules. They remain at their
  current tiers. Extending the gate to a second rule is a **separate, later phase**
  with its own validation.

---

## 6. Validation gates (must pass before and to stay enabled)

| # | Gate | Pass criterion | Oracle / source |
|---|---|---|---|
| 6.1 | **QuixBugs correct** | **0** `inconsistent_return` findings on QuixBugs *correct* programs are marked `Confirmed Defect` (0 FP) | `C:\Repos\QuixBugs` correct variants (frozen) |
| 6.2 | **Holdout fixed** | **0** Confirmed on holdout *fixed* variants (0 FP) | holdout fixed pairs (frozen) |
| 6.3 | **Phase 95E rejected findings** | re-running the gate over the 95E-labeled set yields **0 Confirmed** among findings humans labeled `false_positive`/`not_useful` (the 18 FP + 34 not-useful) | `phase95e_pilot_human_review_results.md` labels |
| 6.4 | **Phase 98A review sample** | **human review required before enabling.** The gate's `Confirmed Defect` candidates within the 98A 300-finding blinded sample must be reviewed and confirmed by ≥2 blinded reviewers with adjudication; enable only if reviewed-Confirmed precision is **1.0** (0 misleading) on that sample | `reports/phase98a_run/` review workflow (95D tooling) |

Additional standing invariants (regression guards, not new gates):
- The full suite stays green (98A baseline **337 passed**).
- QuixBugs 12 TP / 0 FP and holdout 2 TP / 0 FP **detector** numbers are unchanged
  (the gate is downstream of findings; it changes no detector output).
- On test-less corpora (95E/97C), Confirmed count is **0** (expected).

**Interpretation of 6.1/6.2:** these are *negative* gates (the gate must stay
silent on correct/fixed code). The *positive* direction — Confirmed firing on a
genuinely broken, test-backed `inconsistent_return` — is demonstrated on a
fixture/corpus where a failing test binds to the finding (holdout-style buggy
variant with a bound test). Until such a case exists, an empty Confirmed tier is
the correct, passing state.

---

## 7. Rollback and default-off behavior

- **Default-off flag:** `CONFIRMED_DEFECT_GATE_ENABLED = False` (new, default
  False). When False, `inconsistent_return` findings retain their current status
  (`enriched_lead` / advisory) and **no finding is ever labeled `Confirmed
  Defect`**. The system behaves exactly as today.
- **Double gate:** `Confirmed Defect` additionally requires the pre-existing
  `EVIDENCE_PROMOTION_ENABLED == True` (today False). Both flags must be on — two
  independent off-switches.
- **Additive only:** the gate is a downstream **label** over existing overlay
  output. It does **not** modify detectors, finding generation, finding schema
  (the tier is an output classification, not a new finding), benchmarks, or
  promotion of any other rule.
- **Rollback:** set `CONFIRMED_DEFECT_GATE_ENABLED = False` (or remove the tier
  mapping). Because the gate writes nothing into any analysis path and only ever
  *upgrades* a `promotion_candidate` to a display tier, disabling it is provably
  behavior-neutral for detectors, benchmarks, and all non-`inconsistent_return`
  output.
- **Staged enablement:** off → shadow (compute Confirmed candidates, log only, do
  not surface) → 6.4 human review → on for `inconsistent_return` only. Any
  regression in 6.1–6.4 returns to off.

---

## 8. Dependencies and prerequisites

- **97D calibration of the overlay** is a prerequisite for *recall* of this gate
  (so genuine violations are not falsely refuted by the weak
  `path.no_implicit_none_exit` witness). It is **not** a prerequisite for *safety*:
  an uncalibrated overlay over-refutes, producing **fewer** Confirmed, never more.
  The gate may ship default-off against an uncalibrated overlay and gain recall
  when 97D lands.
- **Phase 94B impact** supplies the resolved consuming context (2.6/C4). If impact
  is degraded/unresolved on the consuming edge, clause C4 fails → not Confirmed.
- **EVIDENCE_PROMOTION_ENABLED** remains the inner gate; Phase 99 does not flip it.

---

## 9. Safety / constraints honored

- No detector changes; no new detectors.
- No benchmark changes (QuixBugs/holdout detector numbers unchanged; suite 337).
- No finding-schema change — `Confirmed Defect` is an output tier, not a finding.
- No new analysis system — the gate is a boolean over existing 97A atoms + 94B impact.
- No promotion of any rule other than `inconsistent_return`, and only behind two
  default-off flags.
- No target code executed by the gate; executable witnesses (2.5) consume
  **existing** test results / developer-controlled runs only (97A parser-only /
  dev-controlled boundary).
- Default-off; human review (6.4) required before first enablement.

---

## 10. Acceptance (definition of done for this design's implementation)

1. `Confirmed Defect` defined exactly by §1 C1–C6 over existing atoms; no new analysis.
2. Bundle (§2) attached to every Confirmed candidate; missing any element ⇒ lower tier.
3. Hard blockers (§3) demote correctly; 3.2/3.6 honor 97D calibration.
4. Output taxonomy (§4) assigns exactly one of the four tiers to each
   `inconsistent_return` finding; all other rules untouched.
5. Validation gates 6.1–6.4 pass; 6.4 human review completed before enable.
6. Default-off; rollback flips one flag; behavior-neutral when off.
7. Expected first-run result documented and accepted: **0 Confirmed** on test-less
   corpora (95E/97C/98A), Confirmed firing only where an executable witness binds.
