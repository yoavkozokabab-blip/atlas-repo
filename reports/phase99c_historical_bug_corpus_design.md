# Phase 99C — Historical Bug Corpus Design

**Status:** Design only. No code.
**Date:** 2026-05-31
**Purpose:** Design a historical bug corpus whose sole job is to **evaluate the
Phase 99 Confirmed Defect gate** — to prove it fires `Confirmed Defect` on
genuinely broken, test-backed code and stays silent on fixed/guarded code.
**Consumes:** Phase 99 gate design (criteria, evidence bundle, tiers), the holdout
pair format, BugsInPy probe, QuixBugs, the Phase 95B corpus discipline.

---

## 0. Why this corpus, and why now

Every validation run to date reports the **same hole**: `historical_bug_cases: 0`
(95B target 20–30 across ≥10 repos; 95C, 98A actual = 0). The Phase 99 gate is the
reason this hole now blocks progress:

- Phase 99 confirms a finding only with an **executable witness** (a failing
  `test_evidence`/runtime atom bound to the finding).
- 95E/97C/98A corpora are **test-less for the finding** → the gate correctly yields
  **0 Confirmed**. That proves the *negative* direction (no false confirmations) but
  **cannot exercise the positive direction at all**.

A confirmed-defect evaluation therefore needs a corpus of **real bugs that ship
with the trigger test that proves they are broken**. That is precisely the
Defects4J/BugsInPy contract: a *buggy version*, a *fixed version*, and a
*fail-on-buggy / pass-on-fixed* test. This corpus supplies exactly that, shaped to
the Phase 99 evidence bundle.

**This corpus measures the gate, not the detector.** It records both signals
separately (did the detector fire? did the gate confirm at the right tier?) so
detector recall is never conflated with gate precision.

---

## 1. Sources and their roles

| Source | What it provides | Role in this corpus | Caution |
|---|---|---|---|
| **BugsInPy** (`data/external_benchmarks/BugsInPy_probe/projects/*`) | Real bugs from real Python projects (black, fastapi, ansible, …) with `bug_patch`, pinned buggy/fixed commits, and **`run_test` trigger tests** | **Primary positive oracle** — the only source that natively carries the executable witness Phase 99 requires | Heavy; distill per-case minimal slices; trigger tests must be re-verified locally |
| **QuixBugs** (`C:\Repos\QuixBugs`) | 40 single-function algorithmic bugs, buggy + correct, with `json_testcases` | **Breadth + negative/regression oracle + tier discrimination.** Mostly *not* `inconsistent_return` | **Already a frozen detector benchmark** — must not be used to *tune* the gate (see §5) |
| **Defects4J-style principles** | Methodology only (Defects4J itself is Java) | **Curation discipline**: isolated atomic bug-fix pair, trigger test, pinned commit, reproducibility, rich metadata | Do not import Java; import the *standard* |
| **Public GitHub bug-fix commits** | Targeted real fixes where the diff adds/repairs a `return` (the `inconsistent_return` shape) plus the regression test added with the fix | **Fills the first-gate gap** — supplies real `inconsistent_return` / return-contract / nullability positives that BugsInPy/QuixBugs under-represent | License + provenance discipline; minimal extraction; pin commit SHAs |

**Source priority for the first gate (`inconsistent_return`):** GitHub return-fix
commits ≈ BugsInPy (both can carry trigger tests) > QuixBugs (breadth/negative only).

---

## 2. Per-case definition

Each case extends the existing holdout format
(`pairs/<case_id>/{buggy,fixed}.py` + `manifest.json`) with the trigger test and the
expected confirmation packet. A case is the **labeled ground truth** for the gate.

### 2.1 Buggy version
The minimal code slice containing the defect, at a **pinned** buggy commit/state.
File-faithful enough that the detector and overlay run as they would in situ.
Records: `source`, `project`, `pinned_commit`, `bug_class`, defect location
(`file:line:function`).

### 2.2 Fixed version
The same slice after the **atomic** fix (the smallest diff that removes the defect).
Used as the **matched negative**: the gate must NOT mark it `Confirmed`. Records the
fix diff and `pinned_fixed_commit`.

### 2.3 Verification evidence (the witness)
A **trigger test** that **fails on buggy, passes on fixed**, re-verified locally and
recorded as the case's executable witness. This is the `EVIDENCE_TEST` (or
`runtime_reproduction`) atom the Phase 99 gate's clause **C3/C5** requires.
- Cases **with** a bound trigger test → eligible for `Confirmed Defect`.
- Cases **without** one (test exists but does not bind to the finding, or no test) →
  eligible only up to `Strong Suspect`. The corpus deliberately includes both to
  exercise the Confirmed vs Strong-Suspect boundary.
