# Minimum Path to 100 Confirmed Historical Defects

Date: 2026-05-31

## Executive Answer

The minimum path is not a new analysis program. Most of the required foundation
already exists:

- Phase 98A provides the frozen real-repository validation corpus and `300`
  blinded review packets.
- Phase 99 defines the strict confirmation contract.
- Phase 99A provides a default-off confirmation gate.
- Phase 99B defines the evaluation protocol.
- Phase 99C defines the historical buggy/fixed corpus format.
- Phase 99D provides an explicit, default-off read-only replay harness.

The remaining work is four tightly scoped packages:

1. Align the implemented gate with the strict Phase 99 proof contract and apply
   the Phase 97D calibration rule.
2. Bind developer-controlled fail-on-buggy/pass-on-fixed test or runtime
   artifacts into replay packets.
3. Curate rolling preregistered historical batches until `100` cases survive the
   strict gate, fixed-version clearance, and human adjudication.
4. Run the frozen Phase 99B evaluation: historical pairs, matched fixed
   revisions, hard negatives, and the existing Phase 98A `300`-packet sample.

The mathematical minimum is `100` accepted historical buggy/fixed pairs. The
realistic sourcing volume is `250-400` preregistered historical candidates
because some cases will be detector misses, lack bindable executable witnesses,
or remain honest review leads.

No new detectors, benchmarks, repository-understanding features, repair
systems, or autonomous execution paths are required.

## Current State

### Evidence Summary

| Phase | What exists | What it proves | Remaining gap |
| --- | --- | --- | --- |
| `95E` | Dual-reviewed pilot: `202` findings, `148` useful leads, `15` misleading, `0` confirmed actionable defects | Current findings are useful for triage | Review leads are not confirmed defects |
| `97D` | Calibration audit: `12 / 14` changed labels were over-refutations | Weak evidence can distort verdicts | A weak path witness must not globally refute or confirm |
| `98A` | `24` pinned repositories, `16,110` findings, `300` blinded packets | Real-repository scanning breadth exists | Historical cases remain `0`; packets remain unlabeled |
| `99` | Strict confirmation design | Defines proof required for the phrase `confirmed defect` | Design must govern implementation |
| `99A` | Default-off `inconsistent_return` confirmation infrastructure | A replay-only confirmation overlay exists | Implemented support rule is broader than Phase 99 design |
| `99B` | Strict evaluation protocol | Defines zero-false-confirmation measurement | Protocol wording is stale about Phase 99A availability |
| `99C` | Historical corpus design | Defines buggy/fixed pairs, trigger tests, packets, preregistration | Corpus has not been populated |
| `99D` | Default-off replay harness | Reads buggy/fixed snapshots and measures gate classifications | Replay does not itself verify executable trigger tests |

### What Is Already Done

Do not rebuild:

- The real-repository scan harness.
- The dual-review workflow.
- The confirmation taxonomy.
- The historical pair manifest concept.
- The read-only Git and file replay machinery.
- The default-off safety boundary.
- QuixBugs and holdout regression guards.

## Non-Negotiable Count Rule

A defect counts toward `100` only when all conditions below hold:

1. The case was preregistered before JARVIS scanned it.
2. The buggy revision and fixed revision are pinned.
3. A public historical source identifies the defect and fix.
4. JARVIS emits a complete proof packet on the buggy revision.
5. The packet includes a bound failing test or runtime reproduction.
6. The violating path is feasible.
7. The observable consequence is explicit.
8. No hidden unresolved edge, visible guard, unsupported inference, or
   conflicting evidence survives.
9. The same confirmation clears on the fixed revision.
10. Two blinded reviewers accept the packet, with adjudication completed.

The following do **not** count by themselves:

- A useful review lead.
- A detector hit.
- A contract mismatch.
- A feasible path.
- A static `contract_violation_evidence + path_feasibility_evidence` pair.
- A QuixBugs or synthetic benchmark true positive.
- A manually selected case added after observing gate output.

## The Minimum Work

### Work Package 1: Reconcile the Confirmation Contract

Phase 99 and Phase 99A are not fully aligned.

Phase 99 requires:

```text
bound failing test OR runtime reproduction
```

Phase 99A can also accept:

```text
contract_violation_evidence + feasible path
```

That static pair is useful supporting evidence, but it is not executable proof.
The minimum safe correction is:

