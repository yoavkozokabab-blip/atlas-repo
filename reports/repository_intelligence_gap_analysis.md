# Repository Intelligence Gap Analysis

Date: 2026-05-31

Scope: Capability assessment only. No implementation plan, roadmap tasks, code
changes, detector proposals, or benchmark changes.

## Executive Answer

Builder Core has crossed an important threshold: it can understand repository
shape, retrieve architecture-relevant source, assemble a conservative static
dependency graph, and produce ranked evidence-backed review leads without
executing or modifying target code.

It has **not** crossed the threshold implied by:

> JARVIS tells developers what is broken.

Today, Builder Core can more honestly say:

> JARVIS tells developers where to investigate, what static evidence triggered
> concern, and why the concern may be wrong.

The largest remaining gap is not another detector family. It is a trustworthy
closed evidence loop:

```text
signal
  -> defect confirmation
  -> root-cause explanation
  -> impact understanding
  -> bounded repair suggestion
  -> verification evidence
  -> developer-facing conclusion
```

The real-repository pilot makes that distinction concrete:

| Pilot result | Value |
| --- | ---: |
| Human-reviewed grounded findings | 202 |
| Human-confirmed actionable defects | **0** |
| Useful review leads | **148 (73.3%)** |
| Misleading findings | **15 (7.4%)** |
| Benign or not useful | **34 (16.8%)** |
| Unclear | **5 (2.5%)** |

Builder Core already has good review substrate. It still lacks enough
confirmation, causality, repair, and verification intelligence to make a
definitive broken-code claim on ordinary repositories.

## 1. Current Capability Map

### 1.1 Repository Understanding

| Capability | Current state | Confidence boundary |
| --- | --- | --- |
| File role classification | Available: production code, test, benchmark, dataset, generated, report history, architecture doc, general doc, config, unknown | Deterministic path-based classification, not semantic ownership |
| Architecture-oriented retrieval | Available: source and architecture docs preferred; reports capped; benchmarks excluded | Strong for avoiding irrelevant benchmark/report contamination |
| Subsystem discovery | Available: top-level subsystem name, role, file count, entry files, dependencies, role counts | Static top-level map, not a runtime service model |
| Ask quality metrics | Available: source distribution plus production, architecture, report, and benchmark percentages | Measures retrieval composition, not answer correctness |
| Local repository indexing | Available under `.jarvis_builder/` | Read-only except explicit Builder index artifacts |

RU-2 validated architecture answers against real `local_jarvis` subsystems.
The required questions cited production sources such as `voice/voice_loop.py`
and `voice/wakeword.py`, with `0%` benchmark and report-history contamination.

### 1.2 Static Program Intelligence

| Capability | Current state | Confidence boundary |
| --- | --- | --- |
| Python AST parsing | Available | Python-focused; static syntax view only |
| Unified finding schema | Available: category, kind, severity, confidence, evidence, explanation, why-it-might-be-wrong, next verification step | Findings are review leads unless independently confirmed |
| Pattern and semantic checks | Available | Controlled rule families, intentionally recall-limited |
| Data-flow facts | Available | Static and bounded |
| Value-flow and nullability facts | Available | Pilot exposed missed visible guards |
| Taint and security leads | Available | Pilot exposed locally controlled argv/path false positives |
| Intra-file call summaries | Available | Conservative, bounded, static |
| Cross-file call facts | Available behind conservative resolution and gates | Unknown relationships remain unresolved rather than guessed |
| Test-aware reasoning | Available in bounded cases | Not yet a general test-contract model |

### 1.3 Dependency Graph

| Capability | Current state | Confidence boundary |
| --- | --- | --- |
| Node model | Available: repository, module, class, function | Structural identities only |
| Edge model | Available: contains, imports, calls, references | Resolved static relationships only |
| Unknown handling | Available: unresolved imports, calls, references are explicit | Dynamic dispatch and runtime wiring are intentionally not inferred |
| Deterministic export | Available | Snapshot graph; no incremental cache |
| Statistics | Available: counts, top imports/calls, components, import cycles, unresolved counts | Descriptive, not causal |

The dependency graph is a useful substrate for impact analysis. It does not by
itself establish that a defect exists, that an edge participates in a failing
runtime path, or that a proposed change is safe.

### 1.4 Validation and Safety

