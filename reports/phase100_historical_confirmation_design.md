# Phase 100 Design — Historical Confirmation

**Status:** Design only. No code.
**Date:** 2026-05-31
**Goal:** Move a finding from **Strong Suspect** to **Historically Proven
Confirmed Defect** — a confirmation corroborated by a real buggy→fixed
differential, not by a single static witness.
**Consumes (all on disk):** Phase 99 gate (tiers + bundle), Phase 99B evaluation
protocol (scorecard + automatic fails), Phase 99C historical corpus (answer keys),
Phase 99D replay harness (`builder_core/historical_bug_replay/`).

---

## 0. The tier this phase defines

```
Review Lead
  → Strong Suspect            statically strong; no executable witness
  → Confirmed Defect          Strong Suspect + in-repo executable witness   (Phase 99)
  → Historically Proven       Confirmed Defect + buggy→fixed differential    (Phase 100)
        Confirmed Defect       + preregistered ground-truth match + human acceptance
```

**Strong Suspect → Historically Proven** is earned **only** by replaying a
preregistered buggy/fixed pair: the historical corpus *supplies* the witness
(trigger test) and the *differential* (present-on-buggy, gone-on-fixed) that an
in-repo Strong Suspect lacked. It is **never** earned by resemblance to a past bug
— that would be guessing. The output of Phase 100 is a **measured track record**:
"the gate historically-proves N defects across M repositories at 100% precision,"
which is what licenses the product claim.

This phase **builds no analysis**. It orchestrates the existing 99D harness over
the existing 99C corpus, validates packets against existing 99B rules, and reports
existing 99D/99B metrics.

---

## 1. Historical bug replay workflow

End-to-end, read-only, default-off, gate-enabled-in-session-only (99D guarantee).

| Step | Action | Existing artifact |
|---|---|---|
| **1. Freeze candidate** | Record Builder Core commit, Phase 99 gate version, detector version, evidence-schema version, feature flags, corpus/sample/fixture manifest hashes | 99B §10.1 |
| **2. Lock corpus** | Preregister the 99C manifest (buggy/fixed revisions, trigger test, `expected_packet.json`, hard-negatives, distractors); freeze before any run | 99C, 99B §6 |
| **3. Replay** | `historical_bug_replay.cli run --manifest <99C> --output <run> --enable` — runs `analysis → contract_review → verification_evidence → confirmed_defect_gate` on **both** revisions of every case | 99D harness |
| **4. Collect** | Per case: `classification` on buggy and on fixed (`detected`/`strong_suspect`/`review_lead`/`refuted`/`unknown`), the full gate packet, and the trigger-test result | 99D `results.json` |
| **5. Differential** | Apply §2 (buggy→fixed comparison) | 99D `metrics.json` |
| **6. Packet validation** | Apply §3 (schema + ground-truth + unsupported/hidden-edge audits) | 99B §2/§8, 99C keys |
| **7. False-confirmation guards** | Apply §4 (Tracks B/D + automatic fails) | 99B §6/§8 |
| **8. Human review** | Dual blinded review + adjudication of every confirmed candidate | 99B §7 |
| **9. Measure** | Compute §5 historical precision/recall; assign 99B score (`<7` / `7` / `8`) | 99B §4/§5/§9 |

The workflow runs Track D (synthetic negatives) **before** Tracks A/B (99B §10
Step 3): any synthetic-negative confirmation stops the run before historical
claims are even measured.

---

## 2. Buggy → fixed comparison

The differential is the heart of "historically proven." For each case, the gate is
run on both revisions and the outcomes are compared.

### 2.1 The three differential outcomes

| Buggy revision | Fixed revision | Verdict |
|---|---|---|
| `detected` (confirmed) **at the fix site** | absent / `refuted` / blocked-by-changed-evidence | **PROVEN candidate** (→ human review §1.8) |
| `detected` (confirmed) | **still `detected`** | **AUTOMATIC FAIL** — fixed-version persistence (99B §8.5) |
| not `detected` | — | **MISS** — counts in the recall denominator; not a failure |

### 2.2 Required corroboration for a PROVEN candidate

1. **Directional clearance** — the confirmed finding is `detected` on buggy and
   **not** `detected` on fixed (99D `cases_with_detected_buggy_only`;
   `detected_case_purity == 1` for the case).
2. **Fix-site identity** — the confirmed finding's `file:function:line` corresponds
   to the case's `affected_files`/`affected_functions` (99C). A confirmation that
   lands where the fix did **not** touch is **incidental** → rejected, not proven.
3. **Witness flip** — the case's trigger test **fails on buggy, passes on fixed**
   (99C verification evidence). This corroborates that the differential reflects the
   real fix, not unrelated drift.

