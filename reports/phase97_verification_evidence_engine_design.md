# Phase 97 - Verification Evidence Engine Design

Date: 2026-05-31

Status: Design only. No implementation. No detector changes. No promotion
changes. No benchmark changes.

## 0. Executive Summary

Phase 96 improved review clarity without producing defect confirmation:

| Phase 96D outcome | Result |
| --- | ---: |
| Sampled `inconsistent_return` leads | 20 |
| Confirmed defects | 0 |
| Promotion changes | 0 |
| Review confidence, baseline -> enriched | 2.0 -> 3.65 |
| Full understanding of why not confirmed, baseline -> enriched | 0 -> 20 |
| Contract evidence helped | 13 |
| Contract evidence neutral | 7 |

The result is useful and honest. Phase 96 made uncertainty legible. It did not
close the proof gap.

Phase 97 defines a **Verification Evidence Engine**: a read-only evidence
overlay that attaches typed, provenance-preserving evidence to existing
findings and review packets.

The engine answers:

```text
What evidence supports or refutes this lead?
How strong is that evidence?
Which proof obligation is still missing?
Is there enough evidence to form a promotion candidate?
```

It does **not** answer by fiat:

```text
This lead is now a confirmed defect.
```

No automatic promotion is enabled by this design. Promotion remains disabled
until a separate implementation and 0-FP validation gate prove that a narrowly
defined evidence bundle is safe.

The smallest safe first evidence source is **repository-grounded test and
assertion evidence**, linked deterministically to an existing finding. It can
move a lead closer to confirmation without executing target repositories,
inventing runtime behavior, or changing detector output.

---

## 1. Problem Statement

### 1.1 Current capability boundary

Builder Core currently has four useful layers:

| Layer | What it contributes | What it cannot prove |
| --- | --- | --- |
| Existing detectors | A suspicious code shape or flow exists | The behavior is incorrect |
| Phase 93B interprocedural gate | Some callers dereference a possibly missing return without null checks | The missing-return path is feasible in production |
| Phase 96 contract facts | Explicit and inferred obligations, guards, and conflicts | A concrete obligation is violated on an executable path |
| Phase 94B impact analysis | Potentially affected functions, files, and subsystems | Reachability is breakage |

Phase 96C and 96D showed the exact missing layer. Reviewers understood the
contract evidence, but still asked for:

- a test that demonstrates the bad behavior;
- an assertion that states the expected invariant;
- a feasible path from condition to violation;
- or a runtime reproduction tied to the pinned source revision.

### 1.2 Design goal

Phase 97 must create the smallest safe bridge:

```text
review lead
  + verification evidence atoms
  + explicit blockers
  -> enriched review lead
  -> optional promotion candidate after future gate
```

The evidence engine must be:

- read-only with respect to target repositories;
- deterministic;
- local;
- fact-backed;
- conservative under ambiguity;
- independent of LLM reasoning;
- incapable of silently promoting a lead.

### 1.3 Non-goals

Phase 97 design does not authorize:

- new detectors;
- detector threshold changes;
- promotion changes;
- benchmark changes;
- repair generation;
- repair validation;
- automatic execution of target repository code;
- dynamic test generation;
- LLM-generated contracts or reproductions;
- speculative root-cause claims.

---

## 2. Evidence Model

### 2.1 Evidence atom

An **evidence atom** is a deterministic record describing one sourced fact that
supports, refutes, or limits a finding.

Conceptual schema:

```text
verification_evidence:
  schema_version: 1
  finding_id: <existing Finding.id>
  status: enriched_lead | promotion_candidate | refuted | blocked | unknown
  atoms:
    - evidence_id: <stable content-derived id>
      evidence_type: test | assertion | contract_violation |
                     path_feasibility | runtime_reproduction
      polarity: supports | refutes | limits | unknown
      strength: E0 | E1 | E2 | E3 | E4
      claim: <machine-readable predicate id>
      subject:
        file: <repository-relative path>
        qualname: <resolved function or method>
        line: <source line>
        slot: <return | param:name | branch | call | assertion | test>
      provenance:
        source_kind: repository_ast | contract_fact | dependency_graph |
                     approved_harness | ci_import | reviewer_annotation
        source_ref: <stable repository-relative pointer>
        pinned_revision: <optional commit id>
      binding:
        resolved: true | false
        resolution_scope: intra_file | cross_file | repository | external
        unresolved_reasons: []
      limitations: []
  bundle:
    contract_atom_ids: []
    violation_atom_ids: []
    path_atom_ids: []
    consequence_atom_ids: []
    reproduction_atom_ids: []
  blockers: []
  impact_context: <optional non-proof pointer>
```

### 2.2 Evidence bundle

An **evidence bundle** is a set of atoms evaluated together for one finding.
Bundles make the proof boundary explicit:

```text
expected obligation
  + violating behavior
  + feasible path
  + observable consequence
  + no hard blocker
  -> promotion candidate
```

The evidence engine may label a bundle `promotion_candidate`. It must not
change the finding kind, severity, confidence, tags, benchmark verdict, or
review label automatically.

### 2.3 Polarity

Evidence is not positive-only.

| Polarity | Meaning | Example |
| --- | --- | --- |
| `supports` | Moves the lead closer to proof | A mapped test asserts a non-None return |
| `refutes` | Shows that the suspected violation cannot occur on the modeled path | A dominating `if x is None: return` guard |
| `limits` | Narrows the maximum claim strength | A critical call edge remains unresolved |
| `unknown` | Evidence could not be bound safely | Dynamic test generation or `getattr` dispatch |

Negative evidence is first-class. Phase 95E showed why: visible guards were the
dominant misleading-nullability family.

---

## 3. Verification Evidence Types

### 3.1 Test evidence

**Purpose:** Show that repository tests state or observe expected behavior.

Test evidence has two distinct forms:

| Form | Source | Maximum strength | Notes |
| --- | --- | --- | --- |
| Static test expectation | Parsed repository test AST | `E2` | Enriches review; does not prove the test executes or fails |
| Observed test outcome | Imported approved harness or CI result | `E4` | May support a promotion candidate when pinned, deterministic, and bound to the finding |

Static test expectations include:

- `assert fn(...) == expected`;
- `assert fn(...) is not None`;
- `assert fn(...) is None`;
- `pytest.raises(ExpectedError)`;
- direct assertions on returned shape or cardinality.

Static test evidence must include:

- the repository-relative test file;
- the test function;
- the assertion line;
- the resolved subject under test;
- the expected predicate;
- any unresolved binding reason.

Static test evidence must remain `E0` or `E1` when:

- the tested symbol is imported through star import;
- the subject is chosen dynamically;
- a fixture mutates the callable binding;
- parametrization cannot be resolved deterministically;
- the assertion is indirect or free-form;
- third-party behavior is the critical missing link.

Observed test outcomes must include:

- pinned source revision;
- sanitized command fingerprint;
- runner identity and environment fingerprint;
- test id;
- exit status;
- observed failure class;
- deterministic rerun count;
- artifact timestamp;
- source binding.

A failing test is powerful evidence. It is not an automatic defect label. The
failure may be unrelated, stale, flaky, environmental, or caused by the test.

### 3.2 Assertion evidence

**Purpose:** Surface explicit repository invariants and guard conditions.

Assertion evidence includes:

- production `assert x is not None`;
- production `assert len(items) > 0`;
- test assertions;
- explicit guard assertions already extracted by Phase 96 facts.

Assertion evidence can play two roles:

| Role | Example | Effect |
| --- | --- | --- |
| Obligation | `assert result is not None` | Supports a non-None contract |
| Refutation | `assert value is not None` dominates dereference | Refutes an unsafe-dereference path after the assertion |

Production assertions have a strict ceiling of `E2` as obligation evidence
because Python may disable them under optimized execution. They can still be
useful local path evidence when dominance is proven.

Test assertions can contribute to `E3` only when paired with an observed,
pinned test execution record. Without observed execution they remain `E2`.

