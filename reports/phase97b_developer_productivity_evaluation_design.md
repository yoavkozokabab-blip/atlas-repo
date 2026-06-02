# Phase 97B - Developer Productivity Evaluation Design

Date: 2026-05-31

Status: Design only. No implementation. No tuning. No detector, benchmark,
promotion, or product-behavior changes.

## 0. Executive Summary

This document defines a small controlled pilot for one practical question:

> Does JARVIS help a developer understand, review, and prepare changes to a
> repository faster than Claude/Cursor alone?

The evaluation uses only capabilities that exist today:

- RU-3 architectural question understanding;
- the deterministic dependency graph;
- impact analysis;
- contract-enriched review packets;
- Phase 95 and Phase 96 review artifacts.

The pilot compares four conditions:

1. developer alone;
2. Claude/Cursor alone;
3. JARVIS only;
4. JARVIS + Claude.

The primary product comparison is:

```text
JARVIS + Claude
versus
Claude/Cursor alone
```

The pilot measures whether JARVIS reduces time and unnecessary repository
reading **without reducing correctness, decision quality, or appropriate
uncertainty**.

This is a productivity evaluation, not an intelligence-tuning exercise. The
system is frozen for the duration of the study.

---

## 1. Evidence Baseline

### 1.1 Existing capabilities

| Capability | Current useful output | Evaluation role |
| --- | --- | --- |
| RU-3 | Graph/index-backed answers for production layout, dependency centrality, subsystem centrality, bottlenecks, and targeted impact questions | Repository understanding tasks |
| Dependency Graph | Deterministic nodes, resolved imports, resolved calls, references, unresolved channels, cycles, top modules, top functions | Architecture and execution-path tasks |
| Impact Analysis | Direct impact, transitive impact, execution paths, possible unverified impact, unanalyzed scope, risk, confidence | Change-impact tasks |
| Contract-Enriched Review Packets | Explicit return contracts, strong caller behavior, conflicts, and `why_not_confirmed` | Finding-review and actionability tasks |
| Phase 95 review workflow | Human labels, dual-review protocol, adjudication, misleading-rate analysis | Gold labels and review-quality rubric |
| Phase 96D pilot | Review clarity and confidence measurements for `inconsistent_return` packets | Study design calibration |

### 1.2 Current limitation

Phase 95E and Phase 96D establish a strict claim boundary:

| Existing review result | Value |
| --- | ---: |
| Phase 95E grounded findings reviewed | 202 |
| Phase 95E useful review leads | 148 (`73.3%`) |
| Phase 95E misleading findings | 15 (`7.4%`) |
| Phase 95E confirmed actionable defects | 0 |
| Phase 96D sampled `inconsistent_return` leads | 20 |
| Phase 96D confirmed defects | 0 |
| Phase 96D promotion changes | 0 |

Therefore this pilot can measure:

- faster repository understanding;
- faster change-impact assessment;
- faster, clearer review decisions;
- better handling of uncertainty;
- reduced unnecessary context reading.

It cannot claim to measure:

- improved confirmed-defect recall;
- repair quality;
- repair verification quality;
- autonomous coding speed.

The first pilot measures **change readiness**, not patch implementation.

---

## 2. Evaluation Question And Hypotheses

### 2.1 Primary question

```text
For the same frozen repositories and task rubrics, does adding JARVIS to a
pinned Claude/Cursor workflow reduce time-to-correct-answer while preserving
or improving answer quality?
```

### 2.2 Secondary questions

1. Does JARVIS-only improve productivity over a developer-alone workflow?
2. Which task types benefit most from JARVIS?
3. Does JARVIS reduce the number of source files opened?
4. Does JARVIS reduce unnecessary context reading?
5. Do JARVIS outputs help developers express uncertainty correctly?
6. Do contract-enriched review packets improve actionability decisions without
   causing overconfident defect claims?

### 2.3 Hypotheses

| ID | Hypothesis |
| --- | --- |
| `H1` | `JARVIS + Claude` reduces median time-to-correct-answer versus `Claude/Cursor alone`. |
| `H2` | `JARVIS + Claude` preserves correctness within a strict non-inferiority margin. |
| `H3` | `JARVIS + Claude` reduces unnecessary source context read versus `Claude/Cursor alone`. |
| `H4` | `JARVIS only` reduces median time-to-correct-answer versus `developer alone`. |
| `H5` | JARVIS-supported finding review produces equal or better actionability decisions without increasing false actionable claims. |

