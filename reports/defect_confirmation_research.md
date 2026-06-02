# Defect Confirmation Research

Date: 2026-05-31

Scope: Capability analysis only. No implementation, roadmap, code changes,
detector proposals, benchmark changes, or promotion changes.

## Executive Answer

Builder Core currently produces useful review leads, not confirmed defects.

The shortest defensible path from:

```text
Review Lead
```

to:

```text
Confirmed Defect
```

is:

```text
review lead
  -> expected contract or invariant
  -> feasible violating path
  -> observable incorrect consequence
  -> verification evidence
  -> confirmed defect or retained lead
```

The single highest-leverage missing capability for this conversion is:

> **Contract analysis with path-feasibility evidence.**

Contract analysis answers the question Phase 95 reviewers could not answer from
the existing packets:

> What behavior was expected, and does a feasible path actually violate it?

Impact analysis remains valuable and should preserve its current
confidence-aware design. It answers what may be affected. It does not by itself
prove that anything is broken.

## 1. Phase 95E and 95F Evidence

### 1.1 Pilot Review Outcome

Phase 95E reviewed 202 grounded findings from two public pilot repositories.
The repositories were plugin and skill tooling at pinned commits.

| Outcome | Count | Share |
| --- | ---: | ---: |
| Confirmed actionable defects | **0** | **0%** |
| Useful review leads | **148** | **73.3%** |
| Misleading findings | **15** | **7.4%** |
| Benign or not useful | **34** | **16.8%** |
| Unclear | **5** | **2.5%** |

The finding population was heavily skewed:

| Rule | Kind | Count | Share |
| --- | --- | ---: | ---: |
| `null_dereference` | `value_flow` | 176 | 87.1% |
| `command_injection` | `security` | 14 | 6.9% |
| `path_traversal` | `security` | 12 | 5.9% |

The review process was operationally sound:

- packets validated before review;
- two independent reviewers completed all 202 candidates;
- 41 disagreements were adjudicated;
- no target repository was modified;
- no target code was executed;
- external-alpha verdict remained `HOLD`.

### 1.2 Phase 95F Interpretation

Phase 95F identified a taxonomy mismatch:

| Existing treatment | Human review result |
| --- | --- |
| Grounded findings are treated as verdict-eligible defects | Reviewers treated most findings as useful prompts for inspection |
| `null_dereference` implies a broken dereference path | Reviewers often saw a conservative maybe-None signal without proof of an unguarded path |
| `command_injection` implies an exploitable sink | Reviewers often saw locally controlled argv lists or wrappers without proven hostile input |
| `path_traversal` implies unsafe path use | Reviewers often lacked enough provenance and trust-boundary evidence to confirm exploitability |

Phase 95F therefore separated:

- confirmed defects;
- risk leads;
- security review leads;
- style or robustness advisories.

That separation is the correct evidence posture. A lead should become a defect
only when an additional proof obligation is satisfied.

## 2. Why Useful Leads Were 73% but Confirmed Defects Were 0

The two numbers are compatible. They measure different things.

### 2.1 What "Useful Lead" Meant

Reviewers considered a finding useful when it reduced investigation effort:

| Lead pattern | Why it was useful |
| --- | --- |
| Conservative maybe-None value | Prompted a quick check for guards and missing-key behavior |
| `.get()` result use | Prompted inspection of whether a missing key is allowed |
| Subprocess wrapper receiving `cmd: list[str]` | Prompted caller tracing for untrusted argv construction |
| CLI-selected path | Prompted clarification of the operator trust boundary |

A useful lead tells a developer:

> Open this location and inspect this condition.

That is valuable even when the final answer is:

- guarded correctly;
- locally controlled;
- intended behavior;
- insufficiently proven.

### 2.2 What "Confirmed Defect" Required

A confirmed defect requires a stronger statement:

> Under condition X, the program violates expected behavior Y, through feasible
> path Z, with consequence C.