A PROVEN candidate is one where directional clearance ∧ fix-site identity ∧ witness
flip all hold. Only then does it proceed to packet validation and human review.

---

## 3. Confirmation packet validation

Every confirmed candidate must carry a complete, honest, ground-truth-matching
proof packet. Three audits, all failing-closed.

### 3.1 Schema completeness (99B §2.2, §8.2)
Every required section present: `expected_contract`, `violating_condition`,
`feasible_path`, `observable_consequence`, `supporting_evidence`,
`refuting_evidence_considered`, `unresolved_edges`, `blockers`,
`runtime_or_test_evidence`, plus `gate_version`/`evidence_schema_version`/
`detector_version`. **Any missing section → automatic fail** (the finding may
remain a Strong Suspect / review lead; it may not remain confirmed).

### 3.2 Ground-truth match (99C answer key)
The produced packet must **match** the case's preregistered `expected_packet`:
same rule (`inconsistent_return` for the first gate), the stated contract aligns
with the expected contract, a feasible (not partial) path is present, the witness
is the registered trigger test, and the tier is `confirmed_defect`. A **right
verdict with the wrong reasoning** (packet mismatch) is **not** historically proven
— it is flagged for review (prevents accidental-correct confirmations).

### 3.3 Unsupported-claim & hidden-edge audit (99B §8.3, §8.4)
Automatic fail if the packet: treats impact as proof; claims a feasible path on a
**partial** witness; uses `callee_behavior` alone as a contract; uses docstring as
decisive; ignores explicit `Optional`, a dominating guard, or an expected negative
test; relies on a stale/flaky/unbound runtime artifact; claims third-party behavior
without project-grounded evidence; or **omits any critical unresolved edge**.
Visible unresolved edges may stand; **hidden** ones always invalidate trust.

---

## 4. False-confirmation prevention

The governing rule (99B §0): **one confirmed false positive is an automatic
evaluation failure** — never averaged against correct cases. Prevention is
**multiplicative** (every guard must pass), layered as follows.

| # | Guard | Source | On violation |
|---|---|---|---|
| 4.1 | **Fixed-version persistence** — confirmed on the fixed revision | 99B §8.5 / 99D `detected_on_fixed` | **Automatic fail** |
| 4.2 | **Synthetic-negative confirmation** — any Track D fixture confirmed (optional-return, dominating guard, truthiness narrowing, raise-only exit, expected-negative test, unresolved/dynamic edge, star import, runtime assignment, shadowed symbol, third-party boundary, impact-only, **single weak `path.no_implicit_none_exit` witness**, stale/flaky runtime, security-sink-no-provenance) | 99B §6.4/§8.6, 99C hard-negatives | **Automatic fail** |
| 4.3 | **Incidental confirmation** — confirmed away from the fix site | §2.2 (2) | Reject (not proven) |
| 4.4 | **Incomplete / unsupported / hidden-edge packet** | §3 / 99B §8.2–§8.4 | **Automatic fail** |
| 4.5 | **Over-confirmation (97D mirror)** — confirmation driven by one atom/status rather than the complete Phase 99 bundle (C1–C6) | 99B §1.2, 97D | Reject (require full bundle) |
| 4.6 | **Human-rejected confirmation** — any adjudicated `rejected_false_confirmation` | 99B §8.1 | **Automatic fail** |
| 4.7 | **Integrity failure** — corpus changed post-preregistration, detector/gate version changed mid-eval, tuning after seeing results, blinding broken, target modified/executed outside the trigger-test boundary | 99B §8.7 | **Automatic fail** |
| 4.8 | **Non-determinism** — replay not byte-stable across frozen reruns | 99B §5.6 | Block (must be deterministic) |

Tracks B (fixed versions) and D (synthetic negatives) are the dedicated
false-confirmation tracks; both must produce **zero** confirmations.

---

## 5. Historical precision measurement

All metrics are existing 99D outputs or 99B dashboard formulas. They are reported
**separately** — never merged (99B §9.5).

| Metric | Formula | 7/10 | 8/10 |
|---|---|---:|---:|
| **Historical confirmation precision** | `accepted_confirmed / reviewed_confirmed` | **100%** | **100%** |
| **Confirmed false positives** | count | **0** | **0** |
| **Fixed-version clearance rate** | `confirmed_buggy_cleared_on_fixed / confirmed_buggy` (= 1 − 99D `detected_case_false_positive_rate`) | **100%** | **100%** |
| **Differential purity** | 99D `detected_case_purity` = `buggy_only / detected_on_buggy` | **1.0** | **1.0** |
| **Historical confirmation recall** | `historical_cases_confirmed / historical_cases_total` (99D `detected_case_recall`; misses kept in denominator) | **≥25%** | **≥40%** |
| **Accepted confirmed historical defects** | count | **≥10** | **≥20** |
| **Distinct repositories / defect families** | count | **≥5 / ≥3** | **≥10 / ≥5** |
| **Proof-packet completeness** | `complete_confirmed / confirmed` | **100%** | **100%** |
| **A/B confirmed-label agreement** | exact agreement / reviewed | **≥90%** | **≥95%** |
| **Phase 98A sample false confirmations** | count over 300 | **0** | **0** |