---

## 3. Frozen Evaluation Scope

### 3.1 Freeze rules

Before the first participant session:

- freeze two repository revisions;
- export a clean JARVIS index, dependency graph, impact outputs, and selected
  review packets for those revisions;
- freeze all task prompts;
- freeze gold-answer rubrics;
- freeze the Claude/Cursor configuration;
- prohibit Builder Core tuning during the pilot;
- record the date, repository revisions, tool versions, model selection, and
  assistant settings.

The active dirty `local_jarvis` working tree must not be used directly as an
evaluation repository. Use a clean pinned snapshot.

### 3.2 Claude/Cursor baseline definition

`Claude/Cursor alone` must be one pinned assistant configuration per study run.
Do not pool results from materially different products or model settings.

Record:

- product surface;
- model name;
- model version or date if exposed;
- context mode;
- repository indexing state;
- agent mode;
- tool permissions;
- network availability;
- prompt template;
- session reset policy.

If both Claude and Cursor are evaluated, report them as separate sub-studies.
Do not merge them into one baseline.

### 3.3 Allowed repository tools

| Condition | Source editor/search | Git read-only commands | JARVIS outputs | Claude/Cursor |
| --- | --- | --- | --- | --- |
| Developer alone | Yes | Yes | No | No |
| Claude/Cursor alone | Yes | Yes | No | Yes |
| JARVIS only | Yes | Yes | Yes | No |
| JARVIS + Claude | Yes | Yes | Yes | Yes |

Allowed read-only developer tools include:

- editor navigation;
- repository search;
- `git log`, `git show`, and `git grep`;
- opening source and documentation files;
- frozen JARVIS Builder Core commands in JARVIS-enabled groups.

Disallowed during timed tasks:

- source modification;
- detector changes;
- JARVIS tuning;
- prompt tuning between participants;
- internet searches;
- opening gold answers;
- sharing answers between participants;
- using JARVIS-generated outputs in non-JARVIS groups.

---

## 4. Pilot Corpus

### 4.1 Repository count

Use exactly two frozen Python repository snapshots.

| Repository role | Required characteristics | Candidate |
| --- | --- | --- |
| Repo A: architecture-rich | Multiple production subsystems, meaningful import graph, impact-analysis targets, at least one partially resolved execution-path question | Clean pinned `local_jarvis` snapshot |
| Repo B: review-grounded | Existing Phase 95 human-reviewed packets, known useful leads, misleading cases, and unclear cases | Frozen `openai-plugins-public-pilot` Phase 95 snapshot |

The final selected revisions must be recorded before task execution.

### 4.2 Why these two repository roles

Repo A exercises RU-3, graph, and impact analysis on a structurally rich system.

Repo B exercises review quality against existing Phase 95 human adjudication,
including the important behavior:

```text
useful lead != confirmed defect
```

### 4.3 Task count

Each participant completes:

```text
2 repositories x 5 task types = 10 timed tasks
```

Total observations:

| Developers | Timed observations |
| ---: | ---: |
| 3 | 30 |
| 4 | 40 |
| 5 | 50 |

Four developers is the preferred pilot size because it balances the four
comparison groups cleanly.

---

## 5. Evaluation Tasks

Each repository supplies one task for each required task type.

### 5.1 Task 1 - Understand subsystem

**Prompt form**

```text
Explain the purpose of <subsystem>. Identify its main entry files, important
dependencies, and one uncertainty that should be checked before changing it.
```

**Current JARVIS inputs**

- RU-3 specialized architectural answers;
- RU-2 subsystem map;
- dependency graph imports and module statistics.

**Required answer**

- subsystem role;
- two to four entry or central files;
- important upstream and downstream relationships;
- explicit uncertainty where graph coverage is partial;
- cited source paths.

**Gold rubric**

| Criterion | Points |
| --- | ---: |
| Correct subsystem purpose | 2 |
| Correct entry or central files | 2 |
| Correct dependency relationships | 2 |
| Grounded source citations | 1 |
| Honest uncertainty | 1 |

Maximum: `8`.

### 5.2 Task 2 - Assess impact of change

**Prompt form**

