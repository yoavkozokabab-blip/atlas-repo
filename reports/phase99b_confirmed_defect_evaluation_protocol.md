# Phase 99B - Confirmed Defect Evaluation Protocol

Date: 2026-05-31

Status: Design only. No code. No tuning. No detector changes.

## 0. Executive Summary

This protocol defines how to measure whether JARVIS reaches:

```text
Defect Confirmation: 7 / 10
```

or:

```text
Defect Confirmation: 8 / 10
```

The protocol is intentionally strict. A JARVIS output may be called
`confirmed_defect` only when it ships with a complete proof packet and survives
independent human review.

The central rule:

> One confirmed false positive is an automatic evaluation failure.

The current workspace contains:

- Phase 95E human-review evidence;
- Phase 97A verification-evidence infrastructure;
- Phase 97C review-pilot evidence;
- Phase 97D calibration analysis;
- Phase 98A 24-repository corpus artifacts;
- a confirmed-defect shortest-path design.

No Phase 99 confirmed-defect gate implementation is currently present on disk.
Until that gate exists and passes this protocol, the score is:

```text
HOLD - not yet eligible for Defect Confirmation 7 / 10
```

This protocol evaluates confirmation quality separately from:

- review-lead usefulness;
- advisory volume;
- repository-understanding quality;
- impact-analysis usefulness;
- synthetic benchmark recall.

---

## 1. Why A Separate Protocol Is Required

### 1.1 Phase 95E established the review-lead baseline

Phase 95E reviewed `202` grounded findings from two public pilot repositories.

| Outcome | Count | Share |
| --- | ---: | ---: |
| Confirmed actionable defects | `0` | `0%` |
| Useful review leads | `148` | `73.3%` |
| Misleading findings | `15` | `7.4%` |
| Benign or not useful | `34` | `16.8%` |
| Unclear | `5` | `2.5%` |

The result supports:

```text
JARVIS can surface useful places to inspect.
```

It does not support:

```text
JARVIS can tell developers what is broken.
```

### 1.2 Phase 97C and 97D established the calibration risk

Phase 97C added verification evidence to `20` sampled `inconsistent_return`
review packets.

| Phase 97C signal | Result |
| --- | ---: |
| Verification evidence helped orient review | `20 / 20` |
| Confirmation clarity | `3.0 -> 4.0` |
| Overlay status `refuted` | `16 / 20` |
| Overlay status `blocked` | `4 / 20` |

Phase 97D then audited the reclassifications:

| Calibration result | Count |
| --- | ---: |
| Over-refutation | `12` |
| Correct reclassification | `2` |
| Unchanged | `6` |

This matters because confirmation has a mirror-image risk:

```text
weak evidence can over-refute
weak evidence can also over-confirm
```

The confirmed tier must therefore require a complete evidence bundle, not one
atom or one status flag.

### 1.3 Phase 98A established evaluation breadth

Phase 98A assembled and scanned a preregistered public corpus:

| Phase 98A metric | Value |
| --- | ---: |
| Repositories | `24` |
| Successful scans | `22` |
| Degraded scans | `2` |
| Unsafe scans | `0` |
| Total findings | `16,110` |
| Verdict-eligible findings | `8,832` |
| Advisory findings | `7,278` |
| Blinded review sample | `300` |
| Historical bug cases | `0` |
| Reviewed Phase 98A sample rows | `0` |

Phase 98A supplies the real-repository corpus and review workflow. It does not
yet supply confirmed-defect evidence because the sample is unlabeled and the
historical-bug track is empty.

---

## 2. Evaluation Object

### 2.1 Confirmed defect candidate

A **confirmed defect candidate** is a finding emitted by the future Phase 99
gate with:

```text
status: confirmed_defect
```

or an equivalent explicitly mapped status.

The candidate must include a complete proof packet.

### 2.2 Required proof packet

Every confirmed candidate must include:

```text
candidate_id
repository_id
pinned_revision
finding_id
rule
file
line
function

expected_contract
violating_condition
feasible_path
observable_consequence
supporting_evidence
refuting_evidence_considered
unresolved_edges
blockers
runtime_or_test_evidence
impact_context_optional

gate_version
evidence_schema_version
detector_version
```

Minimum semantic contents:

| Packet section | Required answer |
| --- | --- |
| Expected contract | What behavior is required? |
| Violating condition | Which concrete value, branch, state, or path violates it? |
| Feasible path | How does execution reach the violation? |
| Observable consequence | What incorrect behavior results? |
| Evidence | Which repository facts, test artifacts, or runtime artifacts support the claim? |
| Refutation review | Which guards, allowed outcomes, or conflicting facts were considered? |
| Unknowns | Which unresolved edges remain, and why do they not invalidate the claim? |

### 2.3 Incomplete packet rule

If a candidate lacks any required proof-packet section:

```text
automatic FAIL
```

It may remain a review lead. It may not remain confirmed.

### 2.4 Current implementation availability

At the time of this design:

- `verification_evidence.py` exists;
- evidence overlays exist;
- `EVIDENCE_PROMOTION_ENABLED = False`;
- no Phase 99 confirmed-defect gate implementation is present.

The protocol is ready to evaluate a future gate. It does not assume one exists.

---

## 3. Defect Confirmation Score Scale

### 3.1 Score interpretation

| Score | Meaning |
| ---: | --- |
| `0-4 / 10` | Review leads only; confirmed-defect claims unsupported |
| `5-6 / 10` | Candidate confirmation exists but corpus, precision, or reviewer evidence is insufficient |
| `7 / 10` | Narrow, trustworthy confirmed-defect tier with real historical validation |
| `8 / 10` | Broader, repeatable confirmed-defect tier with stronger recall and reviewer consistency |
| `9-10 / 10` | Not defined by this protocol; requires external workflow evidence and broader language/domain validation |

### 3.2 Why 7/10 is not perfection

`7 / 10` means:

- the confirmed tier is real;
- every claim is reviewable;
- precision is high;
- recall is measured but still limited;
- unresolved edges are visible;
- review leads remain separate.

It does not mean:

- JARVIS finds most bugs;
- JARVIS replaces code review;
- every repository is supported;
- repairs are generated or verified.

---

## 4. Definition Of 7 / 10

JARVIS reaches **Defect Confirmation 7 / 10** only when every hard gate below
passes.

### 4.1 Confirmed precision threshold

| Metric | Required |
| --- | ---: |
| Human-adjudicated confirmed precision | `100%` |
| Confirmed false positives | `0` |
| Reviewer-rejected confirmed candidates | `0` |

Formula:

```text
confirmed_precision =
  accepted_confirmed_candidates
  /
  reviewed_confirmed_candidates
```

The threshold is `100%`, not `90%`, for the first confirmed tier.

Reason:

- the label is intentionally strong;
- the candidate volume is expected to be small;
- Phase 97D showed how one weak witness can distort status;
- review leads already provide a lower-certainty escape hatch.

### 4.2 Misleading-rate threshold

| Metric | Required |
| --- | ---: |
| Confirmed-tier misleading rate | `0%` |
| Overall surfaced-output misleading rate | `< 5%` |

Formula:

```text
confirmed_misleading_rate =
  rejected_confirmed_candidates
  /
  reviewed_confirmed_candidates
```

The confirmed tier must remain perfect in the evaluation sample.

The broader developer surface may include retained leads, but its misleading
rate must stay below the Phase 95F external-alpha cap.

### 4.3 Minimum confirmed cases

| Metric | Required |
| --- | ---: |
| Human-accepted confirmed historical defects | At least `10` |
| Distinct repositories containing accepted confirmed defects | At least `5` |
| Distinct defect families | At least `3` |
| Buggy-to-fixed directional pairs | `100%` of confirmed historical cases |

Directional pair rule:

```text
buggy revision:
  confirmed_defect present

fixed revision:
  confirmed_defect absent, refuted, or explicitly blocked by changed evidence
```

A candidate that remains confirmed on the fixed revision is an automatic fail.

### 4.4 Recall threshold

| Metric | Required |
| --- | ---: |
| Confirmed recall on preregistered historical bugs | At least `25%` |

Formula:

```text
confirmed_recall =
  preregistered historical bug cases with accepted confirmed candidate
  /
  preregistered historical bug cases evaluated
```

The recall denominator includes misses. Do not filter the corpus after seeing
the result.

### 4.5 Reviewer agreement

| Metric | Required |
| --- | ---: |
| Two-reviewer exact agreement on confirmed vs not-confirmed | At least `90%` |
| Adjudication completion | `100%` |
| Reviewer agreement on proof-packet completeness | At least `90%` |

Reviewers must independently answer:

```text
Does this packet justify the confirmed-defect label?
```

Agreement is calculated before adjudication.

### 4.6 Real-repository safety sample

From the Phase 98A `300`-packet blinded sample:

| Metric | Required |
| --- | ---: |
| Human review completed | `300 / 300` |
| Confirmed false positives in sampled real-repo output | `0` |
| Hidden unresolved-edge failures | `0` |
| Unsupported confirmed claims | `0` |

The Phase 98A sample tests whether the gate stays silent when proof is missing.

---

## 5. Definition Of 8 / 10

JARVIS reaches **Defect Confirmation 8 / 10** only after passing every `7 / 10`
gate plus the stronger requirements below.

### 5.1 Confirmed precision threshold

| Metric | Required |
| --- | ---: |
| Human-adjudicated confirmed precision | `100%` |
| Confirmed false positives | `0` |
| Reviewer-rejected confirmed candidates | `0` |

Precision does not loosen at `8 / 10`.

### 5.2 Misleading-rate threshold

| Metric | Required |
| --- | ---: |
| Confirmed-tier misleading rate | `0%` |
| Overall surfaced-output misleading rate | `< 3%` |

### 5.3 Minimum confirmed cases

| Metric | Required |
| --- | ---: |
| Human-accepted confirmed historical defects | At least `20` |
| Distinct repositories containing accepted confirmed defects | At least `10` |
| Distinct defect families | At least `5` |
| Buggy-to-fixed directional pairs | `100%` |

### 5.4 Recall threshold

| Metric | Required |
| --- | ---: |
| Confirmed recall on preregistered historical bugs | At least `40%` |

### 5.5 Reviewer agreement

| Metric | Required |
| --- | ---: |
| Two-reviewer exact agreement on confirmed vs not-confirmed | At least `95%` |
| Adjudication completion | `100%` |
| Reviewer agreement on proof-packet completeness | At least `95%` |

### 5.6 Breadth and stability

| Metric | Required |
| --- | ---: |
| Phase 98A real-repo sample reviewed | `300 / 300` |
| Historical cases represented in Phase 98A corpus | At least `10` repositories |
| Repeated frozen reruns | At least `3` byte-stable gate-output runs |
| Gate version stability | Same gate version across final evaluation |
| Detector changes during evaluation | `0` |
| Tuning after preregistration | `0` |

### 5.7 Lead usefulness remains visible

At `8 / 10`, the product must still preserve useful uncertainty:

| Metric | Required |
| --- | ---: |
| Retained-review-lead usefulness | At least `60%` useful among reviewed retained leads |
| Refuted or blocked leads shown as confirmed | `0` |
| Appropriate unknown handling | `100%` on hidden-edge test cases |

The confirmed tier must not become trustworthy by deleting all non-confirmed
context.

---

## 6. Evaluation Corpus

The evaluation corpus has four mandatory tracks.

### 6.1 Track A - Known historical bugs

Purpose:

```text
Measure whether the confirmed tier fires on real defects.
```

Required for `7 / 10`:

- at least `30` preregistered historical bug cases;
- at least `10` repositories;
- at least `3` defect families;
- each case includes a buggy commit and a fixed commit.

Required for `8 / 10`:

- at least `50` preregistered historical bug cases;
- at least `15` repositories;
- at least `5` defect families.

Historical-case record:

```text
case_id
repository_id
repository_url
buggy_commit
fixed_commit
fix_commit
affected_files
affected_functions_if_known
defect_family
ground_truth_summary
ground_truth_source
test_or_reproduction_if_available
selection_rationale
```

Selection rules:

- preregister before scanning;
- use public issues, changelog entries, fix commits, or regression tests;
- include cases the current engine may miss;
- do not select only detector-friendly bugs;
- preserve misses in the denominator.

### 6.2 Track B - Fixed versions

Purpose:

```text
Measure whether the confirmed tier becomes silent when the defect is fixed.
```

Every Track A buggy revision must have a corresponding fixed revision.

Fixed-version outcome:

| Outcome | Interpretation |
| --- | --- |
| Candidate absent | Pass |
| Candidate explicitly refuted by changed evidence | Pass |
| Candidate blocked because proof is no longer complete | Pass, report separately |
| Candidate still confirmed | Automatic fail |

### 6.3 Track C - Phase 98A real-repository review sample

Purpose:

```text
Measure false confirmation, retained-lead usefulness, and unknown handling on
ordinary repository snapshots.
```

Use the frozen Phase 98A artifacts:

- `24` pinned repositories;
- `300` blinded review packets;
- `22` success scans;
- `2` degraded scans;
- `0` unsafe scans.

Review every sampled packet under the Phase 99 taxonomy:

- `confirmed_defect`
- `retained_review_lead`
- `security_review_lead`
- `advisory`
- `refuted`
- `blocked`
- `unknown`

The Phase 98A sample must not be silently resampled after seeing Phase 99
output. Preserve the existing sample and add a separate confirmed-candidate
overflow sample if needed.

### 6.4 Track D - Synthetic negative cases

Purpose:

```text
Prove that common tempting shortcuts do not create confirmed false positives.
```

Minimum negative fixture families:

| Family | Required negative case |
| --- | --- |
| Optional return | Explicit `Optional` return used intentionally |
| Guarded dereference | Dominating `if x is None: return` |
| Truthiness narrowing | `if not x: return` before use |
| Raise-only exit | Branch exits by `raise`, not implicit `None` |
| Expected negative test | `pytest.raises` or intentionally failing validation |
| Unresolved call | Critical dynamic dispatch or unresolved cross-file edge |
| Star import | Subject binding is ambiguous |
| Runtime assignment | Export or callable binding changes dynamically |
| Shadowed symbol | Imported name shadowed locally |
| Third-party boundary | Critical behavior lives outside project source |
| Impact-only evidence | Many dependents but no violated contract |
| Weak path witness | One `path.no_implicit_none_exit` atom without complete bundle |
| Stale runtime artifact | Revision mismatch |
| Flaky runtime artifact | Non-deterministic rerun |
| Security sink without hostile provenance | Constant argv list, no shell |

Every Track D fixture must result in:

```text
not confirmed
```

### 6.5 Existing benchmark track

Keep QuixBugs and holdout as regression guards:

| Corpus | Current result |
| --- | --- |
| QuixBugs | `12 TP / 0 FP` |
| Holdout | `2 TP / 0 FP` |

Do not treat these synthetic or curated corpora as substitutes for Track A.

They answer:

```text
Did existing detector behavior regress?
```

They do not answer:

```text
Does JARVIS confirm real production defects?
```

---

## 7. Human Review Workflow

### 7.1 Review roles

Use:

- Reviewer A;
- Reviewer B;
- adjudicator for disagreements.

Reviewers must be comfortable reading Python and must not see each other's
labels before submission.

### 7.2 Blinding

For each candidate packet, hide:

- whether source is buggy or fixed;
- historical-case label;
- detector expected result;
- other reviewer decision;
- aggregate metric progress;
- repository score.

Reviewers may see:

- source window;
- contract facts;
- verification evidence;
- path witness;
- unresolved edges;
- mapped test or runtime artifacts;
- impact context marked as non-proof.

### 7.3 Review questions

Every confirmed candidate receives answers to:

| Question | Response |
| --- | --- |
| Is the expected contract explicit and applicable? | yes / no / unclear |
| Is the violating condition concrete? | yes / no / unclear |
| Is the path feasible? | yes / no / partial / unclear |
| Are critical unresolved edges visible? | yes / no |
| Does any unresolved edge invalidate confirmation? | yes / no / unclear |
| Is the consequence observable and relevant? | yes / no / unclear |
| Is supporting evidence sufficient? | yes / no / unclear |
| Was refuting evidence considered? | yes / no / unclear |
| Is the confirmed-defect label justified? | yes / no |
| What is the rejection reason if not? | structured code + note |

### 7.4 Review labels

Use:

- `accepted_confirmed_defect`
- `rejected_false_confirmation`
- `retained_review_lead`
- `security_review_lead`
- `refuted`
- `blocked`
- `unknown`
- `out_of_scope`

### 7.5 Rejection reason codes

At minimum:

- `missing_contract`
- `missing_violating_condition`
- `missing_feasible_path`
- `missing_consequence`
- `missing_test_or_runtime_support`
- `hidden_unresolved_edge`
- `critical_unresolved_edge`
- `guard_refutes_path`
- `optional_behavior_allowed`
- `expected_negative_test`
- `stale_runtime_artifact`
- `flaky_runtime_artifact`
- `unsupported_claim`
- `wrong_subject_binding`
- `third_party_boundary`
- `impact_used_as_proof`
- `packet_incomplete`

### 7.6 Adjudication

Adjudicate:

- all Reviewer A/B disagreements;
- all confirmed candidates;
- all Track A misses sampled for quality review;
- all Track B candidates that remain visible;
- all cases with hidden or critical unresolved edges.

The adjudicator must record:

- final label;
- evidence basis;
- disagreement reason;
- whether the gate must be disabled;
- whether the protocol fails automatically.

---

## 8. Automatic Fail Conditions

The evaluation fails immediately when any condition below occurs.

### 8.1 Confirmed false positive

```text
Any reviewer-adjudicated rejected_false_confirmation
```

Automatic fail.

Do not average it away with correct cases.

### 8.2 Missing proof packet

```text
Any confirmed_defect without every required packet section
```

Automatic fail.

### 8.3 Hidden unresolved edge

```text
Any critical unresolved call, import, alias, or dynamic-dispatch edge omitted
from the confirmed packet
```

Automatic fail.

Visible unresolved edges do not always invalidate a claim. Hidden unresolved
edges always invalidate trust.

### 8.4 Unsupported claim

Automatic fail when a confirmed packet:

- treats impact as proof;
- claims a path is feasible when the witness is partial;
- treats `callee_behavior` alone as a contract guarantee;
- uses free-text docstring evidence as decisive proof;
- ignores explicit Optional behavior;
- ignores a dominating guard;
- ignores an expected negative test;
- relies on an unbound, stale, or flaky runtime artifact;
- claims third-party behavior without project-grounded evidence;
- fabricates a source path or function.

### 8.5 Fixed-version persistence

```text
Any Track A confirmed candidate remains confirmed on its Track B fixed revision
```

Automatic fail.

### 8.6 Synthetic-negative confirmation

```text
Any Track D synthetic negative fixture emits confirmed_defect
```

Automatic fail.

### 8.7 Evaluation integrity failure

Automatic fail when:

- corpus changes after preregistration;
- detectors change during evaluation;
- gate version changes during final measurement;
- tuning occurs after results are inspected;
- reviewer blinding is broken;
- target repositories are modified;
- target repository code is executed outside the approved artifact boundary.

