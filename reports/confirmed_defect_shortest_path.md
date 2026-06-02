# Confirmed-Defect Shortest Path

**Goal:** *"JARVIS can **correctly** tell developers what is broken."*
**Date:** 2026-05-31
**Type:** Sequencing analysis. **No code.**
**Hard constraints honored:** use existing infrastructure; **build no new analysis
system**; consume existing evidence; deliver a step-by-step sequence.
**Inputs:** Phase 95E (real-repo human review), Phase 97C (verification-evidence
review pilot), Phase 97D (verification calibration), `repository_intelligence_roadmap_v1.md`,
`defect_confirmation_research.md`.

---

## 0. One-line answer

> **Do not build contract/path analysis. Calibrate the verification-evidence
> overlay that already exists (per Phase 97D), define a deterministic
> "confirmed" gate over the atoms it already emits, validate it against evidence
> that already exists (holdout tests as the positive oracle, the 95E labels as
> the negative oracle), and ship only that gated tier as "broken."**

The gap to "correctly tell what is broken" is **proof, not warning volume**
(defect_confirmation_research §9). Every piece of proof machinery is already
built; it is dormant and miscalibrated, not missing.

---

## 1. What the evidence already proved

| Source | Fact | Consequence for the path |
|---|---|---|
| **95E** | On 2 real repos, 202 grounded findings → **0 confirmed**, **73.3% useful leads**, **7.4% misleading**, strict precision **0.0** | Raw grounded output is *review leads*, not "broken." Default-emitting it is the wrong product claim. |
| **95E** | **176/202 (87%)** were `null_dereference`; dominant FP cause = **intraprocedural null analysis missed visible guards** | The noise is refutable by evidence already computable: a visible guard = a refuting path witness. |
| **97A/97C** | The verification overlay emits typed atoms (polarity supports/refutes, strength, **proof obligations**, **blockers**, **path-feasibility witnesses**) and **helped review in 20/20 cases** (confirmation clarity 3.0→4.0) | The confirmation/refutation engine **exists and works** to orient humans. |
| **97D** | The overlay **over-refutes**: a single weak witness (`path.no_implicit_none_exit`) drove a global `status: refuted` on 16/20 cases; **12/14 reclassifications were over-refutation, only 2 correct** | The overlay needs **calibration**, not replacement. 97D already specifies the fix. |
| **research §3, §8** | A confirmed defect = explicit **contract** + **feasible violating path** + **observable consequence** + **verification evidence**; smallest bridge is a minimal defect packet | The output contract is already defined. Reuse it verbatim. |
| **roadmap M3/M4** | Verification-evidence is built but `EVIDENCE_PROMOTION_ENABLED=False`; promotion must be precision-gated | The remaining work is gating + surfacing, not analysis. |

**Synthesis:** 97C/97D measured the overlay in the **refutation** direction (which
findings are *not* defects). A **confirmed defect is the same machinery read in the
opposite direction** — a finding the overlay **cannot refute** and whose proof
obligations are **all met**. Nothing new needs to be analyzed.

---

## 2. Existing infrastructure to consume (no new analysis)

| Capability needed for confirmation | Already exists as | Status |
|---|---|---|
| Expected contract (nullability, return shape, pre/post, security boundary) | `contract_facts.py` (96A) | Built; emits facts, dormant |
| Refuting / supporting witnesses with polarity + strength | `verification_evidence.py` (97A) atoms | Built; **miscalibrated (97D)** |
| Proof obligations + which are missing | 97A `missing_proof_obligations` | Built; improved clarity (97C) |
| Blockers / unknowns | 97A `blockers`, `why_not_confirmed` | Built |
| Path-feasibility (guard accounting) | 97A `path_feasibility_evidence` (`path.no_implicit_none_exit`, `path.partial`) | Built; **the over-refutation driver** |
| Executable proof (failing test) | 97A `test_evidence` / `runtime_reproduction_evidence` (parser-only / dev-controlled) | Built; rarely populated |
| Confirmation taxonomy (confirmed vs lead vs advisory) | **Phase 95F** separation | Defined |
| Negative oracle (clean repos) | **95E** 202 adjudicated labels | Exists |
| Positive oracle (known bugs + tests) | **holdout** (2 TP, failing tests) + **QuixBugs** (12 TP) | Exists, frozen |
| Output packet shape | research §3.1 **minimal defect packet** | Specified |

Everything above is on disk. The path below **wires and calibrates** it.

---

## 3. The shortest sequence (step by step)

Each step is tagged with the existing artifact it consumes. No step builds a new
analyzer.