```text
Assume <file or function> changes. Which files or subsystems are most likely to
be affected? Separate direct impact, transitive impact, and unknown or
unverified impact.
```

**Current JARVIS inputs**

- Phase 94A dependency graph;
- Phase 94B impact analysis;
- asserted, possible, and unanalyzed channels;
- risk and confidence summaries.

**Required answer**

- direct dependents;
- material transitive dependents;
- affected subsystems;
- unresolved or possible impact;
- risk and confidence explanation;
- source paths.

**Gold rubric**

| Criterion | Points |
| --- | ---: |
| Correct direct dependents | 2 |
| Correct transitive scope | 2 |
| Correct subsystem summary | 1 |
| Separates asserted from possible impact | 2 |
| Avoids unsupported breakage claim | 1 |

Maximum: `8`.

### 5.3 Task 3 - Review risky finding

**Prompt form**

```text
Review this finding. Explain why it may matter, what evidence supports it, what
evidence weakens it, and what the next verification step should be.
```

**Current JARVIS inputs**

- Phase 95 reviewer packets;
- Phase 96C contract-enriched review packets where applicable;
- source window;
- `why_not_confirmed`;
- conflicting evidence.

**Required answer**

- suspected risk;
- supporting evidence;
- conflicting or missing evidence;
- likely disposition;
- next verification step;
- no unsupported confirmation language.

**Gold rubric**

| Criterion | Points |
| --- | ---: |
| Correctly identifies suspected risk | 1 |
| Uses supporting evidence accurately | 2 |
| Identifies refuting or missing evidence | 2 |
| Chooses appropriate disposition | 2 |
| Gives an efficient next verification step | 1 |

Maximum: `8`.

### 5.4 Task 4 - Trace execution path

**Prompt form**

```text
Trace the strongest supported execution path from <entry point> to <target>.
List the path and clearly identify any unresolved edge. If the path cannot be
proven, say so.
```

**Current JARVIS inputs**

- dependency graph resolved call edges;
- impact-analysis execution paths;
- unresolved-call channels;
- RU-3 architectural routing.

**Required answer**

- resolved path segments;
- unresolved segments;
- source paths and functions;
- confidence;
- explicit `cannot prove` answer when coverage is incomplete.

**Gold rubric**

| Criterion | Points |
| --- | ---: |
| Correct resolved path segments | 3 |
| Correct unresolved edge handling | 2 |
| Grounded citations | 1 |
| Correct confidence | 1 |
| No fabricated path | 1 |

Maximum: `8`.

### 5.5 Task 5 - Decide whether a finding is actionable

**Prompt form**

```text
Classify this finding as:
- actionable defect candidate
- useful review lead
- misleading or benign
- unclear

Explain the smallest next step that would change your decision.
```

**Current JARVIS inputs**

- Phase 95 adjudicated review labels;
- Phase 96C contract packets;
- Phase 96D `why_not_confirmed` treatment;
- source window.

**Required answer**

- classification;
- evidence-based rationale;
- missing proof obligation;
- efficient next step;
- calibrated confidence.

**Gold rubric**

| Criterion | Points |
| --- | ---: |
| Correct adjudicated classification | 3 |
| Correct evidence rationale | 2 |
| Correct missing proof obligation | 1 |
| Efficient next step | 1 |
| Calibrated confidence | 1 |

Maximum: `8`.

### 5.6 Actionability-task limitation

The current Phase 95/96 reviewed corpus contains zero confirmed actionable
defects. The initial pilot therefore measures:

- correct restraint;
- useful-lead recognition;
- misleading-finding rejection;
- uncertainty handling.

It does not measure sensitivity to confirmed defects.

Any later inclusion of known-positive actionability tasks must use separately
preregistered historical defects with pinned buggy and fixed revisions. Those
results must be reported separately from this pilot.

---

## 6. Comparison Groups

### 6.1 Group definitions

| Group | Purpose | What the developer sees |
| --- | --- | --- |
| `D0` - Developer alone | Human baseline | Source, docs, editor search, read-only Git |
| `C1` - Claude/Cursor alone | Existing assistant baseline | `D0` tools plus pinned assistant configuration |
| `J1` - JARVIS only | Builder Core standalone value | `D0` tools plus frozen JARVIS outputs and commands |
| `JC` - JARVIS + Claude | Product-combination hypothesis | `D0`, frozen JARVIS outputs, and the same pinned assistant configuration as `C1` |