**Score assignment (99B §10 Step 9):** assign `<7` / `7` / `8`; **do not round
up**. A single automatic-fail (§4) caps the score below 7 regardless of the
averages. Recall is *measured and reported* but never traded against precision.

---

## 6. Definition — Historically Proven Confirmed Defect

A finding is a **Historically Proven Confirmed Defect** iff **all** hold:

```
H1  Phase 99 gate classification == confirmed_defect on the BUGGY revision
       (full bundle C1–C6, witness = the case trigger test)            [Phase 99 + 99D]
H2  Directional clearance: NOT confirmed on the FIXED revision           [§2.2(1), 99D]
H3  Fix-site identity: confirmed location ∈ case affected files/functions [§2.2(2), 99C]
H4  Witness flip: trigger test fails-on-buggy, passes-on-fixed           [§2.2(3), 99C]
H5  Packet complete, ground-truth-matching, no unsupported claim,
       no hidden unresolved edge                                         [§3, 99B §8]
H6  No false-confirmation guard tripped (§4)                             [99B §8]
H7  Human-accepted under dual blinded review + adjudication              [99B §7]
H8  Preregistered & deterministic (no post-hoc corpus/tuning change)     [99B §8.7]
```

`Historically Proven ⟺ H1 ∧ H2 ∧ H3 ∧ H4 ∧ H5 ∧ H6 ∧ H7 ∧ H8`.

Everything weaker is reported at its honest tier: confirmed-on-buggy-only-without-
human-acceptance = *candidate*; static-strong-without-differential = *Strong
Suspect*; cleared-but-unconfirmed = *miss*.

---

## 7. Safety, defaults, rollback

- **Default-off, in-session-only:** `HISTORICAL_BUG_REPLAY_ENABLED = False` and the
  confirmed-defect gate enabled **only inside** a replay session (99D); both return
  to off afterward. No global behavior change.
- **Read-only:** file read / `git show` only; the **only** execution is the case's
  declared trigger test in a developer-controlled sandbox (97A/99D boundary). No
  target source modified or executed otherwise.
- **No detector/benchmark/finding-schema change:** Phase 100 is orchestration +
  measurement over existing components. QuixBugs 12 TP / 0 FP and holdout 2 TP / 0 FP
  remain regression guards, not historical evidence (99B §6.5).
- **Rollback:** disable the replay flag; the workflow leaves no production state and
  emits no `Historically Proven` label outside an explicit, preregistered replay run.
- **Honest current baseline (99B §12):** 0 confirmed, **HOLD**. Phase 100 is the
  workflow that closes the open blockers — *once* the 99C corpus is built and
  locked: no preregistered corpus and no accepted cases are the remaining gaps, not
  missing machinery.

---

## 8. Acceptance (definition of done for this design)

| Criterion | Met by |
|---|---|
| Historical bug replay workflow defined end-to-end on existing 99D harness | §1 |
| Buggy→fixed comparison with directional clearance, fix-site identity, witness flip | §2 |
| Confirmation packet validation: schema + ground-truth match + unsupported/hidden-edge audits | §3 |
| False-confirmation prevention: multiplicative guards + automatic fails; 0-FP absolute | §4 |
| Historical precision measurement tied to 99B 7/10–8/10 thresholds and 99D metrics | §5 |
| `Historically Proven Confirmed Defect` defined as H1–H8 over existing artifacts | §6 |
| Default-off, read-only, no detector/benchmark change, rollback trivial | §7 |
| No code; corpus build, replay execution, and human review are later, separately reviewed phases | whole doc |

---

## 9. Bottom line

"Historically Proven Confirmed Defect" is the **buggy→fixed differential** applied
to a Phase 99 confirmation: present and confirmed on the broken revision, gone on
the fixed revision, with the trigger test flipping, a complete ground-truth-matching
packet, and human acceptance — measured over a preregistered corpus at **100%
precision with directional clearance**. The machinery already exists (99D harness,
99C keys, 99B protocol, Phase 99 gate); Phase 100 is the disciplined workflow that
turns a Strong Suspect into a claim JARVIS can defend with history.