The existing packets did not consistently establish:

- a precise expected contract;
- a feasible unguarded or unsanitized path;
- caller and callee obligations;
- trust-boundary provenance;
- an observable incorrect consequence;
- a failing test or minimal reproduction.

The system usually surfaced the **location of uncertainty**, not the **proof of
incorrect behavior**.

### 2.3 Null-Dereference Findings

The dominant false-positive family was visible guard blindness:

| Pilot evidence | Count |
| --- | ---: |
| Negated guard before use | 5 |
| Explicit None guard on `best` | 2 |
| Explicit None guard on `me` | 2 |
| HTTP status guard | 2 |
| Truthiness guard | 1 |
| None path rejected before `open()` | 1 |

The missing question was not:

> Could this value be None?

It was:

> Is there a feasible path where this value is None, no guard excludes that
> path, the dereference is reached, and the contract requires success?

Without that answer, the correct product category is **Risk Lead**.

### 2.4 Security Findings

The dominant security ambiguity was provenance and trust boundary:

| Pilot evidence | Interpretation |
| --- | --- |
| Constant Git argv list with no shell | Subprocess call exists, but exploitability is not established |
| Fixed `[python, script_path]` argv with JSON stdin | Execution sink exists, but hostile command construction is not established |
| Constant ffmpeg argv list | Shell-like operation exists, but tainted command string is not established |
| Internal template path | File path use exists, but traversal from untrusted input is not established |
| CLI user-chosen path | May be operator-controlled rather than a remote exploit boundary |

The missing question was not:

> Does data reach a sensitive operation?

It was:

> Does untrusted data cross a defined boundary, remain insufficiently
> constrained, reach a sink with dangerous semantics, and produce an observable
> security violation?

Without that answer, the correct product category is **Security Review Lead**.

### 2.5 Corpus Shape

The pilot repositories were not a bug-rich historical corpus. They were useful
for operational validation and lead-quality review, but absence of confirmed
defects does not prove Builder Core can never confirm one.

The evidence supports:

> On these two pilot repositories, the analyzer found many useful inspection
> prompts but did not establish a single confirmed actionable defect.

It does not support:

> The analyzer is useless.

It also does not support:

> The analyzer already tells developers what is broken.

## 3. Confirmation Standard

A review lead should cross into confirmed-defect status only when the evidence
packet answers all of the following.

| Confirmation question | Required answer |
| --- | --- |
| What is expected? | A contract, invariant, test expectation, API obligation, or security boundary |
| What violates it? | A concrete value, state, branch, call sequence, or data provenance |
| Is the path feasible? | Guards, sanitizers, early returns, and unresolved calls are accounted for |
| What goes wrong? | A dereference, incorrect result, exception, unsafe operation, or violated security property |
| How certain is the claim? | Confirmed, strongly supported, unresolved, or retained as a lead |
| What evidence closes the case? | Static proof, failing test, minimal reproduction, historical regression evidence, or human confirmation |

### 3.1 Minimal Defect Packet

```text
Status:
  confirmed defect | review lead | security review lead | unknown

Expected contract:
  what the code is required to do

Violating condition:
  input, state, provenance, or branch condition

Feasible path:
  origin -> propagation -> guard state -> operation

Observable consequence:
  what behavior becomes incorrect

Evidence:
  source lines, resolved calls, tests, reproduction, and caveats

Unknowns:
  unresolved calls, dynamic dispatch, opaque files, missing runtime evidence
```

This packet is the shortest meaningful bridge between static suspicion and
confirmed defect.

## 4. Missing Capabilities Preventing Confirmation