### 6.2 Primary and secondary comparisons

| Comparison | Interpretation |
| --- | --- |
| `JC` vs `C1` | Primary: incremental value of JARVIS in an AI-assisted developer workflow |
| `J1` vs `D0` | Secondary: standalone value of JARVIS |
| `JC` vs `J1` | Secondary: complementary value of general assistant synthesis |
| `C1` vs `D0` | Context: assistant uplift without JARVIS |

### 6.3 Fairness rules

- `C1` and `JC` use the same assistant configuration.
- Every group receives the same task text.
- JARVIS outputs are frozen before the study.
- No group receives a hand-curated answer not available to the others.
- If a JARVIS output is degraded or incomplete, it remains degraded or
  incomplete in every JARVIS-enabled session.
- Developers may answer `unknown` or `cannot prove`; this can be the correct
  answer.

---

## 7. Pilot Protocol

### 7.1 Participants

Recruit `3-5` software developers.

Preferred composition:

- at least two developers comfortable with Python repositories;
- at least one developer unfamiliar with the selected repositories;
- no participant who authored the frozen evaluation tasks;
- record years of experience and prior familiarity.

Ideal pilot size: `4`.

### 7.2 Counterbalanced crossover

Use a within-participant crossover:

- every developer completes all `10` tasks;
- each task is completed once per developer;
- each developer uses all four tool conditions;
- task-condition assignment rotates across developers using a Latin-square
  schedule;
- task order is shuffled within a preregistered balanced sequence;
- repository order alternates across participants.

For four developers, each canonical task is completed once under each
condition across the participant set.

Example condition rotation:

| Developer | Task block 1 | Task block 2 | Task block 3 | Task block 4 |
| --- | --- | --- | --- | --- |
| A | `D0` | `C1` | `J1` | `JC` |
| B | `C1` | `J1` | `JC` | `D0` |
| C | `J1` | `JC` | `D0` | `C1` |
| D | `JC` | `D0` | `C1` | `J1` |

The final schedule must balance task type, repository, and condition.

### 7.3 Carryover controls

Developers cannot unlearn a repository after the first task. Control this by:

- alternating repository order;
- rotating conditions across task types;
- using targets from different subsystems;
- preventing the same developer from answering the same question twice;
- recording task sequence;
- reporting first-half and second-half results separately;
- treating the small pilot as exploratory rather than statistically conclusive.

### 7.4 Session procedure

For each task:

1. Reset the assistant conversation if the condition uses one.
2. Open the frozen repository snapshot.
3. Reveal the task prompt.
4. Start the timer.
5. Record source files opened and context viewed.
6. Let the participant submit a written answer and confidence score.
7. Stop the timer.
8. Ask one short usability question:

```text
What information saved the most time, and what information was missing?
```

Time cap: `15 minutes` per task.

Incomplete tasks remain incomplete. Do not silently extend the cap.

---

## 8. Metrics

### 8.1 Primary metrics

| Metric | Definition |
| --- | --- |
| Time to answer | Wall-clock seconds from prompt reveal to submitted answer |
| Time to correct answer | Wall-clock seconds when answer meets minimum correctness threshold; capped incomplete otherwise |
| Correctness | Expert rubric score, `0-8`, normalized to `0-100%` |
| Decision quality | Task-specific quality score, including correct uncertainty and actionability classification |

### 8.2 Required supporting metrics

| Metric | Definition |
| --- | --- |
| Confidence | Participant self-rating, `1-5`, recorded after submission |
| Confidence calibration | Difference between normalized confidence and normalized correctness |
| Number of files opened | Count of distinct repository source/doc files viewed during task |
| Unnecessary context read | Distinct opened files outside the preregistered gold evidence set |
| Unnecessary context ratio | Unnecessary files opened / all source files opened |
| Context volume | Approximate source lines viewed or copied into assistant context |
| Completion rate | Tasks submitted within the `15-minute` cap |
| Grounded citation rate | Answers with accurate source-file references |
| Unsupported-claim count | Claims not supported by source, graph, impact, or review packet evidence |
| Appropriate-unknown rate | Tasks where participant correctly says `unknown`, `partial`, or `cannot prove` |

