# Repository Intelligence Gap Analysis v2

Date: 2026-05-31

Scope: Evidence-only capability assessment. No implementation, code changes,
roadmap, detector proposals, benchmark changes, or promotion changes.

## Executive Answer

The shortest credible path from current Builder Core to:

> JARVIS tells developers what is broken.

is no longer blocked by basic repository understanding. RU-2, the dependency
graph, and the Phase 95 validation workflow now provide a solid foundation.

The remaining product gap is a chain of missing conclusions:

```text
review lead
  -> affected surface
  -> confirmed failure condition
  -> root-cause evidence chain
  -> bounded repair candidate
  -> verified repair outcome
```

Two statements must remain separate:

1. **Largest truth blocker:** defect confirmation. Builder Core still cannot
   generally distinguish a useful review lead from a confirmed real-repository
   defect.
2. **Single highest-leverage capability to build next:** the designed
   **Impact Analysis Engine**. It is the most implementation-ready, lowest-risk
   missing consumer of the completed dependency graph, and it supplies
   affected-surface context required by root-cause analysis, repair generation,
   and repair verification.

Impact analysis alone will not prove that code is broken. It is the highest
leverage next capability because it turns repository structure into usable
change and diagnosis context without weakening Builder Core's precision-first
trust model.

## 1. Re-Evaluated Current Capabilities

### 1.1 Repository Understanding: Complete

RU-2 established deterministic repository structure in the index and ask path.

| Capability | Evidence | Current boundary |
| --- | --- | --- |
| File roles | Files classified as production code, test, benchmark, dataset, generated, report history, architecture doc, general doc, config, or unknown | Path-based role model, not semantic ownership |
| Architecture retrieval routing | Production code and architecture docs preferred; reports capped at 20%; benchmarks and datasets excluded | Retrieval quality guard, not architecture correctness proof |
| Subsystem map | Name, role, file count, entry files, dependencies, role counts | Top-level subsystem view |
| Ask quality metrics | Source distribution plus production, architecture, report, and benchmark percentages | Measures source composition, not answer truth |
| Real repository measurement | `local_jarvis`: 4,060 files indexed and required architecture questions answered from real subsystems | Static repository view |

RU-2 successfully prevented architecture answers from drifting into BugsInPy,
QuixBugs, pandas, thefuck, or historical report content.

### 1.2 Static Bug Intelligence: Available but Review-Oriented

| Capability | Evidence | Current boundary |
| --- | --- | --- |
| Unified engine | Python AST parse -> facts -> agents -> ranked findings | Static analysis only |
| Unified finding schema | Category, kind, severity, confidence, evidence, explanation, why-it-might-be-wrong, next verification step | Explanation packet, not defect confirmation |
| Data-flow and value-flow facts | Loops, containers, branches, returns, nullability, intervals, taint | Conservative and incomplete around some visible guards |
| Semantic algorithm profiles | BFS, DFS, shortest path, sorting, recursion, graph/tree traversal, dynamic programming | Controlled benchmark coverage |
| Intra-file interprocedural facts | Call graph and bounded summaries | Static direct-call coverage |
| Cross-file facts | Conservative import-table-based resolution | Gated consumption; unresolved relationships stay unknown |
| Security review leads | Taint-based sink findings | Not validated as exploit claims |

The static engine is useful, but Phase 95 showed that useful output is not the
same as a confirmed defect.

### 1.3 Dependency Graph: Complete

Phase 94A added a deterministic structure-only graph.

| Graph surface | Available evidence |
| --- | --- |
| Nodes | Repository, module, class, function |
| Edges | Contains, imports, calls, references |
| Resolution rule | Resolved static edges only |
| Unknown handling | Unresolved imports, calls, and references recorded separately |
| Export | Byte-identical deterministic JSON for identical source |
| Statistics | Counts, fan-in lists, components, cycles, unresolved counts |
| Safety | Additive engine entry point; no detector or benchmark consumption |

The graph can describe how resolved code structure is wired. It does not yet
answer reverse-impact questions as a product capability.

### 1.4 Impact Analysis: Design Complete, Capability Absent

Phase 94B defines a complete design for a downstream Impact Analysis Engine.
No implementation has shipped.

The design already specifies:

- direct dependents for files, modules, and functions;
- transitive reverse reachability;
- resolved entrypoint-to-target execution paths;
- blast-radius risk scoring;
- confidence scoring based on unresolved structure;
- separate asserted, possible-unverified, and unanalyzed channels;
- deterministic output;
- explicit unknown outcomes instead of false safety claims.