| Missing capability | Why it prevents confirmation | Pilot evidence |
| --- | --- | --- |
| Contract analysis | The analyzer does not consistently state the violated expectation | Maybe-None, locally controlled argv, and path provenance findings remained advisory |
| Path-feasibility reasoning | The analyzer does not consistently prove that a violating path survives guards and reaches the operation | Visible guard misses dominated null-dereference false positives |
| Trust-boundary reasoning | Security sink presence is not enough; exploitability depends on provenance and sink semantics | Constant argv lists and internal paths were misleading |
| Cross-function usage context | Caller obligations and callee guarantees can determine whether a return or input is unsafe | Cross-file facts exist, but consumption remains deliberately gated |
| Verification evidence | Static suspicion is stronger when tied to a failing test, reproduction, or historical defect | Pilot packets did not produce confirmed-actionable labels |
| Explicit confirmation taxonomy | Leads must not inherit defect language by default | Phase 95F identified the grounded-equals-defect mismatch |
| Negative evidence handling | Guards, sanitizers, resolved safe paths, and unknowns must actively constrain claims | Human reviewers found source-visible evidence that reduced confidence |

## 5. Candidate Solution Ranking

This ranking answers one narrow question:

> Which capability most directly converts a review lead into a confirmed defect?

It is not a roadmap or implementation order.

| Rank | Candidate capability | Confirmation value | Difficulty | Risk | Why it ranks here |
| ---: | --- | --- | --- | --- | --- |
| 1 | **Contract analysis** | Critical | High | Medium to high | Defines what behavior is required and whether the suspected path violates it. Directly addresses nullability, return, API, and trust-boundary ambiguity. |
| 2 | **Execution-path reasoning** | Critical | High | High | Establishes whether the violating condition can actually reach the operation after guards, sanitizers, branches, and calls. Essential companion to contract analysis. |
| 3 | **Verification engine** | Critical | High | High | Supplies failing-test, reproduction, and post-check evidence. Strongest way to turn a static case into a confirmed result when safe execution is available. |
| 4 | **Root-cause engine** | High | High | High | Explains the earliest actionable source rather than the sink symptom. Improves a confirmed defect substantially, but requires contract and path evidence to avoid speculative causality. |
| 5 | **Impact analysis** | Medium for confirmation; high for engineering usefulness | Medium | Low to medium | Identifies potentially affected files, functions, modules, execution paths, and confidence gaps. It scopes the problem but does not establish that the problem exists. |
| 6 | **Repair validation** | Low for initial confirmation; critical after repair exists | High | High | Confirms that a proposed correction works without known regression. It is downstream of defect confirmation and repair generation. |

## 6. Candidate Capability Analysis

### 6.1 Contract Analysis

**Role in confirmation:** Define the expected behavior that a path violates.

Contract analysis is the highest-leverage missing capability because the pilot
findings repeatedly lacked the answer to:

> What obligation is actually broken?

Relevant contract forms include:

| Contract form | Example confirmation question |
| --- | --- |
| Nullability | May this function return `None`, and does the caller require a non-None result? |
| Return shape | Must every reachable path return a value of the same usable shape? |
| Preconditions | Is this operation allowed only after a guard or validation step? |
| Postconditions | Does this function guarantee a populated collection, valid object, or sanitized value? |
| Security boundary | Is the value remote, user-controlled, operator-controlled, internal, or constant? |
| Sink semantics | Does the sink invoke a shell, accept structured argv, normalize paths, or use an internal template? |
| Algorithm invariant | Does BFS preserve FIFO behavior and terminate when the frontier is exhausted? |

**Dependency chain:**

```text
review lead
  + local flow facts
  + caller/callee summaries
  + test expectations where available
  -> explicit contract
  -> violated, satisfied, or unknown
```

**Value:** Critical.

**Difficulty:** High.

**Risk:** Medium to high. Incorrectly inferred contracts can create polished
false positives. Contracts must remain evidence-scoped and may resolve to
unknown.

### 6.2 Execution-Path Reasoning

**Role in confirmation:** Prove that the violating state reaches the operation.

Execution-path reasoning must account for:

- branch narrowing;
- negated guards;
- explicit `is None` checks;
- truthiness guards;
- early returns and continues;
- sanitizers;
- resolved caller/callee relationships;
- unresolved dynamic behavior.

For a null lead, the central question is:

```text
Can None reach this dereference on a feasible, unguarded path?
```

For a security lead:

```text
Can untrusted data reach this sink with dangerous semantics on a feasible,
unsanitized path?
```

**Dependency chain:**

```text
contract
  + control/data/value flow
  + resolved call facts
  + negative evidence
  -> feasible violating path or retained uncertainty
```

**Value:** Critical.

**Difficulty:** High.

**Risk:** High. Static path reasoning is incomplete around dynamic dispatch,
framework behavior, and runtime state. Missing coverage must remain explicit.

### 6.3 Verification Engine

**Role in confirmation:** Add empirical or executable evidence where allowed.

A verification engine strengthens the static case through:

- existing failing tests;
- minimal reproductions;
- targeted checks;
- historical failing-versus-fixed comparisons;
- explicit blocked or unavailable outcomes.

The verification engine must preserve Builder Core's trust boundary:

- no implicit execution of untrusted target repositories;
- developer-controlled execution;
- clear reporting of unavailable dependencies;
- no interpretation of skipped or blocked checks as success.

**Dependency chain:**

```text
suspected contract violation
  + reproduction or relevant test
  + safe execution boundary
  -> confirmed, partially confirmed, blocked, or unresolved
```

**Value:** Critical.

**Difficulty:** High.

**Risk:** High. Unsafe execution and false-success semantics would undermine
the read-only safety model.

### 6.4 Root-Cause Engine

**Role in confirmation:** Explain why the defect exists and identify the
earliest actionable causal boundary.

A root-cause engine should connect:

```text
origin
  -> propagation
  -> branch or state transition
  -> violated contract
  -> symptom
```

It should distinguish:

- cause from sink;
- cause from correlated dependency;
- caller violation from callee violation;
- regression source from nearby edit;
- proven relationship from plausible hypothesis.

**Dependency chain:**

```text
confirmed or strongly supported violation
  + contract
  + feasible path
  + impact context
  -> causal explanation with competing hypotheses and unknowns
```

**Value:** High.

**Difficulty:** High.

**Risk:** High. Reachability is not causality. Root-cause output must not be
generated from graph adjacency alone.

### 6.5 Impact Analysis

**Role in confirmation:** Scope the affected surface and expose confidence
limits.

The Phase 94B design correctly separates:

1. asserted resolved impact;
2. possible additional unverified impact;
3. unanalyzed or degraded surface.

Impact analysis can answer:

- who depends on this function;
- what files and modules may be affected;
- which resolved execution paths reach the code;
- how wide the potential blast radius is;
- where unresolved edges reduce confidence.

It cannot answer:

- whether the lead is a real defect;
- whether a reachable path is behaviorally failing;
- whether a contract is violated;
- whether a proposed repair is correct.

**Dependency chain:**

```text
RU-2 roles and subsystems
  + deterministic dependency graph
  + unresolved edge channels
  -> confidence-aware affected surface
```

**Value:** Medium for defect confirmation, high for developer usefulness.

**Difficulty:** Medium.

**Risk:** Low to medium. The key failure mode is presenting absence of a
resolved path as safety.

### 6.6 Repair Validation

**Role in confirmation:** Validate a repair after a defect and candidate
correction exist.

Repair validation answers:

- did the reproduction stop failing;
- do relevant checks pass;
- did static evidence disappear or downgrade;
- did affected interfaces remain compatible;
- did another regression appear;
- is verification complete, partial, blocked, or ambiguous.

It is essential for:

> JARVIS tells developers this repair holds.

It is not the shortest path to:

> JARVIS tells developers this is broken.

**Dependency chain:**

```text
confirmed defect
  + bounded repair candidate
  + verification engine
  + impact-aware test surface
  -> repair validation outcome
```