| Capability | Current state | Evidence boundary |
| --- | --- | --- |
| Curated algorithm benchmark | QuixBugs: 12/40 true positives, 0 false positives, precision 1.0, recall 0.30 | Strong but narrow paired-benchmark evidence |
| Holdout benchmark | 2 true positives, 0 false positives, precision 1.0, recall 0.1667 | Strong but narrow external fixture evidence |
| Real-repository harness | Available: manifests, deterministic exports, review packets, dual review, adjudication, aggregate reporting | Operationally validated |
| Real-repository defect claim | Not established | 0/202 confirmed actionable defects in the first pilot |
| Read-only posture | Established | No target code execution and no target source modification |

### 1.5 Honest Product Position Today

Builder Core is currently a **local deterministic Review Intelligence System**
and **Risk Discovery Tool** for Python repositories.

Its strongest proven behavior is:

- understanding repository structure;
- surfacing ranked static review leads;
- showing evidence and uncertainty;
- preserving a read-only trust boundary;
- avoiding unsupported claims when resolution is ambiguous.

Its weakest unproven behavior is the actual product promise under assessment:

- reliably identifying a real defect;
- distinguishing cause from symptom;
- describing the affected behavior;
- suggesting a repair;
- verifying the repair.

## 2. Missing Capability Map

| Missing capability | Why it blocks "what is broken" | Current nearest substrate |
| --- | --- | --- |
| Defect confirmation | A risk lead is not a broken-behavior claim | Finding schema, human review harness |
| Causal root-chain reasoning | Developers need the earliest actionable cause, not only the sink or suspicious line | Data-flow, value-flow, call facts |
| Impact analysis | Developers need to know what callers, modules, tests, and interfaces may be affected | Dependency graph |
| Reproduction binding | A defect claim is stronger when linked to a failing test, violated invariant, or reproducible path | Test-aware semantic checks |
| Repair suggestion quality | "Broken" becomes useful when paired with the smallest plausible correction | Evidence-backed finding explanations |
| Verification closure | A proposed repair needs proof that the failure disappeared without regression | Next-verification-step text only |
| Semantic architecture model | Static edges do not identify boundaries, entry points, contracts, or runtime responsibilities | RU-2 subsystem map, dependency graph |
| Change-aware reasoning | Many real defects are regressions introduced by a specific diff | Indexed Git history |
| Developer workflow integration | Findings must arrive where engineers investigate, review, and validate changes | CLI and deterministic exports |
| Broader language and framework coverage | Python AST intelligence cannot explain breakage in mixed-language systems | Repository role index |

The decisive product gap is **closure**. Builder Core can start an
investigation; it cannot yet finish one with a defensible defect statement.

## 3. Root-Cause Analysis Requirements

Root-cause analysis must answer more than "this line looks risky." A useful
developer-facing diagnosis needs the following properties.

### 3.1 Confirmed Failure Condition

The system must state the condition under which behavior becomes incorrect:

- the input, state, branch, or call sequence that exposes the defect;
- the violated invariant or contract;
- whether the failure is guaranteed, plausible, or still unconfirmed;
- the evidence that separates a real defect from a conservative review lead.

### 3.2 Evidence Chain

The explanation must connect:

```text
origin
  -> propagation
  -> branch or state transition
  -> unsafe or incorrect operation
  -> externally visible consequence
```

For example, a nullability warning is not complete until the system can show
where the maybe-null value originates, why guards do not eliminate that path,
where it is dereferenced, and what user-visible behavior follows.

### 3.3 Cause Versus Symptom

The system must prefer the earliest actionable causal point. A thrown exception,
unsafe dereference, or failed assertion may be a symptom of:

- a missing validation boundary;
- an inconsistent return contract;
- an invalid state transition;
- stale configuration;
- a caller violating a callee precondition;
- a callee violating a caller expectation;
- an earlier regression.

Static adjacency alone is not causality. Dependency edges may narrow the search,
but they must not be presented as proof.

### 3.4 Competing Hypotheses and Unknowns

A trustworthy diagnosis must expose ambiguity:

- alternate plausible causes;
- unresolved calls and dynamic behavior;
- missing runtime evidence;
- framework behavior the analyzer cannot observe;
- assumptions that require developer confirmation.

Unknown must remain preferable to a polished but speculative answer.

### 3.5 Cross-Function and Cross-File Context

The current graph and call facts are enough to locate candidate neighbors. A
root-cause explanation additionally needs:

- caller expectations;
- callee return and exception contracts;
- argument and state provenance;
- guard behavior across call boundaries;
- public versus internal usage;
- tests that encode expected behavior.

