# Confirmed Defect Acceleration Plan

Date: 2026-05-31

## Executive Recommendation

The fastest credible route from `0` confirmed defects to `100` historically
confirmed defects with `0` confirmed false positives is a proof-first historical
validation program, not another detector expansion.

The program should:

1. Reconcile the Phase 99 confirmation contract before enabling any gate.
2. Build a pre-registered corpus of buggy and fixed historical revisions.
3. Run the existing evidence engine in shadow mode against that corpus.
4. Expand confirmation eligibility one existing rule family at a time only when
   the family produces complete proof packets and survives negative controls.
5. Count a defect only after buggy-revision proof, fixed-revision clearance,
   packet completeness, and blinded human acceptance.

The practical target is a corpus of `300-400` pre-registered historical defects.
At a conservative `25-40%` confirmation recall, that range can yield `100`
accepted confirmations without weakening the standard.

## Current Evidence

### Phase 95E: Leads Are Not Confirmations

Phase 95E reviewed `202` grounded findings across two public repositories:

| Metric | Result |
| --- | ---: |
| Confirmed actionable defects | `0` |
| Useful review leads | `148 / 202` (`73.3%`) |
| Misleading findings | `15 / 202` (`7.4%`) |
| Unclear findings | `5 / 202` |

The existing analyzer is useful for review triage, but its raw findings cannot
be treated as confirmed defects.

### Phase 97C and 97D: Evidence Can Mislead in Both Directions

Phase 97C enriched `20` sampled `inconsistent_return` cases with verification
evidence. Review orientation improved, but the overlay classified `16` cases as
`refuted` and `4` as `blocked`.

Phase 97D then audited the changed labels:

| Metric | Result |
| --- | ---: |
| Changed labels audited | `14` |
| Correct reclassifications | `2` |
| Over-refutations | `12` |

The main failure was a single weak `path.no_implicit_none_exit` witness driving
a global `refuted` status. The lesson is important: conservative confirmation
does not justify aggressive refutation. Weak evidence should enrich a packet,
not silently determine its verdict.

### Phase 98A: Breadth Exists, Ground Truth Does Not

Phase 98A assembled and scanned `24` pinned public Python repositories:

| Metric | Result |
| --- | ---: |
| Successful repositories | `22` |
| Degraded repositories | `2` |
| Unsafe repositories | `0` |
| Findings | `16,110` |
| Verdict-eligible grounded findings | `8,832` |
| Advisory findings | `7,278` |
| Blinded review packets | `300` |
| Historical bug cases | `0` |

The `300` packets are useful for misleading-rate and lead-usefulness
measurement. They cannot establish historical confirmation recall because the
historical corpus is empty.

### Phase 99 and 99A: Confirmation Infrastructure Exists, but Its Contract Is Not Yet Settled

Phase 99 designed a strict, default-off `confirmed_defect` gate for
`inconsistent_return`. Its required conditions include an executable witness:
a bound failing test or runtime reproduction.

Phase 99A implemented default-off infrastructure, but its executable-support
rule is broader than the design. It can accept either:

- `test_evidence` or `runtime_reproduction_evidence`, or
- `contract_violation_evidence` paired with a feasible path.

That second branch is not equivalent to an executable witness. It may be useful
supporting evidence, but it should not independently satisfy the confirmation
gate until validated under a revised protocol. The gate remains disabled by
default, so this is a repairable shadow-mode issue rather than a production
incident.

Phase 99B provides the right evaluation discipline:

- `0` confirmed false positives.
- Complete proof packets.
- Buggy-to-fixed directional clearance.
- Negative controls.
- Reviewer agreement.
- Automatic failure for unsupported claims or hidden unresolved edges.

Its implementation-status wording should be refreshed because Phase 99A now
exists.

## Definition of a Counted Confirmation

A case counts toward the target of `100` only when all of the following are
true:

1. The historical defect was selected and recorded before JARVIS scans it.
2. The buggy revision and fixed revision are pinned.
3. The historical source is recorded: issue, pull request, commit, changelog, or
   regression test.
4. JARVIS produces a complete proof packet on the buggy revision.
5. The proof packet includes a bound failing test or runtime reproduction.
6. The claimed consequence is observable and tied to a feasible path.
7. No unresolved edge, visible guard, unsupported inference, or conflicting
   evidence survives.
8. The same confirmation clears on the fixed revision.
9. Two blinded reviewers accept the defect classification, with adjudication
   for disagreement.

A plausible finding, a contract mismatch, a feasible path, or a useful review
lead does not count by itself.

## Corpus Math

The required corpus size depends on conservative confirmation recall:

| Confirmation recall | Historical cases needed for `100` confirmations |
| --- | ---: |
| `20%` | `500` |
| `25%` | `400` |
| `33%` | `304` |
| `40%` | `250` |
| `50%` | `200` |

