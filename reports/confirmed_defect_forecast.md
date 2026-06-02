# Confirmed Defect Forecast

Date: 2026-05-31

## Forecast Status

This is a conditional forecast, not a measured post-phase result.

No Phase 99F or Phase 100A completion reports are currently present in the
workspace. The forecast therefore assumes:

### Assumed Phase 99F Outcome

- The Phase 99A implementation has been aligned with the approved Phase 99
  `C1-C6` confirmation contract.
- A bound failing test or runtime reproduction is required for
  `confirmed_defect`.
- Static `contract_violation_evidence + feasible path` remains supporting
  evidence, not executable proof.
- Observable consequence, empty proof obligations, and unresolved-edge checks
  are required.
- Phase 97D weak-witness over-refutation is calibrated.
- Confirmation remains default-off outside explicit shadow or replay sessions.

### Assumed Phase 100A Outcome

- The Phase 100 historical-confirmation workflow is operational.
- Declared trigger tests or runtime artifacts can be bound to pinned buggy and
  fixed revisions.
- Replay verifies `fail-on-buggy / pass-on-fixed`.
- Historically proven packets require directional clearance, fix-site
  identity, witness flip, complete packet validation, and blinded human
  acceptance.
- Rolling preregistered historical batches can be processed without tuning
  after results are inspected.

These assumptions remove the infrastructure bottleneck. They do not create a
measured historical corpus yield.

## Evidence Used

| Evidence | Observed result | Forecast implication |
| --- | ---: | --- |
| Phase 95E real-repository pilot | `0` confirmed defects, `73.3%` useful leads, `7.4%` misleading | Raw findings cannot be treated as confirmations |
| Phase 97D calibration audit | `12 / 14` changed labels were over-refutations | Strict packet semantics are necessary; weak atoms cannot drive verdicts |
| Phase 98A real-repository run | `24` repositories, `300` blinded packets, `0` historical cases | Scanning capacity exists; labeled historical supply is missing |
| QuixBugs regression guard | `12 / 40` true positives, `0` false positives | Existing intelligence is precision-first with incomplete recall |
| Holdout regression guard | `2 / 12` true positives, `0` false positives | Recall varies materially outside the primary benchmark |
| Phase 99C corpus design | Real `inconsistent_return` positives are expected to be scarce | One rule family is unlikely to supply `100` confirmations |
| Phase 100 design | Historically proven requires buggy-to-fixed differential plus witness flip | Precision should be high; recall must fall when proof is incomplete |

## 1. Expected Confirmed Precision

### Forecast

| Metric | Expected result |
| --- | ---: |
| Pre-adjudication historically proven candidate precision | `97-100%` |
| Human-adjudicated historically confirmed precision | `100%` target; expected `99-100%` |
| Permitted confirmed false positives for the program goal | `0` |

The honest operational expectation is:

```text
accepted confirmed precision: 100%
```

This does not mean every candidate will be correct. It means the system should
demote or reject uncertain candidates before they are counted. A single
adjudicated false confirmation is an automatic stop, not an acceptable average.

### Why Precision Should Be High

Historically proven status is multiplicative:

```text
strict Phase 99 packet
  + executable witness
  + buggy-only confirmation
  + fixed-version clearance
  + fix-site identity
  + witness flip
  + hidden-edge audit
  + blinded human acceptance
```

Each gate removes volume. That is the intended trade.

### Confidence

Confidence in the precision forecast is **moderate**, not high, until a locked
historical corpus has been run. Phase 97D demonstrated that status semantics can
look convincing while still being wrong. The safeguards are strong, but they
must be measured.

## 2. Expected Confirmed Recall

Recall needs two separate views.

### End-to-End Historical Recall

This is the product-relevant number:

```text
accepted historically confirmed defects
/
all preregistered historical defects
```

| Scenario | Expected end-to-end recall |
| --- | ---: |
| Conservative | `20-25%` |
| Base forecast | `25-35%` |
| Optimistic after careful existing-family expansion | `35-40%` |

Use `30%` as the planning estimate.

### Gate Recall on Proof-Eligible Candidates

This narrower metric excludes detector misses and cases without a bindable
witness:

```text
accepted historically confirmed defects
/
detector-fired historical cases with a valid bound witness
```

| Scenario | Expected gate recall |
| --- | ---: |
| Conservative | `50-60%` |
| Base forecast | `60-75%` |
| Optimistic | `75-85%` |

The gap between the two recall measures is the heart of the next phase of work.
The strict gate may perform well on proof-ready candidates while end-to-end
recall remains limited by detector coverage, rule-family eligibility, and
historical witness availability.

### Why Recall Should Remain Modest

- QuixBugs recall is `30%`.
- Holdout recall is `16.7%`.
- The confirmation tier is stricter than either benchmark.
- Phase 99 begins with `inconsistent_return` only.
- Phase 99C expects genuine `inconsistent_return` positives to be scarce.
- Cases without complete proof must remain `strong_suspect` or `review_lead`.