### 3.6 Regression Context

When Git history exists, a diagnosis should be able to distinguish:

- long-standing risk;
- newly introduced regression;
- code made unsafe by a changed caller;
- code made unsafe by a changed callee;
- behavior already covered by a known fix or rollback point.

This is essential for prioritization. A static risk with no recent behavioral
change is a different engineering problem from a regression in the current
patch.

## 4. Repair Suggestion Requirements

A repair suggestion must be evidence-bound. The product should not jump from a
weak signal to a confident patch.

### 4.1 Minimum Standard

Every suggested repair needs:

- the confirmed or hypothesized root cause it addresses;
- the smallest relevant edit surface;
- the contract or invariant restored;
- the affected callers, tests, and interfaces;
- assumptions that remain unverified;
- risks introduced by the change;
- an explicit confidence level.

### 4.2 Multiple Valid Repairs

The system must recognize that a defect can often be repaired at different
boundaries:

- reject invalid input earlier;
- normalize data at the source;
- restore a callee contract;
- handle an optional result in the caller;
- narrow a public API;
- add a regression test without changing behavior.

It should explain tradeoffs instead of pretending the first syntactically valid
edit is uniquely correct.

### 4.3 Scope Discipline

A credible repair suggestion must avoid:

- broad refactors unrelated to the failing behavior;
- style churn;
- guessed framework semantics;
- silently changing public contracts;
- repairing only the symptom while leaving the cause active;
- presenting an unverified patch as complete.

### 4.4 Safety Boundary

Builder Core's current read-only posture is an asset. Repair intelligence can
remain useful while preserving:

- preview before application;
- developer-controlled edits;
- no autonomous target-repository mutation;
- clear separation between suggestion and verified repair.

## 5. Verification Requirements

Verification is the difference between "plausible patch" and "developer can
trust this conclusion."

### 5.1 Defect Verification

A broken-code claim should be backed by one or more of:

- an existing failing test tied to the behavior;
- a minimal reproduction;
- a violated static invariant with no unresolved alternate path;
- an explicit caller/callee contract mismatch;
- historical evidence showing the regression boundary;
- human confirmation when static evidence remains incomplete.

### 5.2 Repair Verification

A repair suggestion needs a verification packet:

| Verification layer | Required evidence |
| --- | --- |
| Targeted regression | The previously failing or newly added reproduction now passes |
| Related tests | Tests associated with affected modules and callers pass |
| Static re-analysis | The causal finding is absent or intentionally downgraded |
| Build and lint | Relevant repository checks remain clean |
| Negative behavior | The repair does not broaden accepted invalid input or remove required errors |
| Blast-radius review | Affected public interfaces and dependent modules are identified |

### 5.3 Honest Outcomes

Verification must distinguish:

- verified;
- partially verified;
- blocked by missing dependencies;
- blocked by unavailable tests;
- still ambiguous;
- regressed elsewhere.

"Could not verify" is a valid result. It must never be rendered as success.

### 5.4 Test Relationship Intelligence

The dependency graph needs a test-facing view:

- which tests directly import or call the changed code;
- which tests cover affected entry points;
- which affected modules have no obvious test relationship;
- which historical failures or fixtures express the contract;
- which checks are likely relevant without claiming exhaustive coverage.

## 6. Architecture Intelligence Requirements

RU-2 and the dependency graph provide structural understanding. Architecture
intelligence requires additional meaning layered on top of that structure.

| Architecture question | Current answer quality | Missing intelligence |
| --- | --- | --- |
| What are the major subsystems? | Good top-level deterministic answer | Nested subsystem boundaries and ownership |
| Which code depends on this function? | Graph can enumerate resolved static edges | Reverse impact semantics, confidence, public API awareness |
| What breaks if this changes? | Not yet answerable | Affected behavior, tests, interfaces, config, and runtime paths |
| Where does a user request enter the system? | Source retrieval can cite likely entry files | Runtime path model and framework wiring |
| Is this import cycle harmful? | Cycle can be listed | Layer policy, runtime initialization risk, architectural intent |
| Is this module public or internal? | Not established | Export surface and external-consumer model |
| Which configuration controls this behavior? | Not established | Config-to-code dependency relationships |
| Who owns this area? | Not established | Ownership metadata and repository conventions |
| How do mixed-language pieces interact? | Weak | Language-specific parsers plus cross-language interface boundaries |