**Value:** Low for initial confirmation; critical after repair generation.

**Difficulty:** High.

**Risk:** High. Partial checks must never be presented as complete validation.

## 7. Candidate Comparison by Product Question

| Candidate | Does it prove a defect exists? | Does it explain root cause? | Does it scope impact? | Does it help verify repair? |
| --- | --- | --- | --- | --- |
| Contract analysis | **Directly, when evidence is sufficient** | Major input | Indirectly | Major input |
| Execution-path reasoning | **Directly, when path is statically feasible** | Major input | Some path context | Major input |
| Verification engine | **Directly, when a safe reproduction or relevant test exists** | Supporting evidence | Some test context | **Directly** |
| Root-cause engine | Strengthens an established case | **Directly** | Uses impact context | Major input |
| Impact analysis | No | Supporting context | **Directly** | Major input |
| Repair validation | No, assumes a defect and repair candidate | No | Uses impact context | **Directly** |

## 8. Evidence-Based Recommendation

### Recommendation

The highest-leverage defect-confirmation capability is:

> **Contract analysis with path-feasibility evidence and explicit unknown
> outcomes.**

This recommendation follows directly from Phase 95E and 95F:

| Phase 95 evidence | Capability implication |
| --- | --- |
| 176/202 findings were null-dereference leads | Confirmation needs nullability contracts and path-sensitive guard accounting |
| Visible guards caused the dominant misleading family | Confirmation needs feasible-path reasoning and negative evidence |
| Constant argv lists caused security false positives | Confirmation needs trust-boundary contracts and sink semantics |
| Path provenance was unclear for traversal leads | Confirmation needs provenance across relevant calls |
| 148 findings were useful but none confirmed | The system needs a promotion proof obligation, not broader warning volume |
| Phase 95 remained `HOLD` | Claims must remain conservative until confirmation quality is measured |

### Smallest Defensible Confirmation Model

```text
Lead:
  a suspicious operation exists

Contract:
  expected behavior or security property is explicit

Path:
  a feasible violating path reaches the operation

Consequence:
  the path produces incorrect or unsafe behavior

Verification:
  static proof, failing test, reproduction, historical evidence, or human
  confirmation closes the case

Outcome:
  confirmed defect | retained lead | unknown
```

### Relationship to Impact Analysis

Impact analysis is worth completing because it provides:

- callers;
- dependent modules;
- potential blast radius;
- resolved execution paths;
- confidence caveats;
- likely verification surface.

But the confirmation model must not collapse:

```text
reachable or widely used
```

into:

```text
broken
```

### Relationship to Root Cause

Root-cause analysis becomes trustworthy after the system can state:

- the expected contract;
- the feasible violating path;
- the visible consequence.

Without those, a root-cause engine risks producing an elegant explanation for
an unconfirmed warning.

### Relationship to Verification and Repair

A verification engine is the strongest confirmation companion when safe tests
or reproductions exist. Repair validation remains downstream:

```text
confirm defect
  -> explain cause
  -> scope impact
  -> suggest repair
  -> validate repair
```

## 9. Final Conclusion

Phase 95 showed that Builder Core already provides meaningful review value.
The 73% lead rate is real. The 0 confirmed-defect count is also real.

The gap between them is not warning volume. It is proof.

The shortest capability bridge is:

```text
contract
  + feasible path
  + observable consequence
  + verification evidence
```

Impact analysis improves scope. Root-cause analysis improves explanation.
Repair validation improves confidence after a patch exists.

Contract analysis with path-feasibility evidence is the capability that most
directly changes the product statement from:

> JARVIS found something worth inspecting.

to:

> JARVIS can show why this behavior is broken.

## Local Evidence Used

- `reports/phase95e_pilot_human_review_results.md`
- `reports/phase95f_post_review_calibration_plan.md`
- `reports/phase94b_impact_analysis_design.md`
- `reports/repository_intelligence_gap_analysis_v2.md`