The planning assumption should be `25-40%`, not the optimistic `50%`. A
`300-400` case corpus is therefore the smallest responsible target range.

The corpus must be divided before scanning:

| Cohort | Purpose | Suggested size |
| --- | --- | ---: |
| Calibration cohort | Tune packet semantics and family gates in shadow mode | `75-100` |
| Locked evaluation cohort | Measure the final target without contamination | `250-350` |
| Synthetic and hand-checked negatives | Exercise false-confirmation controls | `50-100` |
| Phase 98A frozen review sample | Measure misleading rate and retained usefulness | `300` packets |

Calibration confirmations should be reported separately. The final claim of
`100` historically confirmed defects should be earned from locked cases, or
clearly disclose any calibration cases counted.

## Bottlenecks

### 1. Historical Ground Truth Acquisition

This is the dominant bottleneck. The current real-repository corpus contains
`0` historical bug cases. Each new case needs a pinned buggy revision, pinned
fixed revision, public source of truth, and preferably a regression test or
reproducible failure.

### 2. Executable Evidence Supply

The current evidence system is better at generating review context than bound
proof. The strict gate will remain empty unless historical cases include tests
or reproducible executions that can be tied to a finding.

### 3. Phase 99 Contract Drift

Phase 99 requires executable proof. Phase 99A can accept a static
contract-violation and feasible-path pair as executable support. Scaling before
reconciling this difference risks inflating confirmation counts with
insufficient proof.

### 4. Over-Refutation Calibration

Phase 97D showed that weak path evidence can incorrectly suppress useful cases.
The acceleration path needs precise confirmation without allowing weak
refutation atoms to hide real candidates.

### 5. Rule-Family Coverage

Phase 99A is intentionally limited to `inconsistent_return`. That is a good
first safety boundary, but it is unlikely to yield `100` historical
confirmations alone. After calibration, confirmation eligibility must widen
only across existing rule families that already have proof-ready evidence.

### 6. Human Review Capacity

The final claim requires dual review, fixed-version clearance, negative
controls, and adjudication. Automated scanning is cheap relative to curating
and reviewing trustworthy evidence.

## Effort Estimate

### Base Estimate

| Workstream | Estimated effort |
| --- | ---: |
| Reconcile confirmation semantics and Phase 97D calibration | `4-7` engineer-days |
| Curate `300-400` historical buggy/fixed cases | `225-450` curator-hours |
| Bind tests or runtime reproductions and validate manifests | `80-160` engineer-hours |
| Shadow runs, deterministic exports, and negative controls | `8-15` engineer-days |
| Dual review, adjudication, and fixed-version audits | `120-220` reviewer-hours |
| Final report and integrity audit | `3-5` engineer-days |

Total base effort: approximately `500-900` person-hours.

With two engineers and two part-time reviewers or curators working in parallel,
the realistic calendar range is `8-12` weeks. A focused five-person effort can
compress this to roughly `6-9` weeks. A solo effort is more likely to require
`14-24` weeks.

### Diminishing-Return Point

The program should reassess after the first `100` calibration cases. If fewer
than `10` cases produce complete, reviewer-accepted proof packets, the limiting
factor is executable evidence binding or existing rule coverage. At that point,
adding more historical cases without fixing the evidence bottleneck wastes
curation effort.

## Work to Defer

The following work is unnecessary for the shortest path to `100` confirmed
historical defects:

- New detectors.
- Benchmark recall tuning.
- New repository-understanding features.
- New dependency-graph features unless a concrete proof packet requires them.
- Broad root-cause narration.
- Repair generation.
- Repair validation.
- Autonomous code changes.
- LLM reasoning.
- Scanning more unlabelled repositories merely to increase finding volume.
- Human review of all `8,832` Phase 98A grounded findings.
- Broad promotion of every rule family at once.
- External-alpha expansion before the confirmation protocol has passed its
  locked evaluation.

Phase 98A's frozen `300` packets remain valuable for usefulness and misleading
rate. They should not be mistaken for the historical-defect corpus.

## Next Five Phases Only

### Phase 99C - Confirmation Contract Reconciliation

**Goal:** Make the Phase 99 implementation match a single explicit confirmation
standard before any count is trusted.

**Scope:**

- Decide whether `contract_violation_evidence + feasible path` is supporting
  evidence or independently confirmatory evidence.
- Preserve the stricter rule by default: executable test or runtime
  reproduction is required for `confirmed_defect`.
- Apply Phase 97D calibration so weak path witnesses cannot globally refute a
  pattern finding.
- Require a resolved observable consequence, empty proof obligations, and
  explicit unresolved-edge checks.