### 3.3 Contract violation evidence

**Purpose:** State exactly which obligation is violated.

Contract violation evidence is **derived evidence**. It is never created from a
single contract fact.

Required shape:

```text
obligation:
  subject: helper.return
  predicate: return.non_none
  source: explicit type hint

observed incompatible behavior:
  subject: helper.exit_path
  predicate: implicit_none_return
  source: AST return summary

violation:
  predicate: return.non_none violated by implicit_none_return
```

Contract violation evidence may reach `E3` only when:

- the obligation source is explicit and audit-safe;
- the incompatible behavior is directly represented in repository facts;
- the subject binding is exact;
- conflicts are absent;
- any required call edge is resolved;
- a feasible violating path exists or is separately supplied at `E3`.

Contract violation evidence is capped below promotion support when it relies
only on:

- `callee_behavior`;
- free-text docstrings;
- weak caller behavior;
- unresolved unions;
- unresolved call edges;
- impact analysis;
- reviewer notes.

### 3.4 Path feasibility evidence

**Purpose:** Show whether the violating condition can reach the operation after
guards, branches, returns, raises, and resolved calls are accounted for.

Path evidence has two forms:

| Form | Meaning | Maximum strength |
| --- | --- | --- |
| Static path witness | Deterministic branch and call sequence from AST and resolved graph | `E3` |
| Runtime path witness | Imported approved trace or reproduction artifact | `E4` |

A static path witness must record:

- origin;
- branch decisions;
- guard decisions;
- early returns and raises considered;
- call edges traversed;
- unresolved edges;
- destination;
- consequence site.

Path status:

| Status | Meaning |
| --- | --- |
| `feasible` | A complete conservative witness reaches the violation |
| `refuted` | All modeled paths are blocked by a dominating guard, return, raise, or sanitizer |
| `partial` | A possible path exists but one or more critical edges or guards remain unresolved |
| `unknown` | The engine cannot bind the relevant path safely |

Only `feasible` static witnesses with zero critical unresolved edges may reach
`E3`.

`partial` and `unknown` witnesses enrich a lead but never support promotion.

### 3.5 Runtime reproduction evidence

**Purpose:** Record an observed failure tied to the finding and pinned source.

Runtime reproduction is the strongest evidence type, but also the most
sensitive. Phase 97 must treat it as an **imported artifact**, not permission to
execute arbitrary target repository code.

Accepted origins:

- approved local harness result;
- CI result imported from a trusted artifact;
- manually supplied reproduction artifact with command and revision metadata.

Minimum record:

```text
revision
sanitized command fingerprint
environment fingerprint
input fixture fingerprint
exit code
failure class
stack location or assertion location
rerun count
determinism result
subject binding
```

Runtime evidence reaches `E4` only when:

- the source revision matches the analyzed revision;
- the reproduction is deterministic under the defined rerun policy;
- the failure binds to the finding's subject or consequence site;
- the command and input are sanitized for report output;
- no unsafe execution claim is inferred from an opaque third-party failure.

Runtime artifacts that are stale, flaky, unbound, redacted beyond usefulness,
or environment-only remain `E1` or `E2`.

---

## 4. Evidence Strength Levels

| Level | Name | Meaning | Can enrich review? | Can support promotion candidate? |
| --- | --- | --- | --- | --- |
| `E0` | Unknown | Missing, conflicting, stale, or unsafe-to-bind evidence | Yes, as an explicit blocker | No |
| `E1` | Contextual | Useful orientation without proof-grade subject binding | Yes | No |
| `E2` | Grounded support | Repository-grounded and correctly bound, but incomplete proof | Yes | No |
| `E3` | Promotion-supporting | Deterministic static proof component with exact binding and no local conflict | Yes | Yes, as one component of a complete bundle |
| `E4` | Reproduced | Pinned, deterministic observed failure or runtime witness | Yes | Yes, as one component of a complete bundle |

### 4.1 Strength is capped per atom

Strength is not a confidence vibe. It is a maximum claim allowed by provenance
and binding quality.