### 8.3 Decision-quality details

Decision quality must reward restraint, not confidence alone.

| Task family | Decision-quality signal |
| --- | --- |
| Understand subsystem | Correctly identifies architecture without inventing responsibilities |
| Assess impact | Separates asserted, possible, and unanalyzed impact |
| Review risky finding | Surfaces supporting and weakening evidence |
| Trace execution path | Reports unresolved edges instead of fabricating a path |
| Decide actionability | Distinguishes defect candidate, useful lead, misleading/benign, and unclear |

### 8.4 Severe errors

Track severe errors separately:

- fabricated source file;
- fabricated call path;
- stated breakage based only on impact;
- misleading finding labeled confirmed without evidence;
- ignored explicit refuting guard;
- exposed gold-answer artifact;
- used JARVIS output in a non-JARVIS group.

One severe error can matter more than a small median speed improvement.

---

## 9. Gold Answers And Scoring

### 9.1 Gold-answer preparation

Before sessions, two independent reviewers prepare the gold set.

For each task:

- record required evidence files;
- record acceptable alternate paths or answers;
- record known unresolved graph edges;
- record the correct uncertainty level;
- record the answer rubric;
- record disallowed overclaims;
- adjudicate reviewer disagreements before the pilot.

Gold answers must be created without using the timed participant sessions.

### 9.2 Gold evidence set

Each task includes a preregistered gold evidence set:

```text
required files:
  files needed for a strong answer

optional useful files:
  files that reasonably add context

unnecessary files:
  any opened files outside required + optional sets
```

This supports a fair unnecessary-context metric.

### 9.3 Correctness threshold

Define a correct answer as:

```text
rubric score >= 6 / 8
and
zero severe errors
```

This threshold is used for `time to correct answer`.

### 9.4 Blind scoring

Scorers should receive:

- participant answer;
- task id;
- confidence score.

Scorers should not receive:

- participant identity;
- comparison group;
- time-to-answer;
- assistant transcript;
- source of the answer.

Score disagreements are adjudicated before aggregate analysis.

---

## 10. Analysis Plan

### 10.1 Unit of analysis

The unit of analysis is:

```text
participant x repository x task
```

Report raw observations and aggregated results.

### 10.2 Required result views

Report:

1. overall results by condition;
2. results by task type;
3. results by repository;
4. results by participant;
5. first-half versus second-half results;
6. severe errors;
7. incomplete tasks;
8. confidence calibration;
9. unnecessary-context distribution.

### 10.3 Summary statistics

For the small pilot, use:

- median;
- interquartile range;
- paired per-participant deltas;
- paired per-task deltas;
- completion counts;
- raw score table.

Optional bootstrap intervals may be reported as exploratory. Do not claim
statistical significance from a `3-5` developer pilot.

### 10.4 Primary outcome

Primary outcome:

```text
median time-to-correct-answer delta:
  JC versus C1
```

Guardrails:

- normalized correctness;
- decision quality;
- severe errors;
- unsupported claims;
- false actionable claims.

### 10.5 Secondary outcomes

- `J1` versus `D0` time-to-correct-answer;
- files opened;
- unnecessary context ratio;
- confidence calibration;
- task-family-specific uplift;
- qualitative comments about missing or distracting information.

---

## 11. Pass, Hold, And Fail Gates

### 11.1 PASS

The pilot passes only when all hard safety gates and primary value gates pass.

#### Hard safety and quality gates

| Gate | PASS requirement |
| --- | --- |
| Severe unsupported claims in `JC` | `0` |
| False actionable claims in Phase 95/96 adjudicated misleading or benign cases | `0` |
| Correctness non-inferiority, `JC` vs `C1` | `JC` normalized correctness no more than `5` percentage points below `C1` |
| Decision-quality non-inferiority, `JC` vs `C1` | `JC` mean no more than `0.25 / 8` below `C1` |
| Appropriate unknown handling | No fabricated path where gold answer is partial or unknown |
| Completion integrity | Every timeout and incomplete task reported |

#### Primary value gates

| Gate | PASS requirement |
| --- | --- |
| Median time-to-correct-answer, `JC` vs `C1` | At least `20%` faster |
| Task-family spread | `JC` improves time-to-correct-answer by at least `15%` in at least `3 / 5` task families |
| Context reduction | `JC` reduces median unnecessary-context ratio by at least `20%` versus `C1` |
| Correct-answer completion | `JC` completion rate is not lower than `C1` |