The correct forecast is a narrow, trustworthy confirmed tier, not broad
coverage.

## 3. Expected Time to Milestones

### Planning Assumptions

The timing model assumes:

- Phase 99F and 100A are complete before the clock starts.
- Historical cases are curated in frozen batches of `30-50`.
- Average accepted-confirmation yield is `30%`.
- Case sourcing, pinning, provenance, witness verification, replay, and packet
  review average `1.5-2.5` human-hours per preregistered historical case.
- Dual review and adjudication add `0.5-1.0` human-hour per accepted confirmed
  packet.
- Replay compute time is minor compared with curation and review.
- A small parallel team is available: two engineers plus two part-time
  curators or reviewers.

### Base Forecast

| Milestone | Cases likely required at `30%` yield | Human effort after 99F/100A | Small-team calendar time | Solo calendar time |
| --- | ---: | ---: | ---: | ---: |
| `10` confirmed defects | `34` | `70-110` hours | `1-2` weeks | `2-4` weeks |
| `50` confirmed defects | `167` | `320-520` hours | `4-7` weeks | `9-15` weeks |
| `100` confirmed defects | `334` | `650-1,000` hours | `8-13` weeks | `18-28` weeks |

### Range by Recall

| Milestone | At `20%` yield | At `30%` yield | At `40%` yield |
| --- | ---: | ---: | ---: |
| `10` confirmations | `50` cases | `34` cases | `25` cases |
| `50` confirmations | `250` cases | `167` cases | `125` cases |
| `100` confirmations | `500` cases | `334` cases | `250` cases |

### Practical Interpretation

The first `10` confirmations should be treated as the calibration checkpoint.
They establish whether the post-100A workflow actually yields complete packets
without false confirmations.

The path from `10` to `50` is mostly corpus operations:

- acquire cases;
- pin revisions;
- reproduce witnesses;
- replay;
- review;
- adjudicate.

The path from `50` to `100` is where rule-family scarcity is likely to become
visible. If the yield falls below `20%`, continuing to source cases without
understanding the miss distribution becomes wasteful.

## 4. Next Bottleneck

### Immediate Bottleneck: Proof-Ready Historical Case Throughput

Assuming 99F and 100A are complete, the next bottleneck is:

```text
finding enough preregistered historical bugs with:
  pinned buggy and fixed revisions
  + reproducible fail-on-buggy/pass-on-fixed witness
  + detector hit
  + complete proof packet
  + fixed-version clearance
```

The system can scan repositories quickly. Phase 98A processed `24`
repositories in about eight minutes. Compute is not the limiting resource.

The scarce resource is a clean historical case that survives every proof gate.

### Likely Secondary Bottleneck: Existing Rule-Family Coverage

After the first `10-30` accepted confirmations, the throughput bottleneck will
likely expose a coverage ceiling:

- `inconsistent_return` alone is unlikely to supply `100` historical positives;
- some sourced historical defects will be detector misses;
- some detector hits will lack a complete observable consequence;
- some witnesses will not bind cleanly to the finding;
- some cases will correctly remain `strong_suspect`.

The response should not be new detector work by default. First measure the miss
distribution. Then admit additional **existing** rule families one at a time,
using the same zero-false-confirmation gates.

## 5. Decision Checkpoints

| Checkpoint | Required result | If missed |
| --- | --- | --- |
| First `30-50` preregistered cases | At least `10` accepted confirmations, `0` false confirmations | Stop and inspect witness binding, packet blockers, and detector misses |
| First `10` accepted confirmations | `100%` fixed-version clearance, complete packets, no hidden edges | Do not scale corpus operations |
| `50` accepted confirmations | Yield remains at least `20%`, multiple existing rule families represented | Measure family scarcity before curating the next batch |
| `100` accepted confirmations | `0` false confirmations, `100%` directional clearance, all adjudication complete | Publish the historically proven track record |

## 6. What Not to Build Next

Do not respond to slow confirmation accumulation with:

- new detectors before the miss distribution is measured;
- synthetic benchmark tuning;
- more unlabeled repository scans;
- general autonomous execution;
- repair generation;
- repair verification;
- broader repository-understanding work;
- LLM reasoning;
- relaxed packet requirements;
- post-hoc case selection.

Those paths either do not increase historically proven throughput or weaken the
claim.

## Bottom Line

Assuming Phase 99F and Phase 100A are complete:

| Question | Forecast |
| --- | --- |
| Expected accepted confirmed precision | `100%` operational target; `99-100%` expectation before measurement |
| Expected end-to-end historical recall | `25-35%` base forecast |
| Time to `10` confirmations | `1-2` small-team weeks |
| Time to `50` confirmations | `4-7` small-team weeks |
| Time to `100` confirmations | `8-13` small-team weeks |
| Next bottleneck | Proof-ready historical case throughput; then existing rule-family coverage |

The next meaningful act is measurement: run the first frozen `30-50` case batch
and replace this forecast with observed yield.