Examples:

| Evidence | Strength cap | Why |
| --- | --- | --- |
| Impact shows 30 dependents | `E1` | Scope is not proof |
| Reviewer says "looks wrong" | `E1` | Human orientation, not reproducible evidence |
| Explicit `-> str` annotation | `E2` alone | Contract exists, but no violated path proven |
| Explicit non-None contract + bound implicit-None exit | `E3` derived violation atom | Obligation and incompatible behavior are exact |
| Fully resolved unguarded caller dereference path | `E3` | Static consequence path is feasible |
| Pinned failing test reproduced twice | `E4` | Observed deterministic failure |
| Flaky timeout | `E1` | Failure is not deterministic |

### 4.2 No single atom promotes

Even `E4` runtime evidence must be evaluated as part of a bundle. A failing
test can expose:

- a stale test;
- an unrelated failure;
- a fixture bug;
- an environment failure;
- a third-party break;
- an expected negative case.

The evidence engine records what happened and what it binds to. It does not
erase the need for a violated obligation and a consequence.

---

## 5. Promotion Boundaries

### 5.1 Evidence roles

| Evidence source | Enrich a review lead | Support a future promotion candidate | Never support promotion |
| --- | --- | --- | --- |
| Static mapped test expectation | Yes | Only as `E2` context in a larger bundle | Alone |
| Observed pinned deterministic failing test | Yes | Yes, `E4`, when bound to finding | Unbound, flaky, stale, or unrelated failure |
| Production assertion | Yes | Only as local `E2` obligation or path refutation | Alone |
| Test assertion with observed failure | Yes | Yes, as part of `E3`/`E4` bundle | Static-only assertion without execution |
| Explicit type-hint contract | Yes | Yes, as contract component | Alone |
| Phase 96 `caller_behavior` strong | Yes | May strengthen bundle context | Alone |
| Phase 96 `callee_behavior` | Yes, advisory only | No | Always at current audited precision |
| Phase 96 guard fact | Yes | May refute or limit a path after dominance proof | As positive confirmation by itself |
| Free-text docstring | Yes, advisory only | No | Always until parser and quality gate improve |
| Static fully resolved path witness | Yes | Yes, `E3`, as path component | Partial or unresolved witness |
| Runtime reproduction | Yes | Yes, `E4`, when pinned and bound | Unsafe, stale, flaky, or opaque artifact |
| Impact analysis | Yes | No | Always |
| Review usefulness label | Yes | No | Always |

### 5.2 Complete bundle requirements

A future promotion candidate requires all of:

| Bundle component | Minimum evidence |
| --- | --- |
| Expected obligation | One audit-safe `E2` or stronger contract atom |
| Incompatible behavior | One exact `E3` violation atom |
| Feasible path | One `E3` static path witness or `E4` runtime path witness |
| Observable consequence | One exact consequence atom, bound to source or observed failure |
| Conflict review | No unresolved explicit conflict |
| Critical graph edges | Fully resolved or irrelevant to proof |
| Global safety gate | Explicitly enabled only after 0-FP validation |

An `E4` runtime reproduction can satisfy path and consequence components when
the artifact binds directly to the violating source path. It cannot compensate
for an unknown expected obligation.

### 5.3 Initial Phase 97 output ceiling

The initial implementation must cap output at:

```text
enriched_lead
promotion_candidate
refuted
blocked
unknown
```

It must not emit:

```text
confirmed_bug
confirmed_defect
confirmed_actionable
```

Those labels require a separate approval after validation.

---

## 6. Interaction With Existing Phases

### 6.1 Phase 93B `inconsistent_return`

Phase 93B remains unchanged.

Its current rule:

```text
value-return path + implicit fall-through
  + at least one resolved caller dereference
  + no caller null-check
  -> value_flow promotion
```

Phase 97 interprets this as a **candidate source**, not confirmation.

The evidence overlay for one `inconsistent_return` lead should gather:

| Evidence question | Source |
| --- | --- |
| Does the callee have an explicit non-optional return obligation? | Phase 96 explicit type-hint contract |
| Does a reachable exit produce implicit `None` or bare return? | Existing return summary plus path witness |
| Does a resolved caller dereference the result without compensation? | Phase 93B caller usage facts |
| Does any caller null-check the result? | Phase 93B conflict evidence |
| Is there a mapped repository test that states the expected return behavior? | Static test evidence |
| Has an approved test or reproduction observed the consequence? | Imported runtime evidence |

Decision rules:

| Situation | Phase 97 evidence status |
| --- | --- |
| Existing 93B gate not met | `enriched_lead` or `blocked` |
| Explicit return contract, feasible implicit-None path, fully resolved dereference consequence | `promotion_candidate` only |
| Mapped deterministic failing test also binds to consequence | `promotion_candidate` with `E4` reproduction |
| Any caller null-check or explicit Optional contract conflicts | `blocked` or `unknown` |
| Critical cross-file edge unresolved | `blocked` |

Phase 97 must not alter `INTERPROC_PROMOTION_ENABLED`, finding kind, rank, or
benchmark behavior.

### 6.2 Phase 96 contract facts

Phase 96 facts are inputs with source-specific ceilings.

| Phase 96 source | Phase 97 treatment |
| --- | --- |
| Explicit type hint | Allowed as `E2` contract atom |
| Explicit local assert | Allowed as `E2` obligation or refutation atom |
| Strong caller behavior | Allowed as `E2` context and Phase 93B-compatible gate evidence |
| Weak caller behavior | `E1` context only |
| Guard fact | Refutation aid; reaches `E3` only after dominance/path proof |
| Docstring return heuristic | `E1` context only |
| Callee behavior | `E1` context only; never promotion support |
| Test fact without exact binding | `E1` context only |

This follows the Phase 96B quality audit:

- return contracts are the safest current contract type;
- `callee_behavior` over-claims non-None argument obligations;
- guard facts are useful but path-local;
- free-text docstrings are too fragile for proof;
- caller usage is a proto-contract, not an API guarantee.

### 6.3 Impact analysis

Impact analysis stays a non-proof context channel.

Allowed uses:

- prioritize which promotion candidates reviewers inspect first;
- show potentially affected callers, files, and subsystems;
- identify unresolved dependency edges;
- choose where an engineer may add or run a reproduction.

Disallowed use:

```text
many dependents -> stronger defect claim
```

Reachability and blast radius never increase evidence strength.

### 6.4 Review workflow

Phase 95D review packets gain a separate verification section:

```text
VERIFICATION EVIDENCE
status: enriched_lead | promotion_candidate | refuted | blocked | unknown

SUPPORTING EVIDENCE
REFUTING EVIDENCE
MISSING PROOF OBLIGATIONS
RUNTIME OR TEST EVIDENCE
IMPACT CONTEXT (non-proof)
```

Reviewer workflow should preserve current labels while adding evidence-specific
judgments:

| Review field | Values |
| --- | --- |
| Evidence binding correct? | yes / no / unclear |
| Path witness credible? | yes / no / partial / not present |
| Contract source acceptable? | yes / no / unclear |
| Runtime artifact reproducible? | yes / no / not present |
| Promotion candidate accepted? | yes / no / not applicable |
| Rejection reason | structured reason code + note |

Existing human labels remain unchanged:

- `true_positive`
- `false_positive`
- `unclear`
- `useful_advisory`
- `not_useful`

The evidence overlay must not rewrite reviewer decisions.

---

## 7. Hard Non-Promotion Rules

A finding must never become a promotion candidate when any rule below applies.

### 7.1 Missing proof components

- No explicit or audit-safe expected obligation.
- No concrete incompatible behavior.
- No feasible path witness.
- No observable consequence.
- No exact subject binding.
- No pinned source revision for imported runtime evidence.

### 7.2 Ambiguity and unresolved behavior

- Critical dynamic dispatch.
- Critical `getattr`, `eval`, `exec`, or runtime assignment.
- Star-import binding.
- Alias ambiguity.
- Third-party behavior is the critical proof step.
- Shadowed name on the critical path.
- Unresolved call edge on the critical path.
- Conflicting explicit contract sources.