### Step 1 — Adopt the confirmation taxonomy as the output contract
Make `ask`/scan output classify every finding into the **95F** buckets:
`confirmed_defect | retained_lead | security_review_lead | advisory | refuted`.
This is a label field, not analysis. *(Consumes 95F.)*

### Step 2 — Apply the 97D calibration to the overlay's status logic
This is editing existing status-assignment rules, not adding analysis. Apply 97D
verbatim:
- Do **not** set `status: refuted` when the finding is `kind=pattern` and the only
  witness is `path.no_implicit_none_exit`; emit `enriched_lead` + a refuting atom
  (polarity `refutes`, strength E2) instead of a global refutation.
- Keep `contract_violation_evidence` **supporting-only** until the gate is on.
- Require a **path witness paired** with a violation atom before any
  `refuted`/`blocked` status.
- Rename packet `refuted` → `refutation_witness_present`.
This simultaneously kills 97D's over-refutation **and** prevents the mirror failure
(over-confirmation) in Step 3. *(Consumes 97D recommendations.)*

### Step 3 — Define the deterministic confirmation gate over existing atoms
A finding is **`confirmed_defect`** iff, from atoms already emitted:
```
missing_proof_obligations == ∅
  AND blockers == ∅
  AND no surviving refuting witness at strength ≥ R_threshold
  AND ≥ 1 supporting witness of an executable/strong type:
        failing test_evidence
        OR runtime_reproduction_evidence
        OR (contract_violation_evidence PAIRED WITH a feasible path_feasibility witness)
```
Otherwise → `retained_lead` (or `security_review_lead` / `advisory`) if partially
supported, or `refuted` if a strong refuting witness survives. This is a pure
function of existing fields. *(Consumes 97A atoms.)*

### Step 4 — Consume the strongest existing evidence first: tests
The binary, highest-trust witness is a **failing test bound to the finding**
(`test_evidence`). The holdout harness already runs buggy-vs-fixed with tests, so
this atom type is real and parser-safe. Wire the gate to prefer it. No new
execution of untrusted code — only developer-controlled / already-available test
results (97A safety boundary; research §6.3). *(Consumes 97A `test_evidence` + the
holdout test surface.)*

### Step 5 — Let the overlay refute the 95E noise
Route `null_dereference` and the two security rules through the gate. A finding
whose None-path (or taint-path) is excluded by a **surviving refuting path witness**
(the visible guard from 95E) is `refuted` → **not emitted as broken**. This
collapses 95E's dominant FP family using evidence the overlay already computes —
without touching the null analyzer. *(Consumes 97A `path_feasibility_evidence`;
fixes 95E's 7.4% misleading.)*

### Step 6 — Calibrate thresholds on existing labels (no new corpus)
Tune `R_threshold` and the supporting-strength bar against the **95E 202 adjudicated
labels** (negative oracle) and the **97C/97D 20 labels**. Target: strict precision
of the `confirmed_defect` tier ≥ the external-alpha bar (0.90) and misleading rate
< 0.05 on the labeled set. **Accept an empty confirmed tier on the clean pilot as
correct** — see §5. *(Consumes 95E + 97C/97D labels.)*

### Step 7 — Validate the positive direction on existing bug oracles
The confirmed tier must **fire** where ground truth and a failing test exist:
re-run **holdout** (2 known transfer bugs with tests) and **QuixBugs** (12) through
the gate. Required outcome: confirmed on the buggy variant, **empty on the fixed
variant** (0 FP preserved). This is the proof that "confirmed" means *broken*, not
*suspicious*. *(Consumes holdout + QuixBugs, frozen — no detector change.)*

### Step 8 — Re-run the 95E pilot through the gated output
Expected, honest result: **0 confirmed** (the repos had no test-backed defects),
**misleading rate below the 5% cap** (guards now refute), and the 148 leads
re-labeled `retained_lead`. This turns the 95E `HOLD` into a *correct, conservative*
product statement instead of 202 unproven warnings. *(Consumes the 95C/95E run.)*

### Step 9 — Ship the gated tier as the only "broken" claim
Default product surface = **`confirmed_defect` only**, each carrying the research
§3.1 **minimal defect packet** (expected contract, violating condition, feasible
path, observable consequence, evidence, unknowns). Everything else is explicitly
labeled *not a confirmed defect*. Point the external-alpha `strict_precision` gate
at this tier. *(Consumes research §3.1 packet + 95E gate definitions.)*

---

## 4. What "confirmed" consumes vs. what it must NOT build

| Confirmation question (research §3) | Answered today by consuming | Do **not** build now |
|---|---|---|
| What is expected? | `contract_facts` (96A) type/return/assert/test facts | A full contract-inference engine |
| Is the path feasible? | `path_feasibility_evidence` (97A) guard witnesses | A new symbolic path engine |
| Does a witness refute it? | 97A refuting atoms (calibrated per 97D) | New dataflow analysis |
| What closes the case? | `test_evidence` / `runtime_reproduction` (97A) | An execution sandbox for untrusted repos |
| Confirmed vs lead? | 95F taxonomy + the §3 gate | A new classifier |

The `defect_confirmation_research` ranks "build contract analysis with
path-feasibility" as the #1 capability — that is the **long-term** answer (it is
labeled *high difficulty, high risk, build*). The **shortest** path deliberately
substitutes the **already-built approximations** (96A facts + 97A path witnesses),
gated conservatively, and lets the tier stay **small** rather than building the
full engine. Confidence comes from the gate's strictness, not from new analysis.