This distinction matters:

| State | Meaning |
| --- | --- |
| Dependency graph complete | Structural source facts exist |
| Impact design complete | Product semantics and safety contract are specified |
| Impact analysis capability | **Not yet available** |

### 1.5 Real-Repository Validation: Operationally Complete, Product Claim Still Held

Phase 95 established a deterministic read-only validation harness and completed
the first pilot human review.

| Evidence | Value |
| --- | ---: |
| Public pilot repositories | 2 |
| Grounded findings reviewed | 202 |
| Human-confirmed actionable defects | **0** |
| Useful review leads | **148 (73.3%)** |
| Misleading findings | **15 (7.4%)** |
| Benign or not useful | **34 (16.8%)** |
| Unclear | **5 (2.5%)** |
| Target repository writes | **0** |
| External-alpha verdict | **HOLD** |

Curated benchmark evidence remains bounded:

| Corpus | True positives | False positives | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| QuixBugs | 12 / 40 | 0 | 1.0000 | 0.3000 |
| Holdout | 2 | 0 | 1.0000 | 0.1667 |

The evidence supports:

> Builder Core identifies useful places to investigate.

The evidence does not yet support:

> Builder Core identifies confirmed defects in arbitrary repositories.

## 2. Shortest Capability Chain

The shortest path is a dependency chain, not a roadmap.

| Capability layer | Why it is required | Current state |
| --- | --- | --- |
| Repository structure | Locate production code, tests, architecture sources, and subsystems | Complete |
| Dependency graph | Represent resolved structural relationships and unknowns | Complete |
| Impact analysis | Describe what may be affected and how complete that answer is | Designed only |
| Defect confirmation | Separate broken behavior from plausible risk | Missing |
| Root-cause analysis | Explain the earliest actionable cause and its evidence chain | Missing |
| Repair generation | Suggest a bounded contract-restoring correction | Missing |
| Repair verification | Demonstrate that the correction resolves the failure without known regression | Missing |

The smallest useful closed loop is:

```text
confirmed failure
  + affected surface
  + causal explanation
  + bounded repair
  + verification result
```

Repository understanding and the dependency graph are foundations. Impact
analysis is the missing bridge from foundation to diagnosis context. Defect
confirmation remains the gate that prevents review leads from being mislabeled
as broken code.

## 3. Remaining Gaps Ranked by Leverage

| Rank | Capability gap | Value | Difficulty | Risk | Dependency chain |
| ---: | --- | --- | --- | --- | --- |
| 1 | **Impact Analysis Engine** | Converts the completed graph into direct dependents, transitive blast radius, resolved execution paths, and confidence-aware unknowns. Supports diagnosis, repair scoping, and test selection. | Medium | Low to medium: false safety claims if unresolved edges are hidden | RU-2 + dependency graph -> impact context |
| 2 | **Defect confirmation and evidence threshold** | Separates a useful review lead from a claim that behavior is actually broken. Directly addresses the Phase 95 result of 0/202 confirmed defects. | High | High: premature promotion destroys trust | Static finding + reproduction, invariant, contract, or human evidence -> confirmed defect or retained lead |
| 3 | **Root-cause evidence chain** | Replaces sink-level warnings with origin -> propagation -> violated contract -> consequence explanations. | High | High: correlation can be mislabeled as causality | Confirmed failure + impact context + flow/call facts -> causal explanation with unknowns |
| 4 | **Test and reproduction binding** | Anchors a defect claim to expected behavior and supplies the strongest repair-verification target. | Medium to high | Medium: weak test association can imply coverage that does not exist | Finding + relevant tests or minimal reproduction -> failure condition |
| 5 | **Change-aware regression context** | Distinguishes newly introduced breakage from long-standing risk and narrows likely causal edits. | Medium | Medium: history is suggestive, not causal proof | Git history + diff + impact context + confirmed failure -> regression evidence |
| 6 | **Bounded repair generation** | Turns a diagnosis into an actionable correction while preserving contract and scope discipline. | High | High: plausible patches can be behaviorally wrong | Confirmed root cause + impact surface + contract evidence -> repair candidates |
| 7 | **Repair verification closure** | Converts a proposed patch into a defensible outcome: verified, partially verified, blocked, ambiguous, or regressed elsewhere. | High | High: unavailable checks must never be rendered as success | Repair candidate + reproduction + affected tests/checks + impact surface -> verification result |
| 8 | **Semantic architecture overlays** | Adds entrypoint, public-surface, contract, configuration, and ownership meaning to structural edges. | High | Medium: semantic labels may overstate certainty | RU-2 + dependency graph + repository conventions -> architecture context |
| 9 | **Developer-facing issue packet** | Gives engineers one coherent object: defect status, evidence chain, affected surface, repair boundary, and verification status. | Medium | Low: presentation risk if certainty labels blur | Confirmation + root cause + impact + repair + verification -> usable developer conclusion |
| 10 | **Coverage and validation breadth** | Establishes where claims generalize beyond Python fixtures and two pilot repositories. | High | Medium: benchmark success can be mistaken for production truth | Capability outputs + preregistered real-repo evidence -> bounded trust claim |