### 7.3 Unsafe evidence sources

- `callee_behavior` used as a contract guarantee.
- Free-text docstring used as promotion proof.
- Impact analysis used as proof.
- Reviewer note used as proof.
- LLM output used as proof.
- Unpinned or stale runtime output.
- Flaky timeout, race, or environment-only failure without deterministic
  reproduction.
- Runtime output with secrets or unsafe raw command payloads copied into
  report artifacts.

### 7.4 Path refutation

- A dominating guard blocks every path.
- An early return, raise, continue, or sanitizer blocks the violating path.
- An explicit Optional contract permits the behavior.
- A test explicitly encodes the behavior as allowed.
- The observed failure is an expected negative test.

### 7.5 Process gates

- `VERIFICATION_EVIDENCE_ENABLED` is false.
- Future `EVIDENCE_PROMOTION_ENABLED` is false.
- Synthetic negative fixtures show any false promotion candidate.
- QuixBugs correct files produce any promotion-candidate false positive.
- Holdout fixed files produce any promotion-candidate false positive.
- Phase 95 pilot replay produces any reviewer-rejected promotion candidate.
- Phase 96D replay produces any unsupported upgrade from `review_lead_only`.

Default rule:

```text
unknown beats guessing
refutation beats weak support
context never masquerades as proof
```

---

## 8. Architecture Design

### 8.1 Layer placement

```text
Existing findings
  + Phase 93 interprocedural facts
  + Phase 96 contract facts
  + repository test/assertion AST facts
  + optional imported approved runtime artifacts
  -> verification evidence atoms
  -> evidence bundle evaluator
  -> verification overlay on existing finding
  -> review packet rendering

Impact analysis
  -> optional prioritization context only
```

### 8.2 Safety separation

The architecture must preserve three separate channels:

| Channel | Purpose | May affect promotion candidate status? |
| --- | --- | --- |
| Proof evidence | Contracts, exact violations, feasible paths, reproduced failures | Yes, after gates |
| Refutation evidence | Guards, allowed Optional behavior, expected negative tests | Yes, to block or refute |
| Context evidence | Impact, weak facts, reviewer notes, unresolved hints | No |

### 8.3 First implementation slice

The smallest safe implementation slice after this design is:

1. Add the evidence record schema.
2. Extract static test expectations and assertions only.
3. Bind them deterministically to existing `inconsistent_return` findings.
4. Attach an evidence overlay to review packets.
5. Keep all outputs capped at `enriched_lead`, `blocked`, `refuted`, or
   `unknown`.
6. Do not ingest runtime artifacts yet.
7. Do not enable promotion-candidate output yet.

This slice is useful because it answers:

```text
Does the repository already contain a checkable statement of expected behavior?
```

It is safe because it does not execute target code and cannot alter findings.

### 8.4 Future runtime boundary

Any later runtime-reproduction ingestion must be an additive, opt-in boundary:

- imported artifact only by default;
- explicit user or CI provenance;
- pinned revision;
- sanitized report payload;
- no arbitrary command execution from repository metadata;
- no network requirement;
- no target repository write.

---

## 9. Zero-FP Validation Strategy

### 9.1 Default-off behavior

Two independent flags are required conceptually:

| Flag | Default | Effect |
| --- | --- | --- |
| `VERIFICATION_EVIDENCE_ENABLED` | `False` during bring-up | Attaches evidence overlays only |
| `EVIDENCE_PROMOTION_ENABLED` | `False` until separately approved | Allows promotion-candidate status only; never changes findings automatically |

Turning either flag off must restore the Phase 96C review-packet behavior.

### 9.2 Synthetic test matrix

Mandatory fixtures:

| Family | Positive case | Negative or blocking case |
| --- | --- | --- |
| Test mapping | Direct imported function with explicit assertion | Star import, dynamic lookup, fixture rebinding |
| Assertions | `assert result is not None` bound to subject | Unrelated assertion in same file |
| Contract violation | `-> str` plus feasible implicit `None` exit | `-> str | None`, raise-only exit |
| Caller consequence | Resolved dereference without null check | Caller null-check, optional branch |
| Path feasibility | Unguarded fall-through reaches dereference | Dominating `if x is None: return` |
| Runtime artifact parsing | Pinned deterministic failing test artifact | Stale revision, flaky timeout, unrelated failure |
| Impact context | Impact attached after evidence | Impact-only lead never becomes candidate |
| Security boundary | Secrets redacted in imported command/output | Raw token never written to artifact |

### 9.3 Corpus gates

Before promotion-candidate output is enabled:

```text
Synthetic suite:
  100% exact expected overlay statuses
  0 false promotion candidates

QuixBugs correct files:
  0 promotion-candidate false positives

Holdout fixed files:
  0 promotion-candidate false positives

QuixBugs buggy and holdout buggy:
  benchmark TP/FP unchanged

Phase 95C/95E pilot replay:
  0 reviewer-rejected promotion candidates
  misleading guard cases remain blocked or refuted

Phase 96D inconsistent_return replay:
  no unsupported upgrade from review_lead_only
  every candidate records its full proof bundle and blockers
```

### 9.4 Historical positive validation

0-FP discipline alone is insufficient. A useless engine can achieve zero false
positives by producing nothing.

Before external promotion claims:

- preregister historical defect cases;
- pin buggy and fixed revisions;
- verify evidence overlay differs in the expected direction;
- require at least one accepted promotion candidate from a historical case;
- confirm that the fixed revision removes or refutes the candidate;
- report candidate precision and candidate recall separately from detector
  benchmark metrics.

### 9.5 Metrics

Required metrics:

| Metric | Meaning |
| --- | --- |
| `evidence_atom_count_by_type` | Volume by test, assertion, violation, path, runtime |
| `evidence_atom_count_by_strength` | `E0` through `E4` distribution |
| `enriched_lead_count` | Leads with at least one bound atom |
| `refuted_lead_count` | Leads blocked by negative evidence |
| `blocked_lead_count_by_reason` | Why proof could not close |
| `promotion_candidate_count` | Bundles meeting future gate |
| `reviewer_accepted_candidate_count` | Human-accepted candidates |
| `candidate_precision` | Accepted candidates / reviewed candidates |
| `candidate_false_positive_count` | Reviewer-rejected candidates |
| `historical_case_recall` | Historical defects with accepted candidate / historical defects reviewed |
| `benchmark_parity` | QuixBugs and holdout detector output unchanged |

---

## 10. Tests Needed

### 10.1 Schema and determinism

- Evidence records are JSON-serializable.
- IDs are stable for identical inputs.
- Atom ordering is deterministic.
- Repository-relative paths are used.
- Raw secrets are not exported.
- Flag-off behavior returns the pre-Phase 97 packet shape.

### 10.2 Test evidence

- Directly imported test subject binds.
- `module.symbol` test subject binds.
- Static assertion extracts expected predicate.
- `pytest.raises` extracts expected exception.
- Star imports do not bind.
- Dynamic lookup does not bind.
- Ambiguous aliases do not bind.
- Third-party tested subjects do not bind as project proof.

### 10.3 Assertion evidence

- Local production assert extracts obligation.
- Dominating assertion refutes a later unsafe dereference path.
- Non-dominating assertion does not refute sibling paths.
- Unrelated assertion does not bind to finding.
- Production assertion alone never creates promotion-candidate status.

### 10.4 Contract violation evidence

- Explicit non-optional return plus feasible fall-through creates derived
  violation atom.
- Optional return contract blocks violation.
- Conflicting contract facts produce `blocked`.
- `callee_behavior` alone never creates violation proof.
- Free-text docstring alone never creates violation proof.

### 10.5 Path feasibility

- Unguarded implicit-None exit to resolved caller dereference produces `E3`
  static witness.