#### Secondary standalone gate

Report separately:

```text
J1 versus D0 median time-to-correct-answer improves by at least 15%
with no correctness drop greater than 5 percentage points.
```

Failure of the secondary standalone gate does not override a primary PASS, but
it must be reported.

### 11.2 HOLD

Return `HOLD` when:

- safety and correctness gates pass;
- median time improvement is between `5%` and `20%`;
- results are strongly mixed by developer or repository;
- carryover effects appear material;
- the pilot is too small to interpret confidently;
- context reduction is not demonstrated;
- task difficulty imbalance is discovered.

`HOLD` means evidence is inconclusive, not negative.

### 11.3 FAIL

Return `FAIL` when any apply:

- `JC` is more than `5` percentage points worse than `C1` on correctness;
- `JC` creates any false actionable claim on an adjudicated misleading or
  benign Phase 95/96 case;
- JARVIS causes a fabricated execution path;
- severe unsupported claims appear;
- JARVIS outputs leak into control groups;
- frozen artifacts or prompts change during the pilot;
- median `JC` time-to-correct-answer is slower than `C1` by more than `5%`
  without a compensating quality gain accepted by reviewers.

---

## 12. Expected Artifacts

A future execution of this design should produce:

```text
reports/phase97b_productivity_pilot/
  manifest.json
  frozen_tooling.json
  repository_revisions.json
  task_bank.json
  gold_rubrics.json
  schedule.json
  raw_observations.json
  blinded_scores.json
  adjudication.json
  metrics.json
  report.md
```

### 12.1 Raw observation shape

```text
participant_id
task_id
repository_id
task_type
condition
task_order
time_seconds
completed
answer
confidence_1_to_5
files_opened
context_lines_viewed
assistant_transcript_ref
jarvis_output_refs
```

### 12.2 Metrics report shape

```text
overall_by_condition
by_task_type
by_repository
by_participant
paired_deltas
completion_rates
correctness
decision_quality
confidence_calibration
files_opened
unnecessary_context
severe_errors
qualitative_notes
verdict: PASS | HOLD | FAIL
```

---

## 13. Risks And Controls

| Risk | Control |
| --- | --- |
| Small sample produces noisy conclusions | Report raw rows, paired deltas, and `HOLD` when mixed |
| Repository learning improves later tasks | Counterbalance order; report first-half vs second-half |
| Assistant-model drift | Pin configuration and execution date |
| JARVIS tuning contaminates results | Freeze index, outputs, prompts, and code |
| Task authors bias gold answers | Independent dual review and adjudication |
| Easy tasks exaggerate speed gains | Use rubric-scored tasks with unresolved and misleading cases |
| Confidence mistaken for correctness | Score calibration and severe errors separately |
| Impact analysis treated as proof | Penalize unsupported breakage claims |
| Partial graph paths treated as complete | Correct answer may be `cannot prove`; fabricated paths are severe errors |
| Current corpus has no confirmed defects | State limitation; do not claim defect-recall improvement |
| Claude and Cursor results get mixed | Run separately or use one pinned baseline |

---

## 14. Interpretation Rules

Allowed conclusion after a PASS:

```text
On this frozen two-repository pilot, adding JARVIS to the pinned assistant
workflow reduced time-to-correct-answer while preserving answer quality and
reducing unnecessary repository reading.
```

Disallowed conclusions:

```text
JARVIS finds more defects than Claude.
JARVIS repairs repositories faster.
JARVIS proves findings automatically.
JARVIS generalizes to all repositories.
```

Those claims require separate evidence.

---

## 15. Final Recommendation

Run the first pilot with:

- `4` developers if possible;
- `2` pinned Python repositories;
- `5` task types per repository;
- `10` timed tasks per developer;
- the four counterbalanced comparison groups;
- frozen JARVIS outputs;
- one pinned Claude/Cursor baseline;
- blinded scoring;
- correctness and restraint as hard guards around speed.

The most important result is not raw speed. It is:

```text
Does JARVIS help a developer reach a correct, grounded, appropriately cautious
decision with less repository reading than the assistant workflow alone?
```