### Ranking Interpretation

The ranking optimizes leverage, not theoretical importance.

- **Impact analysis** ranks first because its design is complete, its substrate
  exists, and it safely unlocks context used by several later capabilities.
- **Defect confirmation** is the largest truth blocker because no later output
  can honestly say "broken" without it.
- **Root-cause analysis** depends on both: confirmation establishes the failure;
  impact context constrains where to trace and what may be affected.
- **Repair generation and verification** remain downstream because a patch
  should not be generated or certified against an unconfirmed diagnosis.

## 4. Blocker Matrix

Legend:

- **Direct blocker**: the target capability cannot be trustworthy without it.
- **Major input**: the target capability can exist in a limited form, but loses
  important value or confidence.
- **Supporting**: useful but not required for a narrow first form.
- **No direct block**: largely independent.

| Gap | Root-cause analysis | Impact analysis | Repair generation | Repair verification |
| --- | --- | --- | --- | --- |
| Impact Analysis Engine | **Major input** | **Direct blocker** | **Major input** | **Major input** |
| Defect confirmation threshold | **Direct blocker** | Supporting | **Direct blocker** | **Direct blocker** |
| Root-cause evidence chain | Target capability | Supporting | **Direct blocker** | **Major input** |
| Test and reproduction binding | **Major input** | Supporting | **Major input** | **Direct blocker** |
| Change-aware regression context | **Major input** | Supporting | **Major input** | Supporting |
| Bounded repair generation | No direct block | No direct block | Target capability | **Direct blocker** |
| Repair verification closure | No direct block | No direct block | Supporting | Target capability |
| Semantic architecture overlays | **Major input** | **Major input** | **Major input** | Supporting |
| Developer-facing issue packet | Supporting | Supporting | Supporting | Supporting |
| Coverage and validation breadth | Trust gate | Trust gate | Trust gate | Trust gate |

## 5. Gap Evidence

### 5.1 Impact Analysis Engine

**Value:** High.

The dependency graph exists, but its forward edges are not yet exposed as
developer answers to:

- what files depend on this file;
- what functions depend on this function;
- what modules import this module;
- what resolved execution paths reach this code;
- what may break if this changes.

Phase 94B defines those questions, confidence rules, and safety wording. The
missing capability is not conceptual ambiguity; it is the absence of a shipped
downstream consumer.

**Difficulty:** Medium.

The design consumes existing graph facts. Its complexity lies in preserving the
three-channel contract:

- asserted resolved impact;
- possible but unverified impact;
- unanalyzed or degraded surface.

**Risk:** Low to medium.

The primary failure mode is false reassurance. A sparse static graph must never
turn "no resolved path found" into "safe" or "unreachable."

**Dependency chain:**

```text
RU-2 roles and subsystems
  + Phase 94A dependency graph
  + explicit unresolved edges
  -> confidence-aware impact analysis
```

### 5.2 Defect Confirmation and Evidence Threshold

**Value:** Critical.

Phase 95's real-repository pilot produced 148 useful review leads but zero
confirmed actionable defects. This is the central truth gap.

Confirmation requires evidence that a reported condition violates expected
behavior, not merely that a suspicious static shape exists.

**Difficulty:** High.

Confirmation may depend on different evidence classes:

- violated invariant;
- caller/callee contract mismatch;
- failing existing test;
- minimal reproduction;
- historical regression boundary;
- human confirmation where static proof is incomplete.

**Risk:** High.