- Null-checking caller blocks candidate.
- Dominating `if x is None: return` refutes path.
- Raise-only branch does not count as implicit-None exit.
- Critical unresolved cross-file edge caps output at `blocked`.
- Impact-only context never raises evidence strength.

### 10.6 Runtime artifact ingestion

- Pinned deterministic failure imports as `E4`.
- Revision mismatch downgrades to stale blocker.
- Unrelated failing test does not bind.
- Flaky reruns do not reach `E4`.
- Secrets in command or output are redacted.
- Artifact ingestion never executes a command.

### 10.7 Regression

- Phase 93B behavior unchanged.
- Phase 96C packet enrichment unchanged when evidence is flag-off.
- QuixBugs unchanged.
- Holdout unchanged.
- Target repositories remain unmodified.
- No detector reads verification evidence.
- No finding kind, severity, confidence, rank, or tags change from evidence.

---

## 11. Likely Future Files

This design adds no implementation files. A later scoped implementation would
likely touch only:

| File | Reason |
| --- | --- |
| `builder_core/bug_intelligence/verification_evidence.py` | New evidence schema, extraction, and bundle evaluation |
| `builder_core/bug_intelligence/finding.py` | Optional `verification_evidence` attachment on existing finding schema |
| `builder_core/bug_intelligence/engine.py` | Additive post-ranker evidence enrichment call |
| `builder_core/bug_intelligence/contract_enrichment.py` | Preserve and render relationship between contract and verification overlays |
| `builder_core/bug_intelligence/agents.py` | CLI evidence formatting only |
| `builder_core/real_repo_validation/harness.py` | Export overlay in reviewer packets |
| `builder_core/real_repo_validation/review_tool.py` | Show verification sections and structured reviewer fields |
| `builder_core/tests/test_phase97_verification_evidence.py` | New synthetic and regression suite |

Optional later runtime-artifact ingestion should live in a separate module so
static evidence extraction remains read-only and independently disableable.

Legacy paths, benchmarks, detectors, browser code, voice code, trading code,
and website code must remain untouched.

---

## 12. Acceptance Criteria

Phase 97 design is accepted when implementation can satisfy all of:

1. Evidence is represented as typed, deterministic, JSON-serializable atoms.
2. The five required evidence types exist.
3. Strength levels `E0` through `E4` are enforced by provenance and binding.
4. Supporting, refuting, and limiting evidence are all preserved.
5. Existing findings are enriched, not replaced.
6. Phase 93B `inconsistent_return` behavior remains unchanged.
7. Phase 96 facts keep source-specific strength ceilings.
8. Impact analysis remains non-proof context only.
9. Reviewer packets show evidence and missing proof obligations clearly.
10. Static extraction never executes target code.
11. Imported runtime artifacts never cause command execution.
12. No automatic `confirmed_bug`, `confirmed_defect`, or
    `confirmed_actionable` output exists.
13. QuixBugs and holdout detector outputs remain unchanged.
14. Promotion-candidate output remains disabled until a separately reviewed
    0-FP gate passes.
15. Turning the evidence layer off restores Phase 96C behavior.

---

## 13. Rollback Plan

Rollback must be immediate and local:

1. Set `VERIFICATION_EVIDENCE_ENABLED=False`.
2. Do not attach evidence overlays to findings or reviewer packets.
3. Preserve Phase 96C contract review packets unchanged.
4. Leave Phase 93B promotion behavior unchanged.
5. Leave detectors, benchmarks, ranking, impact analysis, and review labels
   unchanged.

No data migration is required. Evidence artifacts are additive and disposable.

---

## 14. Final Recommendation

Proceed with a **static, review-only Phase 97A evidence overlay** first:

- mapped test expectations;
- explicit assertions;
- deterministic subject binding;
- evidence blockers;
- no target execution;
- no promotion-candidate output;
- no confirmed-defect output.

This is the smallest safe step from:

```text
Here is a useful lead.
```

to:

```text
Here is the repository evidence that supports or blocks this lead, and here is
the exact proof still missing.
```

That is the right foundation for confirmation without sacrificing the existing
0-FP discipline.