1. Require a bound failing test or runtime reproduction for
   `confirmed_defect`.
2. Keep static contract and path evidence as prerequisites or supporting
   evidence.
3. Require the resolved observable consequence described by Phase 99.
4. Require proof obligations and unresolved-edge checks to be empty.
5. Apply Phase 97D calibration: one weak `path.no_implicit_none_exit` witness
   must not globally refute a pattern finding.
6. Keep both feature flags default-off outside explicit replay.
7. Refresh Phase 99B's stale implementation-status wording.

This is the only confirmation-semantics change required before corpus work can
produce trustworthy numbers.

### Work Package 2: Bind Executable Witness Artifacts to Replay

Phase 99D already provides read-only source replay. It intentionally does not
execute analyzed code. That boundary should remain.

The minimum missing bridge is evidence ingestion:

1. Run declared trigger tests or runtime reproductions under developer control
   outside implicit analysis.
2. Record the pinned revision, command, result, output hash, and binding to the
   affected function or finding.
3. Verify `fail-on-buggy / pass-on-fixed`.
4. Import the resulting artifact into the replay packet as bound
   `test_evidence` or `runtime_reproduction_evidence`.
5. Reject stale, flaky, unbound, or revision-mismatched artifacts.

Do **not** build a broad autonomous execution system. The minimum path needs a
small declared-artifact boundary, not general target-repository execution.

### Work Package 3: Build Rolling Preregistered Historical Batches

Instantiate the Phase 99C design in rolling frozen batches.

Each batch should be:

- Selected from public BugsInPy cases and public bug-fix commits.
- Frozen before scanning.
- Version-pinned.
- Labeled with provenance.
- Paired buggy/fixed.
- Supplied with a verified executable witness where confirmation eligibility is
  expected.
- Dual-reviewed before counting.

Start with `30-50` cases per batch. After each batch:

1. Run replay without tuning.
2. Count accepted buggy-only confirmations.
3. Record detector misses and insufficient-proof cases honestly.
4. Add the next preregistered batch only if the evidence yield justifies more
   curation.
5. Stop when the cumulative accepted count reaches `100`.

This rolling approach avoids curating hundreds of cases unnecessarily while
preserving preregistration discipline.

### Work Package 4: Run the Frozen Evaluation

Use the Phase 99B protocol without widening it.

Required tracks:

| Track | Minimum required work |
| --- | --- |
| Historical positives | Replay preregistered buggy revisions until `100` packets are accepted |
| Matched negatives | Replay the fixed revision for every counted historical defect |
| Hard negatives | Replay optional-by-design, guarded, stale-artifact, flaky-artifact, unresolved-edge, and unsupported-claim cases |
| Ordinary snapshots | Review the existing frozen Phase 98A `300` packets under the confirmation taxonomy |
| Regression guards | Keep QuixBugs and holdout unchanged |

Publish:

- Accepted historical confirmations.
- Confirmed false positives.
- Historical confirmation recall.
- Fixed-version clearance.
- Proof-packet completeness.
- Hidden unresolved-edge count.
- Unsupported-claim count.
- Reviewer agreement and adjudication count.
- Results by repository and existing rule family.

## Corpus Size: Lower Bound and Realistic Plan

### Mathematical Minimum

The absolute lower bound is:

| Artifact | Minimum |
| --- | ---: |
| Accepted historical buggy cases | `100` |
| Matched fixed revisions | `100` |
| Complete proof packets | `100` |
| Accepted dual-reviewed confirmations | `100` |
| Confirmed false positives | `0` |

This lower bound assumes every curated positive is detected, has a bindable
witness, survives proof obligations, clears on fixed, and passes review. That is
not a realistic planning assumption.

### Realistic Sourcing Volume

| Conservative confirmation yield | Historical candidates required for `100` accepted confirmations |
| --- | ---: |
| `25%` | `400` |
| `33%` | `304` |
| `40%` | `250` |
| `50%` | `200` |

Use `250-400` candidates as the planning range, but curate in frozen batches and
stop once `100` accepted confirmations exist.

### Existing-Rule Breadth

Phase 99C explicitly warns that real `inconsistent_return` defects are scarce.
The practical path will probably require multiple **existing** rule families.

The minimum safe widening policy is:

1. Begin with `inconsistent_return`.
2. Admit another existing rule family only when a preregistered batch contains
   proof-ready historical cases for that family.