Each case records: test id, command, fail-on-buggy result, pass-on-fixed result,
binding (does the test exercise the defect location/value?).

### 2.4 Expected confirmation packet
The Phase 99 §2 bundle the gate **should** produce for the buggy version, plus the
**expected tier**. This is the answer key:

```
case_id
bug_class                      e.g. inconsistent_return / return_contract / nullability / off_by_one ...
gate_eligible_rule             inconsistent_return | none   (Phase 99 first gate scope)
expected_tier                  Confirmed Defect | Strong Suspect | Review Lead | Refuted/Not actionable
expected_bundle:
  finding                      rule + location the detector should emit (or "detector miss")
  contract / expected behavior the return/nullability contract violated
  feasible violation path      the reachable path producing the wrong/missing return
  refuting guard               none  (positives)  |  present  (guarded distractors -> Refuted)
  witness                      trigger test id (Confirmed) | none (Strong Suspect)
  consequence / impact         the consuming caller/return-site that breaks (from 94B impact)
detector_expected_to_fire      yes | no            (separates detector recall from gate behavior)
notes / provenance
```

`expected_tier` is assigned by the same §4 taxonomy the gate uses, so corpus and
gate speak one language. Every label is **dual-reviewed** before freeze.

---

## 3. Corpus parameters

### 3.1 Minimum size

Floor aligned to Phase 95B (20–30 cases, ≥10 repos), specialized for the gate:

| Slice | Minimum | Why |
|---|---:|---|
| Total historical cases | **30** | meets the 95B upper target; statistical floor |
| Distinct projects/repos | **≥ 10** | 95B diversity; avoids single-project overfit |
| **Confirmed-eligible positives** (`inconsistent_return`/return-contract bug **with** bound trigger test) | **≥ 12** | enough to measure Confirmed *recall*; mirrors the 12 QuixBugs TP scale |
| **Matched negatives** (fixed version of each positive) | **= positives (≥ 12)** | the 0-FP backbone (Phase 99 gate 6.2 shape) |
| **Hard negatives** (optional-return-by-design / guarded functions that *look* like the bug) | **≥ 12** | proves the gate refutes guards, not just absent bugs (95E's dominant FP family) |
| **Strong-Suspect cases** (gate-eligible bug, **no** bound witness) | **≥ 6** | exercises the Confirmed vs Strong-Suspect line |
| **Distractor bugs** (other rules: off-by-one, wrong-operator, exception, …) | **≥ 10** | proves the `inconsistent_return`-only gate never confirms another rule |

### 3.2 Diversity requirements

The corpus must span each dimension (no single value > ~40% of cases):

| Dimension | Required spread |
|---|---|
| **Bug class** | return-contract / nullability (primary) **plus** off-by-one, wrong-operator, exception-handling, boundary, state (as distractors) |
| **Project domain** | ≥ 4 of: web framework, CLI tool, library, data/util, automation |
| **Size band** | small / medium / large (Phase 95B bands) |
| **Source** | BugsInPy, GitHub bug-fix commits, QuixBugs all represented |
| **Witness availability** | both *with-trigger-test* (Confirmed-eligible) and *without* (Strong-Suspect) present |
| **Refutability** | include guarded/optional-by-design look-alikes (must land `Refuted`) |
| **Diff atomicity** | predominantly single-concern fixes; record multi-hunk cases explicitly |

### 3.3 Acceptance criteria

The corpus is **accepted** (eligible to evaluate the gate) only when **all** hold:

1. **Size & diversity floors** (§3.1, §3.2) met and recorded in a manifest.
2. **Reproducible witnesses:** 100% of cases verified `fail-on-buggy / pass-on-fixed`
   on pinned commits, deterministically, with the test command recorded.
3. **Complete answer keys:** 100% of cases carry an expected confirmation packet and
   `expected_tier`, **dual-reviewed** with disagreements adjudicated (95D workflow).
4. **Preregistration:** the corpus and all labels are frozen **before** the gate is
   run against it; no case is added, removed, or relabeled to match gate output.
5. **No tuning contamination (§5):** the **positive** Confirmed oracle does not reuse
   any case already used to *tune* a detector; QuixBugs/holdout serve only as
   negative/regression/breadth here.
6. **Provenance & license:** every case has source URL, pinned SHAs, and a
   redistributable license or minimal-quote justification.
7. **Isolation & safety:** corpus lives under `data/` (RU-2 `benchmark` role,
   excluded from `ask`/production indexing); scans are read-only; no target code is
   executed except the **declared, sandboxed trigger test** under developer control.
8. **Deterministic export:** a stable manifest + per-case directory layout
   (mirroring holdout) so runs are byte-reproducible.

---

## 4. How the corpus evaluates the gate

The corpus turns Phase 99's validation into measurable numbers. Per case the runner
records: did the **detector** fire? what **tier** did the **gate** assign? — then
compares to `expected_tier`.

| Measurement | Definition | Target |
|---|---|---|
| **Confirmed precision** | Confirmed labels that are true positives ÷ all Confirmed | **1.0** (0 false confirmations) |
| **Confirmed recall (gate)** | Confirmed among the **≥12 Confirmed-eligible** positives (detector fired + witness bound) | > 0, reported honestly; not required high in v1 |
| **Negative 0-FP** | Confirmed on any **fixed** version | **0** (Phase 99 gate 6.2) |
| **Guard refutation** | hard-negative guarded look-alikes landing `Refuted` | **100%** (addresses 95E guard-blindness) |
| **Rule containment** | distractor (other-rule) bugs marked `Confirmed` by the gate | **0** (first gate is `inconsistent_return` only) |
| **Tier accuracy** | cases whose gate tier == `expected_tier` | high; mismatches triaged |
| **Detector vs gate separation** | detector-miss cases recorded distinctly from gate-tier outcome | 100% recorded |

These feed directly into Phase 99 gates **6.1 (QuixBugs correct 0-FP)**, **6.2
(holdout/fixed 0-FP)**, and supply the **positive** oracle Phase 99 lacked. Phase
99's **6.4 human review** is satisfied by the dual-reviewed answer keys here.

---

## 5. Contamination, safety, and honesty

- **No double-use as a tuning set.** QuixBugs/holdout are already frozen *detector*
  benchmarks; here they are **negative/breadth only**. The **positive** Confirmed
  oracle is built from BugsInPy + GitHub commits **not** used to tune detectors, and
  is **preregistered** so the gate is never tuned to it.
- **Detector recall is out of scope.** If the `inconsistent_return` detector does not
  fire on a known bug, that is a recorded **detector miss**, not a gate failure. The
  gate can only confirm findings the detector produced.
- **Read-only + declared execution.** Scanning is read-only (95A boundary). The only
  execution is the case's **declared trigger test**, run in a developer-controlled
  sandbox — never implicit execution of untrusted target code (97A boundary).
- **Honest positive scarcity.** Real `inconsistent_return` *defects* are rare —
  most inconsistent returns are intentional optional returns (97C/97D: overlay
  mostly refutes them). The Confirmed-eligible positive set may be **small and
  hard-won**, sourced mainly from curated GitHub return-fix commits. A small but
  clean positive set + a large clean negative set is the correct, honest shape for a
  first confirmed-defect oracle.

---

## 6. On-disk layout (deliverable of the build phase, not this design)

Mirrors and extends holdout:

```
data/historical_bug_corpus/phase99c/
  manifest.json                      # cases: id, source, project, pins, bug_class,
                                     #        gate_eligible_rule, expected_tier, license
  cases/<case_id>/
    buggy/      ...                  # minimal buggy slice (pinned)
    fixed/      ...                  # atomic-fixed slice (pinned)
    trigger_test/...                 # the fail-on-buggy/pass-on-fixed test + command
    expected_packet.json             # §2.4 answer key (bundle + expected_tier)
    provenance.json                  # URLs, SHAs, license, reviewer adjudication
```

`benchmark` role under `data/` → excluded from `ask`/production indexing by RU-2.

---

## 7. Acceptance checklist (this design's definition of done)

| Criterion | Met by |
|---|---|
| Uses BugsInPy, QuixBugs, Defects4J principles, GitHub bug-fix commits | §1 |
| Defines buggy version, fixed version, verification evidence, expected confirmation packet | §2 |
| Defines minimum size, diversity, acceptance criteria | §3 |
| Aligns each case to the Phase 99 evidence bundle + 4-tier taxonomy | §2.4, §4 |
| Supplies the positive oracle Phase 99 lacked; keeps QuixBugs/holdout as negatives | §0, §4, §5 |
| Separates detector recall from gate behavior | §0, §4, §5 |
| Contamination, license, safety, preregistration discipline | §3.3, §5 |
| No code; corpus build and gate wiring are later, separately reviewed phases | whole doc |

---

## 8. Bottom line

The shortest way to let Phase 99 prove "this is broken" is a **small, clean,
preregistered corpus of real bug-fix pairs that each carry a fail-on-buggy trigger
test**, labeled with the exact Phase 99 evidence bundle and tier. BugsInPy and
curated GitHub return-fix commits supply the test-backed **positives**; QuixBugs and
holdout supply the frozen **negatives**; Defects4J supplies the **discipline**. The
honest v1 target is **Confirmed precision 1.0 with a small but non-empty
Confirmed-recall on `inconsistent_return`**, every guarded look-alike `Refuted`, and
zero confirmations on fixed code — measured, not assumed.