If a review lead is promoted too easily, the product becomes confidently wrong.
If promotion is too strict, Builder Core remains useful but cannot make the
target claim.

**Dependency chain:**

```text
static finding
  + expected behavior evidence
  + uncertainty accounting
  -> confirmed defect or retained review lead
```

### 5.3 Root-Cause Evidence Chain

**Value:** Critical.

A developer needs the earliest actionable cause, not only the exception,
dereference, sink, or suspicious line.

A complete explanation needs:

```text
origin
  -> propagation
  -> branch or state transition
  -> contract violation
  -> visible consequence
```

**Difficulty:** High.

Static facts are incomplete around dynamic dispatch, framework behavior, and
runtime state. Root-cause analysis must preserve competing hypotheses and
unknowns.

**Risk:** High.

Dependency or call adjacency is not proof of causality. The system must not
turn a reachable neighbor into a causal claim.

**Dependency chain:**

```text
confirmed failure
  + data/value-flow facts
  + call facts
  + impact context
  -> evidence-backed causal explanation
```

### 5.4 Test and Reproduction Binding

**Value:** High.

A reproduction or relevant failing test strengthens both defect confirmation
and repair verification. It also gives developers a concrete starting point.

**Difficulty:** Medium to high.

Indexed tests exist as source evidence, but Builder Core does not yet provide a
general relationship between changed or suspicious code, relevant tests, and
the expected behavior they encode.

**Risk:** Medium.

A nearby test is not necessarily a covering test. Relationship evidence must
not be overstated as execution coverage.

**Dependency chain:**

```text
finding or target symbol
  + dependency/impact context
  + indexed tests and contracts
  -> relevant test set or minimal reproduction target
```

### 5.5 Change-Aware Regression Context

**Value:** High.

Developers often need to know whether a failure was introduced by the current
patch, a recent change, or a long-standing condition. Git history is indexed,
but not central to diagnosis.

**Difficulty:** Medium.

Historical proximity is easier to establish than causal responsibility.

**Risk:** Medium.

The most recent edit near a failure is not necessarily the root cause.

**Dependency chain:**

```text
confirmed failure
  + impacted surface
  + diff and history evidence
  -> bounded regression context
```

### 5.6 Bounded Repair Generation

**Value:** High.

The target product promise becomes practically useful when JARVIS can describe
the smallest plausible correction and the contract it restores.

**Difficulty:** High.

The same defect may support multiple valid repair boundaries: reject invalid
input, normalize earlier, restore a callee contract, or handle an optional
result in a caller.

**Risk:** High.

A syntactically valid patch can repair a symptom, widen a public contract, or
introduce a regression.

**Dependency chain:**

```text
confirmed root cause
  + impacted callers/interfaces/tests
  + contract evidence
  -> bounded repair candidates with stated assumptions
```

### 5.7 Repair Verification Closure

**Value:** Critical.

A proposed repair is still a hypothesis until evidence shows that the failure
disappeared without known regression.

**Difficulty:** High.

Repositories differ in available tests, build tools, dependencies, and safe
execution boundaries.

**Risk:** High.

Unavailable, skipped, or blocked checks must never appear as success.

**Dependency chain:**

```text
repair candidate
  + reproduction
  + affected tests/checks
  + impact surface
  -> verified, partially verified, blocked, ambiguous, or regressed
```

### 5.8 Semantic Architecture Overlays

**Value:** Medium to high.

RU-2 and the graph explain structure. They do not yet establish:

- public versus internal API surface;
- runtime entrypoint behavior;
- framework wiring;
- configuration relationships;
- subsystem contracts;
- ownership;
- mixed-language boundaries.

**Difficulty:** High.

Repository conventions vary, and runtime behavior cannot be inferred safely
from static adjacency alone.

**Risk:** Medium.

Architecture labels can become polished speculation unless their provenance and
confidence remain explicit.

**Dependency chain:**

```text
RU-2 structure
  + dependency graph
  + explicit repository evidence
  -> confidence-scoped architecture meaning
```

### 5.9 Developer-Facing Issue Packet

**Value:** Medium.

Developers need one coherent answer rather than disconnected graph, finding,
and test outputs.

The useful packet contains:

- status: confirmed defect, review lead, advisory, or unknown;
- failure condition;
- evidence chain;
- affected surface;
- unresolved caveats;
- repair boundary;
- verification result.

**Difficulty:** Medium.