3. Apply the same strict packet and fixed-version rules.
4. Quarantine the family immediately after one false confirmation.
5. Add no new detector merely to improve the count.

The current reports do not justify selecting a fixed list of families in
advance. Family eligibility should follow verified historical evidence supply,
not desired metrics.

## Effort Estimate

| Work | Estimate |
| --- | ---: |
| Gate alignment and Phase 97D calibration | `4-7` engineer-days |
| Executable artifact ingestion and binding | `4-8` engineer-days |
| Rolling historical corpus curation | `225-450` curator-hours |
| Existing-family eligibility, one family at a time | `8-20` engineer-days |
| Replay runs, deterministic exports, and negative controls | `5-10` engineer-days |
| Dual review, fixed-version audit, Phase 98A packet review, adjudication | `120-220` reviewer-hours |
| Final integrity report | `2-4` engineer-days |

Expected total: approximately `500-900` person-hours.

The dominant cost is historical case curation and review, not scanning. Phase
98A scanned `24` repositories in about eight minutes. More compute does not
remove the ground-truth bottleneck.

## Bottlenecks

### 1. Proof-Ready Historical Cases

The current corpus has `0` historical bug cases. Real defects with pinned
buggy/fixed revisions and bindable trigger tests are the scarce asset.

### 2. Executable Witness Binding

Phase 99 requires executable proof. Phase 99D supplies replay, but not automatic
verification of trigger-test execution. Without the artifact bridge, replay can
measure classifications but cannot establish strict confirmation.

### 3. Gate Contract Drift

Static contract-and-path evidence must not be mistaken for executable support.
This must be corrected before counts are trusted.

### 4. Single-Family Scarcity

The first gate covers only `inconsistent_return`. Reaching `100` will probably
require careful eligibility for additional existing rule families.

### 5. Human Review Throughput

Zero confirmed false positives requires blinded review, fixed-version checks,
and adjudication. This cannot be replaced with aggregate benchmark precision.

## Work That Is Not Required

Do not spend time on:

- New detectors.
- New benchmark rules or tuning.
- New algorithm profiles.
- New repository-understanding features.
- New dependency-graph features unless a proof packet exposes one concrete
  missing edge.
- Broad root-cause narration.
- Repair suggestions.
- Repair generation.
- Repair verification.
- Autonomous execution.
- LLM reasoning.
- Scanning additional unlabeled repositories for finding volume.
- Reviewing all `8,832` Phase 98A grounded findings.
- Replacing the existing replay harness.
- A general-purpose sandbox before the declared-artifact path is proven
  insufficient.
- Surfacing confirmed labels in production before the frozen evaluation passes.

## Required Safety Stops

Stop the program immediately if any of the following occurs:

- One adjudicated confirmed false positive.
- One counted packet without a bound failing test or runtime reproduction.
- One confirmation that persists on its fixed revision.
- One hidden critical unresolved edge.
- One unsupported consequence claim.
- One stale or flaky executable artifact accepted as proof.
- One gate-version or detector change after a batch is preregistered.
- One target-repository modification outside the declared test boundary.

Do not average these failures away.

## Minimum Completion Checklist

The goal is reached only when:

| Requirement | Target |
| --- | ---: |
| Human-accepted historical confirmations | `100` |
| Confirmed false positives | `0` |
| Complete proof packets | `100%` |
| Bound failing test or runtime reproduction | `100%` |
| Fixed-version directional clearance | `100%` |
| Hidden unresolved edges | `0` |
| Unsupported confirmation claims | `0` |
| Hard-negative confirmations | `0` |
| Phase 98A frozen sample reviewed | `300 / 300` |
| Reviewer disagreements adjudicated | `100%` |
| QuixBugs and holdout regressions | `0` |
| Production confirmation flags | default-off until evaluation passes |

## Bottom Line

The minimum path is deliberately narrow:

```text
strict gate alignment
  -> declared executable-artifact binding
  -> rolling preregistered buggy/fixed batches
  -> replay + blinded adjudication
  -> stop at 100 accepted buggy-only confirmations
```

The fastest trustworthy program reuses Phase 99C and Phase 99D, limits new work
to proof binding and gate alignment, and spends most of its effort on historical
ground truth. The goal is not to manufacture a larger confirmed tier. It is to
earn exactly `100` claims that remain defensible when every one is inspected.