Impact analysis is the natural first consumer of the dependency graph because
it can answer "what may be affected?" It is necessary but not sufficient. It
must remain carefully worded: a reverse-reachable node is **potentially
affected**, not proven broken.

## 7. Developer Workflow Requirements

The product promise only becomes useful when it fits the developer's normal
investigation loop.

### 7.1 Terminal Workflow

Developers need concise, stable output:

- confirmed defects separated from review leads and advisories;
- direct source locations;
- root-cause chain;
- affected surface;
- verification status;
- deterministic JSON or SARIF export;
- clear exit semantics for CI.

### 7.2 Editor Workflow

The useful unit is not a list of warnings. It is an inspectable issue packet:

- the suspicious line;
- upstream cause;
- downstream consequence;
- callers and tests;
- confidence and unknowns;
- suggested repair boundaries;
- verification evidence.

### 7.3 Pull Request Workflow

For changed code, developers need:

- findings scoped to the diff where possible;
- newly introduced versus pre-existing risk;
- impacted modules and tests;
- baseline suppression for known accepted leads;
- a compact explanation suitable for review discussion.

### 7.4 CI Workflow

CI needs a conservative gate:

- fail only on explicitly eligible confirmed-defect classes;
- report leads without treating them as build failures;
- preserve deterministic output;
- avoid executing untrusted repository code implicitly;
- make incomplete verification visible.

### 7.5 Performance and Trust

Developers need to perceive and verify progress:

- incremental indexing;
- cancellation;
- cache visibility;
- bounded analysis;
- honest degraded-mode reporting;
- no hidden writes;
- no hidden execution;
- reproducible exports.

## 8. Competitive Comparison

This comparison uses public official product documentation available on
2026-05-31. It compares developer-facing capability surfaces, not internal
implementation quality or benchmark accuracy.

| Product | Publicly documented capability surface | Where it is ahead of current Builder Core | Builder Core strength worth preserving |
| --- | --- | --- | --- |
| Claude Code | Anthropic describes an agentic coding tool that can understand a codebase, edit files, run commands, and integrate with development tools. | Interactive investigation, repair, and command-driven validation loop | Deterministic local evidence path and explicit read-only safety mode |
| Cursor | Cursor documents codebase indexing, an Agent that can search and edit code and run terminal commands, and Bugbot pull-request review. | IDE-native repair loop, repository context, PR review surface, quick developer feedback | Conservative finding provenance and unknown-over-guessing discipline |
| GitHub Copilot | GitHub documents Copilot coding agent working from issues to pull requests, running tests and linters in its environment, plus Copilot code review on changed code. | GitHub-native issue, PR, review, and validation workflow | Local deterministic analysis with no implicit target execution |
| Sourcegraph | Sourcegraph documents code search, code navigation, code-graph-powered context, and large-scale change workflows. | Multi-repository navigation, architecture-scale discovery, and large-codebase context | Tight local trust boundary and explainable static review leads |

### 8.1 Claude Code Gap

Claude Code's advantage is the conversational engineering loop: inspect,
modify, execute checks, and iterate. Builder Core has a more conservative
static substrate, but it currently stops before repair and verification
closure. To support the target promise, Builder Core needs issue packets that
remain useful even when no autonomous edit or command execution is allowed.