The packet is primarily synthesis of existing and missing capability outputs.

**Risk:** Low.

The main risk is presentation blur: a polished packet must not visually erase
the distinction between confirmed and unconfirmed evidence.

**Dependency chain:**

```text
confirmation
  + root cause
  + impact
  + repair
  + verification
  -> developer-facing conclusion
```

### 5.10 Coverage and Validation Breadth

**Value:** High for trust, lower for immediate functionality.

Builder Core remains Python-focused, benchmark recall remains limited, and the
real-repository pilot covered two repositories rather than the full primary
corpus.

**Difficulty:** High.

Generalization evidence requires independent repositories, historical bugs,
human review, and careful claim boundaries.

**Risk:** Medium.

The dominant danger is overstating bounded benchmark results as broad product
truth.

**Dependency chain:**

```text
capability outputs
  + preregistered real-repository evidence
  + historical bug evidence
  + human review
  -> bounded product trust claim
```

## 6. Single Highest-Leverage Capability

The single highest-leverage capability to build next is:

> **Impact Analysis Engine: confidence-aware reverse dependency and blast-radius
> analysis over the completed deterministic dependency graph.**

### Why This Ranks First

| Reason | Evidence |
| --- | --- |
| Substrate already exists | Phase 94A shipped deterministic nodes, edges, unresolved channels, exports, and statistics |
| Design already exists | Phase 94B specifies direct impact, transitive impact, execution paths, risk, confidence, unresolved handling, and safety wording |
| Low architectural risk | Pure downstream consumer; no detector, benchmark, finding, or promotion change required |
| High reuse | Supplies context for root-cause analysis, repair scope, relevant-test selection, regression review, and verification |
| Trust-preserving | Explicitly separates asserted impact from possible-unverified and unanalyzed surface |
| Honest product improvement | Answers "what may be affected?" without falsely claiming "this is broken" |

### What It Does Not Solve

Impact analysis does not:

- confirm a defect;
- establish causal root cause;
- generate a correct repair;
- prove a repair is safe;
- convert unresolved dynamic behavior into known edges.

Its value is that it is the missing structural bridge between today's
repository graph and tomorrow's evidence-backed diagnosis loop.

## 7. Root-Cause, Impact, Repair, and Verification Boundaries

### Root-Cause Analysis

Blocked primarily by:

1. defect confirmation;
2. root-cause evidence chains;
3. test and reproduction binding.

Improved substantially by:

- impact analysis;
- change-aware regression context;
- semantic architecture overlays.

### Impact Analysis

Blocked directly by:

1. the absent Impact Analysis Engine.

The design is complete. The graph substrate is complete. Confidence must remain
bounded by unresolved and unanalyzed structure.

### Repair Generation

Blocked primarily by:

1. defect confirmation;
2. root-cause evidence chain;
3. impact analysis;
4. contract and test evidence.

Generating repairs before those inputs exist would convert review leads into
speculative edits.

### Repair Verification

Blocked primarily by:

1. reproduction or relevant test binding;
2. impact analysis for affected checks and interfaces;
3. bounded repair candidate;
4. honest verification status.

A missing test environment, blocked command, or unavailable dependency must be
reported as incomplete verification, never success.

## 8. Evidence-Supported Conclusion

Current Builder Core is no longer missing repository structure. It is missing
the chain that turns structure and review leads into a defensible engineering
conclusion.

The shortest path is governed by this dependency logic:

```text
completed repository understanding
  + completed dependency graph
  -> confidence-aware impact analysis
  -> defect confirmation and reproduction evidence
  -> root-cause explanation
  -> bounded repair candidate
  -> verification closure
```

The first missing capability with the best leverage-to-risk ratio is impact
analysis.

The final truth gate remains defect confirmation.

Until both are present and validated, the honest statement remains:

> JARVIS tells developers where to investigate and what may be affected.

Not yet:

> JARVIS tells developers what is broken.

## Local Evidence Used

- `reports/ru2_repository_understanding_v1.md`
- `reports/phase93d_cross_file_consumer_mechanism.md`
- `reports/phase94a_dependency_graph_implementation.md`
- `reports/phase94b_impact_analysis_design.md`
- `reports/phase95c_first_real_repository_validation_report.md`
- `reports/phase95e_pilot_human_review_results.md`
- `reports/phase95g_product_positioning.md`
- `reports/repository_intelligence_gap_analysis.md`