---

## 9. Dashboard Metrics

### 9.1 Core confirmed-tier dashboard

| Metric | Formula | Why it matters |
| --- | --- | --- |
| Confirmed precision | `accepted_confirmed / reviewed_confirmed` | Trustworthiness of the strongest claim |
| False-confirmation rate | `rejected_confirmed / reviewed_confirmed` | Must remain `0` |
| Confirmed recall on known bugs | `historical_cases_confirmed / historical_cases_total` | Whether the tier finds meaningful real defects |
| Fixed-version clearance rate | `confirmed_buggy_cases_cleared_on_fixed / confirmed_buggy_cases` | Directionality and repair sensitivity |
| Proof-packet completeness | `complete_confirmed_packets / confirmed_packets` | Every claim must be inspectable |
| Hidden unresolved-edge count | Count | Must remain `0` |
| Unsupported confirmed-claim count | Count | Must remain `0` |

### 9.2 Review-lead dashboard

| Metric | Formula | Why it matters |
| --- | --- | --- |
| Review-lead usefulness | `useful_retained_leads / reviewed_retained_leads` | Measures value below confirmation threshold |
| Review-lead misleading rate | `misleading_retained_leads / reviewed_retained_leads` | Tracks triage burden |
| Refuted count | Count | Measures noise collapsed by negative evidence |
| Blocked count | Count by blocker reason | Shows missing proof infrastructure |
| Unknown count | Count by unresolved reason | Measures honest uncertainty |

### 9.3 Reviewer dashboard

| Metric | Formula |
| --- | --- |
| Confirmed-label reviewer agreement | `A/B exact confirmed-vs-not agreement / reviewed packets` |
| Packet-completeness agreement | `A/B exact agreement / reviewed confirmed candidates` |
| Adjudication count | Count |
| Adjudication rate | `adjudicated disagreements / reviewed packets` |
| Median review time | Minutes per packet |
| Review time by status | Confirmed / retained / refuted / blocked / unknown |

### 9.4 Corpus dashboard

| Metric | Required slices |
| --- | --- |
| Historical case count | By repository, defect family, size band |
| Confirmed recall | By defect family, repository, evidence type |
| Real-repo sample labels | By rule, kind, severity, repository |
| Synthetic-negative outcomes | By fixture family |
| Scan outcomes | Success / degraded / unsafe / failed |
| Evidence atom distribution | Type, polarity, strength |
| Critical unresolved edges | By resolution reason |

### 9.5 Dashboard separation rule

Never merge:

- confirmed precision;
- review-lead usefulness;
- synthetic benchmark precision;
- historical recall;
- real-repository misleading rate.

Each answers a different question.

---

## 10. Evaluation Sequence

Run the evaluation in this order.

### Step 1 - Freeze the candidate

Record:

- Builder Core commit;
- Phase 99 gate version;
- detector version;
- evidence schema version;
- feature flags;
- corpus manifest hash;
- review-sample hash;
- historical-case manifest hash;
- synthetic-negative fixture hash.

### Step 2 - Validate packet schema

Audit every emitted confirmed candidate:

- required fields present;
- deterministic serialization;
- repository-relative source paths;
- unresolved edges listed;
- secrets redacted;
- impact marked non-proof.

Any packet failure stops evaluation.

### Step 3 - Run Track D synthetic negatives

Required result:

```text
0 confirmed_defect
```

Any confirmation stops evaluation.

### Step 4 - Run Track A and Track B historical pairs

Measure:

- buggy-version confirmations;
- fixed-version clearance;
- misses;
- proof packet quality;
- evidence-type distribution.

Do not tune after seeing outcomes.

### Step 5 - Run Track C Phase 98A sample

Review the frozen `300` packets.

Measure:

- false confirmation;
- retained-lead usefulness;
- misleading rate;
- blocked and unknown reasons;
- degraded-repository behavior.

### Step 6 - Dual human review

Complete independent Reviewer A and Reviewer B passes.