Official source:
[Claude Code overview](https://docs.anthropic.com/en/docs/claude-code/overview)

### 8.2 Cursor Gap

Cursor's advantage is developer immediacy: repository indexing lives inside the
editor, Agent can use codebase search and terminal actions, and Bugbot puts
review feedback on pull requests. Builder Core's CLI can produce deterministic
findings, but its current developer experience does not yet compress the path
from finding to investigation to validated resolution.

Official sources:
[Cursor features](https://cursor.com/en-US/features),
[Cursor codebase indexing](https://docs.cursor.com/chat/codebase),
[Cursor Bugbot](https://docs.cursor.com/bugbot)

### 8.3 GitHub Copilot Gap

GitHub Copilot's advantage is workflow placement: code review works on changed
code, while the coding agent can take an issue, create a pull request, and run
automated checks. Builder Core has a stronger explicit read-only stance for
untrusted analysis, but it lacks comparable change-aware review and
verification packaging.

Official sources:
[About GitHub Copilot coding agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-copilot-coding-agent),
[Using GitHub Copilot code review](https://docs.github.com/en/copilot/using-github-copilot/code-review/using-copilot-code-review)

### 8.4 Sourcegraph Gap

Sourcegraph's advantage is scale: search, navigation, context, and code-graph
relationships help developers move across large repositories and repository
sets. Builder Core's dependency graph is a promising local foundation, but it
does not yet provide multi-repository architecture intelligence, semantic
impact explanations, or large-scale change confidence.

Official sources:
[Sourcegraph code search](https://sourcegraph.com/docs/code-search),
[Sourcegraph precise code navigation](https://sourcegraph.com/docs/code-navigation/precise_code_navigation),
[Sourcegraph Cody context](https://sourcegraph.com/docs/cody/core-concepts/context)

### 8.5 Competitive Position

Builder Core should not imitate the broadest agent surface and lose its trust
model. Its credible differentiator is:

> deterministic, local, evidence-backed repository intelligence that knows the
> difference between a lead, a diagnosis, and a verified repair.

The gap is that only the first of those three is meaningfully present today.

## 9. Ranked Highest-Leverage Capability Gaps

This is a ranking of capabilities, not an implementation roadmap.

| Rank | Capability gap | Why it has high leverage | What becomes possible |
| ---: | --- | --- | --- |
| 1 | **Defect confirmation and output taxonomy** | The pilot's central issue is that useful leads and confirmed defects are not the same product claim. | JARVIS can say "broken" only when evidence passes a defined confirmation bar, while preserving honest review leads. |
| 2 | **Impact analysis over the dependency graph** | A developer needs the affected surface before changing code. The graph substrate now exists. | Potentially affected callers, modules, tests, interfaces, and unresolved relationships can be stated with confidence boundaries. |
| 3 | **Root-cause evidence chains** | Current findings often stop at a sink or suspicious line. | JARVIS can explain origin, propagation, violated contract, symptom, and unknowns. |
| 4 | **Test and reproduction binding** | Defect claims become substantially stronger when connected to executable or inspectable expected behavior. | JARVIS can distinguish a static suspicion from a reproducible failure and point to the smallest validating example. |
| 5 | **Bounded repair suggestions** | Developers ultimately need a correction, not only a warning. | JARVIS can describe the smallest contract-restoring repair and alternate repair boundaries without auto-applying code. |
| 6 | **Verification closure** | A patch without evidence remains a hypothesis. | JARVIS can report whether targeted tests, related checks, static re-analysis, and blast-radius review support the repair. |
| 7 | **Change-aware regression intelligence** | Real developer work is usually diff-centered. Git history is indexed but not yet central to diagnosis. | JARVIS can separate introduced risk from pre-existing debt and identify likely regression boundaries. |
| 8 | **Semantic architecture overlays** | Structural nodes and edges do not explain responsibilities or contracts. | JARVIS can reason about entry points, public surfaces, boundaries, configuration, and ownership without overstating runtime certainty. |
| 9 | **Developer workflow integration** | A technically correct finding that arrives outside the engineer's review loop has limited value. | JARVIS can deliver consistent terminal, editor, PR, and CI issue packets with lead-versus-defect separation. |
| 10 | **Production evidence and coverage breadth** | Python-only static intelligence plus two pilot repositories is too narrow for broad claims. | JARVIS can state where its conclusions are validated, where language/framework support ends, and how much trust a developer should place in each result. |

## 10. The Product Threshold

Builder Core reaches:

> JARVIS tells developers what is broken.

only when a developer can ask about a repository or change and receive an
answer shaped like this:

```text
Confirmed defect:
  behavior X fails under condition Y.

Root cause:
  value/state Z originates here, propagates through these resolved calls,
  and violates contract C here.

Impact:
  these callers, interfaces, and tests are potentially affected;
  these dynamic relationships remain unresolved.

Repair:
  this bounded change restores contract C.

Verification:
  this reproduction now passes, related checks pass, static evidence is gone,
  and remaining uncertainty is listed explicitly.
```

Until that loop is available and validated on real repositories, the honest
product statement remains:

> JARVIS tells developers where to look, why it may matter, and what evidence
> still needs confirmation.

## Local Evidence Used

- `reports/ru2_repository_understanding_v1.md`
- `reports/phase94a_dependency_graph_implementation.md`
- `reports/phase95e_pilot_human_review_results.md`
- `reports/phase95f_post_review_calibration_plan.md`
- `reports/phase95g_product_positioning.md`
- `builder_core/README.md`
- `builder_core/bug_intelligence/engine.py`
- `builder_core/bug_intelligence/depgraph.py`