- Refresh the Phase 99B protocol wording to acknowledge Phase 99A.
- Keep all confirmation flags default-off.

**Effort:** `4-7` engineer-days plus `1-2` reviewer-days.

**Exit gate:** Shadow packets have one stable taxonomy, byte-stable exports, and
no path from weak static evidence alone to `confirmed_defect`.

### Phase 100A - Historical Corpus Factory

**Goal:** Build the preregistered evidence source that Phase 98A does not have.

**Scope:**

- Curate `75-100` calibration cases and `250-350` locked evaluation cases.
- Pin buggy and fixed commits.
- Record public source-of-truth links and defect families before scanning.
- Prefer historical defects with existing regression tests or compact runtime
  reproductions.
- Create `50-100` negative controls, including fixed revisions and hand-checked
  synthetic negatives.
- Use repositories with public issue history and runnable tests; reuse Phase
  98A repositories where suitable, then supplement them.

**Effort:** `225-450` curator-hours, parallelizable.

**Exit gate:** Every case has a frozen manifest, provenance, buggy revision,
fixed revision, and review-ready expected behavior. The locked cohort remains
unscanned until calibration is frozen.

### Phase 100B - Shadow Calibration and First Ten Confirmations

**Goal:** Prove the full protocol end to end without widening semantics.

**Scope:**

- Run the reconciled gate in shadow mode on the calibration cohort.
- Dual-review every proposed confirmation.
- Check every accepted case against its fixed revision.
- Run negative controls and the frozen Phase 98A `300`-packet misleading-rate
  sample.
- Measure proof-packet completeness, reviewer agreement, confirmation recall,
  false-confirmation rate, and retained lead usefulness.

**Effort:** `5-8` engineer-days plus `40-70` reviewer-hours.

**Exit gate:** At least `10` accepted historical confirmations, `0` confirmed
false positives, `100%` fixed-version clearance, and no missing proof packets.
If fewer than `10` cases confirm from `100` calibration cases, stop and diagnose
evidence supply before adding volume.

### Phase 100C - Proof-Gated Existing-Family Expansion

**Goal:** Reach `50` accepted historical confirmations without adding
detectors or weakening proof.

**Scope:**

- Rank existing rule families by historical case supply and proof readiness.
- Admit one existing family at a time.
- Require each family to pass its own buggy/fixed pairs, negative controls,
  packet-completeness review, and blinded reviewer audit.
- Quarantine any family after one confirmed false positive or one unsupported
  confirmation.
- Keep advisory findings advisory.

**Effort:** `10-20` engineer-days plus `50-90` reviewer-hours.

**Exit gate:** At least `50` accepted historical confirmations across multiple
repositories and rule families, `0` confirmed false positives, and no
regression in Phase 98A misleading rate.

### Phase 100D - Locked Hundred-Defect Evaluation

**Goal:** Produce the defensible `100`-defect result.

**Scope:**

- Freeze code, family policies, thresholds, and manifests.
- Run the untouched locked evaluation cohort.
- Require dual blinded review and adjudication.
- Re-run fixed revisions and negative controls.
- Audit hidden unresolved edges, unsupported claims, proof packet completeness,
  deterministic exports, and corpus integrity.
- Report confirmed precision, confirmation recall on known bugs, reviewer
  agreement, retained lead usefulness, misleading rate, and per-family results.

**Effort:** `5-8` engineer-days plus `70-120` reviewer-hours.

**Exit gate:** `100` accepted historically confirmed defects, `0` confirmed
false positives, complete proof packets, `100%` fixed-version directional
clearance, and no unsupported confirmation claims.

## Fastest Safe Operating Model

Use a funnel rather than reviewing everything:

1. Curate cases before scanning.
2. Scan all buggy and fixed revisions deterministically.
3. Automatically reject incomplete proof packets.
4. Dual-review proposed confirmations, fixed-version survivors, negative
   controls, and a representative sample of misses.
5. Continue to review the frozen Phase 98A `300` packets for misleading-rate
   and usefulness measurement.
6. Expand only when the prior family has passed.

This concentrates expensive human time where it changes the confidence of the
final claim.

## Decision Rule

Proceed if Phase 99C restores a strict proof contract and Phase 100B produces at
least `10` accepted confirmations from the calibration cohort with `0`
confirmed false positives.

Pause the scale-up if any of the following occurs:

- One confirmed false positive.
- A confirmation without executable test or runtime evidence.
- A fixed revision remains confirmed.
- A hidden unresolved edge invalidates a packet.
- Reviewer disagreement reveals an ambiguous classification rule.
- Calibration yield is below `10%`.

The fastest route is disciplined because the target is unusually strict. A
smaller, honest confirmed tier that scales through pre-registered historical
proof is materially faster than producing a larger number that later has to be
unwound.