### Step 7 - Adjudicate

Resolve disagreements and apply automatic fail rules.

### Step 8 - Publish dashboard

Publish:

- raw counts;
- denominators;
- corpus manifest;
- gate version;
- failures;
- unresolved edges;
- score verdict.

### Step 9 - Assign score

Assign:

- `< 7 / 10`
- `7 / 10`
- `8 / 10`

Do not round up.

---

## 11. Scorecard Template

### 11.1 7 / 10 checklist

| Gate | Target | Actual | Pass |
| --- | ---: | ---: | :---: |
| Confirmed precision | `100%` |  |  |
| Confirmed false positives | `0` |  |  |
| Confirmed-tier misleading rate | `0%` |  |  |
| Overall surfaced-output misleading rate | `< 5%` |  |  |
| Accepted confirmed historical defects | `>= 10` |  |  |
| Repositories with accepted confirmations | `>= 5` |  |  |
| Defect families | `>= 3` |  |  |
| Confirmed historical recall | `>= 25%` |  |  |
| Fixed-version directional clearance | `100%` |  |  |
| A/B confirmed-label agreement | `>= 90%` |  |  |
| Proof-packet completeness | `100%` |  |  |
| Phase 98A sample reviewed | `300 / 300` |  |  |
| Hidden unresolved edges | `0` |  |  |
| Unsupported claims | `0` |  |  |

### 11.2 8 / 10 checklist

| Gate | Target | Actual | Pass |
| --- | ---: | ---: | :---: |
| All `7 / 10` gates | Pass |  |  |
| Confirmed precision | `100%` |  |  |
| Overall surfaced-output misleading rate | `< 3%` |  |  |
| Accepted confirmed historical defects | `>= 20` |  |  |
| Repositories with accepted confirmations | `>= 10` |  |  |
| Defect families | `>= 5` |  |  |
| Confirmed historical recall | `>= 40%` |  |  |
| Fixed-version directional clearance | `100%` |  |  |
| A/B confirmed-label agreement | `>= 95%` |  |  |
| Proof-packet completeness agreement | `>= 95%` |  |  |
| Byte-stable frozen reruns | `>= 3` |  |  |
| Retained-review-lead usefulness | `>= 60%` |  |  |

---

## 12. Current Baseline Against This Protocol

Using currently available artifacts:

| Requirement | Current state |
| --- | --- |
| Phase 99 confirmed-defect gate | Not present on disk |
| Confirmed candidates | `0` |
| Accepted confirmed historical defects | `0` |
| Historical bug cases | `0` |
| Phase 98A repositories | `24 / 24` assembled and scanned |
| Phase 98A blinded packets | `300` generated |
| Phase 98A reviewed packets | `0 / 300` |
| Phase 95E pilot labels | Complete (`202 / 202`) |
| Phase 97C overlay pilot | Complete (`20 / 20`) |
| Phase 97D calibration analysis | Complete |

Current verdict:

```text
HOLD
Defect Confirmation score remains below 7 / 10.
```

The blocker is not repository breadth anymore. The blockers are:

1. no available Phase 99 confirmed-defect gate;
2. no preregistered historical buggy/fixed corpus;
3. no accepted confirmed cases;
4. Phase 98A review sample still unlabeled;
5. Phase 97D over-refutation calibration must be respected by any future gate.

---

## 13. Final Recommendation

Use this protocol as a hard release gate for the phrase:

```text
confirmed defect
```

Do not score JARVIS at `7 / 10` merely because:

- the overlay is implemented;
- findings have evidence atoms;
- benchmarks remain green;
- repository scans complete;
- review leads are useful.

Score `7 / 10` only when:

```text
real historical bugs are confirmed
  + fixed revisions clear
  + reviewers agree
  + ordinary real-repo scans produce zero false confirmations
  + every proof packet is complete
  + unresolved edges are visible
```

Score `8 / 10` only when the same trust level holds at greater breadth and
recall.