---

## 5. The honest outcome (why an empty/small tier is success)

"**Correctly** tell developers what is broken" includes **correctly saying nothing
is confirmed-broken here.** On the 95E corpus the right answer is 0 confirmed +
148 leads, not 202 warnings dressed as defects. The product becomes trustworthy
the moment its "broken" list is *only* test/contract-proven items — even if that
list is short. Recall of the confirmed tier grows only as test-bearing,
defect-rich code is analyzed (holdout/QuixBugs demonstrate it fires there).

This also resolves the roadmap's M1/M2/M4 in one move: M2 (signal-by-default)
becomes "show the confirmed tier"; M4 (evidence-first) is the §3.1 packet; the
precision number M1 wanted is measured on the gated tier in Steps 6–7.

---

## 6. Acceptance / definition of done

| Criterion | Target | Oracle |
|---|---|---|
| Confirmed tier fires on known bugs | ≥ the existing TP count on buggy variants | holdout (2), QuixBugs (12) |
| Confirmed tier silent on fixed code | 0 false positives | holdout/QuixBugs fixed variants |
| Strict precision of confirmed tier | ≥ 0.90 | 95E + 97C/97D labels |
| 95E misleading rate after gating | < 0.05 | re-run 95E |
| Every confirmed defect ships a §3.1 packet | 100% | output audit |
| No detector / engine / benchmark change | enforced | only overlay status calibration + output gating |
| Verification stays read-only / dev-controlled | enforced | 97A parser-only boundary |

---

## 7. Technical risk

| Risk | Severity | Control (from existing evidence) |
|---|---|---|
| **Over-confirmation** (mirror of 97D over-refutation) | Med | Strict strength thresholds; require executable or contract+path-paired support (Step 3); calibrate on 95E labels (Step 6) |
| **Over-refutation suppresses real bugs** | Med | 97D fixes already cap weak witnesses; positive oracle (Step 7) catches regressions |
| Empty tier read as "no value" | Low | Leads remain available + labeled (95F); empty-is-correct framing (§5) |
| Test atoms rarely present on real repos | Med | First confirmations come from test-bearing code; do **not** add untrusted execution to compensate |
| Calibration overfits 20-case 97C cohort | Low–Med | Prefer the larger 95E set (202) for thresholds; treat 97C as a smoke check |

---

## 8. Dependencies (sequence-critical)

```
Step 2 (97D calibration)  ─┬─>  Step 3 (gate)  ─>  Step 4 (tests)  ─>  Step 5 (refute 95E noise)
                           │
Step 1 (95F taxonomy)  ────┘                                   Step 6 (calibrate on 95E labels)
                                                                      │
                                       Step 7 (holdout/QuixBugs oracle)  ─>  Step 8 (re-run 95E)  ─>  Step 9 (ship gated tier)
```
Hard order: **97D calibration (2) precedes the gate (3)** — without it the gate
inherits the over-refutation bias. **Thresholds (6) precede shipping (9).**

---

## 9. Bottom line

The shortest path to "JARVIS correctly tells developers what is broken" is **nine
calibration-and-wiring steps over infrastructure that already exists** — the 97A
verification overlay, calibrated per 97D, gated to a confirmed tier defined purely
by existing atoms, validated on the holdout/QuixBugs positive oracle and the 95E
negative oracle, and shipped as the only "broken" claim with the research §3.1
packet. **No new analysis system is built.** The honest near-term result is a
small, test/contract-proven "broken" list and a clearly-separated lead list — which
is exactly what *correctly* requires.
