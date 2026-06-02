# Phase 93 Design - Interprocedural Analysis Foundation

Date: 2026-05-31

Status: design only. No implementation in this phase document.

Scope: the smallest safe call-graph and cross-function fact foundation for
Builder Core. This design adds no detector promotion, no new benchmark verdict
signal, no LLM reasoning, and no legacy-path changes.

Baseline:

- Phase 92A commit: `784bf4a0`
- Phase 92B commit: `b1056d00`
- QuixBugs unified: `12 TP / 0 FP`
- Holdout unified: `2 TP / 0 FP`
- Builder Core tests: `122 passing`
- `inconsistent_return`: fact-backed but quarantined as `kind=pattern`

## 1. Current Limitation After Phase 92B

Builder Core now has a unified per-function fact model, but analysis still stops
at the function boundary.

`facts.extract_module_facts()` merges data-flow and value-flow facts per
function. `dataflow.py` already records raw calls as:

```python
{"func": "<callee text>", "line": <line>}
```

Those call facts are unresolved strings. They do not identify a definition,
record a caller, map arguments to parameters, or describe how the caller uses a
return value. `engine.analyze_repository()` also analyzes files independently:
it does not build a repository symbol table or run a second pass over aggregated
facts.

The practical result is a blind spot:

- a callee may intentionally return a sentinel, but the analyzer cannot observe
  whether callers check it;
- a callee may return a maybe-`None` value, but the analyzer cannot observe
  whether a caller guards it;
- a wrapper may pass a value to another function, but the analyzer cannot link
  the two functions;
- unresolved and dynamic calls are indistinguishable from resolvable local
  calls.

Phase 93 should build the factual substrate only. It should not claim that any
cross-function observation is already a bug.

## 2. Why `inconsistent_return` Cannot Be Safely Promoted Yet

The Phase 92B detector fires when:

```text
has_value_return
and not has_none_return
and can_fall_through
```

That shape is useful, but it is not a contract. Correct
`next_permutation.py` intentionally returns a value when a next permutation
exists and falls through to implicit `None` otherwise. The raw shape is
therefore present in both a genuine forgotten-return case and a valid
value-or-`None` API.

Safe promotion requires usage evidence, not a guess about intent. The useful
observations are:

- whether direct callers compare the result with `None`;
- whether callers branch on the result;
- whether callers return the result unchanged;
- whether callers ignore the result;
- whether callers dereference or otherwise consume the result without a guard;
- whether tests document a sentinel outcome.

Even these are evidence, not proof. A caller that checks `None` suggests an
accepted sentinel contract; it does not prove that every fall-through is
intentional. A caller that does not check `None` may still rely on an external
invariant. Phase 93 must record observed use and preserve uncertainty.

`inconsistent_return` remains quarantined as `kind=pattern` throughout Phase 93.

## 3. Minimal Call Graph Design

### First increment: intra-file, observational, opt-in

Add one isolated module:

```text
builder_core/bug_intelligence/callgraph.py
```

It should parse Python source and build a `CallGraphIndex` for one module at a
time. It must not emit findings. It must not change the default behavior of
`analyze_source()`, `analyze_file()`, benchmarks, or legacy analyzers.

The smallest safe resolver supports only:

1. top-level `def` and `async def` definitions;
2. direct `ast.Name` calls such as `helper(x)`;
3. a unique same-file target;
4. direct self-recursion when the unique target is the current function.

Everything else is recorded as unresolved:

- `obj.method()`
- `self.method()`
- `Class.method()`
- imported calls
- aliased calls
- nested functions
- lambdas
- `getattr(...)`
- function variables such as `fn(...)`
- decorators, descriptors, and monkeypatchable dispatch

This intentionally leaves recall on the table. An absent edge is safer than an
invented edge.

### Data model

```text
CallGraphIndex
  modules: list[ModuleGraph]
  functions: dict[function_id, FunctionNode]
  resolved_edges: list[CallEdge]
  unresolved_calls: list[UnresolvedCall]

FunctionNode
  function_id
  module_path
  qualname
  line
  params
  return_summary

CallEdge
  caller_id
  callee_id
  module_path
  line
  resolution = "same_file_unique_name"
  confidence = "exact"
  result_use
  argument_bindings

UnresolvedCall
  caller_id
  module_path
  line
  callee_text
  reason
```

`result_use` is an observation classified from AST parent context:

```text
ignored
assigned
returned
checked_is_none
checked_truthiness
used_as_value
passed_to_call
unknown
```

No classification should be converted into a finding in Phase 93.

### Second pass boundary

The eventual repository pipeline is:

```text
Pass 1: existing per-file analysis, unchanged
Pass 2: build observational call graph from repository Python source
Pass 3: attach read-only cross-function summaries to a separate graph index
```

Do not merge interprocedural facts into benchmark verdicts in this phase.

## 4. Function Identity Model

Use a deterministic identity:

```text
<normalized-relative-module-path>::<qualname>@<definition-line>
```

Example:

```text
pkg/search.py::find_item@12
```

Rules:

- normalize path separators to `/`;
- preserve case in stored display values;
- use the lexical qualified name for future compatibility;
- include the definition line to distinguish repeated or shadowed names;
- resolve an edge only when the target is unique in the supported scope;
- never resolve by function name alone across files.

The first increment resolves only top-level same-file functions, so `qualname`
is initially the top-level function name. The identity format already leaves
room for future `Class.method` and nested-function support without changing
stored IDs.

## 5. Intra-File First, Cross-File Later

### Phase 93 foundation

Support same-file direct calls only:

```python
def helper(x):
    return x

def caller(x):
    return helper(x)
```

This is enough to validate:

- symbol collection;
- exact edge resolution;
- caller/callee indexing;
- bounded summary propagation;
- caller result-use observations;
- recursion handling;
- unresolved-call honesty.

### Deferred cross-file layer

Cross-file resolution should be a separate follow-up after the intra-file graph
is stable. It requires an import model:

- `import module`
- `from module import name`
- `from module import name as alias`
- package-relative imports
- module path normalization

Re-exports, wildcard imports, namespace packages, class dispatch, and runtime
mutation should remain unresolved until separately designed and tested.

## 6. Facts That Should Flow Across Calls

Phase 93 should propagate only monotonic, observational facts across exact
edges.

### Approved first-increment summaries

From callee to call site:

```text
return_summary.has_value_return
return_summary.has_none_return
return_summary.can_fall_through
callee_may_return_none
callee_may_return_value
```

From call site to callee usage summary:

```text
caller_count
call_site_count
result_use counts by classification
observed_none_check_count
observed_truthiness_check_count
ignored_result_count
unresolved_call_count
```

Argument metadata on exact edges:

```text
positional binding where arity is unambiguous
keyword binding where keyword name exactly matches a parameter
unbound / ambiguous markers for everything else
```

### Deliberately deferred facts

Do not propagate these in the first increment:

- taint across parameters or returns;
- nullability state through assignments after a call;
- exceptions;
- mutation side effects;
- container aliases;
- interval arithmetic;
- sanitization guarantees;
- call-path causality;
- inferred API intent.

Those require separate summaries and precision gates. Phase 93 should create a
place to add them later, not implement them speculatively.

## 7. What Must NOT Be Inferred

The graph must not infer:

- that an unresolved call targets a similarly named function;
- that `obj.method()` is a local method;
- that two same-named functions in different modules are related;
- that a fall-through `None` is a bug;
- that a `None` check proves the callee contract;
- that absence of a `None` check proves a caller bug;
- that caller behavior makes a callee bug causally responsible;
- that an imported name refers to a specific file before import resolution
  exists;
- runtime dispatch, monkeypatching, reflection, decorator behavior, or
  inheritance;
- security taint propagation across calls;
- cross-file links in the intra-file milestone.

Every unsupported case must remain visible in `unresolved_calls` with a reason.

## 8. Precision-First Gates

### Graph-edge gate

Create a resolved edge only when all are true:

1. the call is a direct `ast.Name` call;
2. caller and candidate callee are in the same file;
3. the candidate is a supported top-level function;
4. exactly one candidate matches;
5. lexical scope does not introduce ambiguity.

Otherwise emit an unresolved-call fact.

### Propagation gate

- propagate only across `confidence="exact"` edges;
- use monotonic unions and counters only;
- cap fixpoint passes for recursive cycles;
- if the cap is reached, mark the summary incomplete rather than guessing;
- impose file/function/edge caps and report truncation explicitly;
- never hide unresolved or truncated state.

### Verdict gate

Phase 93 adds no finding kind and no detector promotion:

- `INCONSISTENT_RETURN_KIND` remains `"pattern"`;
- `BENCHMARK_VERDICT_KINDS` remains unchanged;
- QuixBugs and holdout verdicts must remain `12/0` and `2/0`;
- single-file analysis behavior must remain unchanged;
- legacy benchmark and analyzer paths remain untouched.

Any future interprocedural detector must start quarantined and pass the same
zero-false-positive gate used in Phase 92B before promotion is discussed.

## 9. Tests Needed

Add a focused test module:

```text
builder_core/tests/test_phase93_interprocedural_foundation.py
```

Required tests:

1. unique same-file direct call resolves to one exact edge;
2. direct self-recursion resolves without infinite propagation;
3. two same-named definitions are treated as ambiguous and remain unresolved;
4. `obj.method()` remains unresolved;
5. imported call remains unresolved in the intra-file milestone;
6. nested-function call remains unresolved until lexical resolution is
   deliberately supported;
7. `getattr(...)` and function-variable calls remain unresolved;
8. result-use classification records assigned, returned, ignored,
   `is None`, and truthiness-check cases;
9. exact positional and keyword argument bindings are recorded;
10. ambiguous `*args` / `**kwargs` bindings remain marked ambiguous;
11. callee return summary flows to exact call sites as `may` facts only;
12. recursive cycles terminate under the propagation cap;
13. graph extraction modifies no target source file;
14. default `engine.analyze_source()` output remains unchanged;
15. QuixBugs unified remains `12 TP / 0 FP`;
16. holdout unified remains `2 TP / 0 FP`;
17. `inconsistent_return` remains quarantined as `kind=pattern`;
18. all existing Builder Core tests remain green.

## 10. Exact Files Likely To Change

### First implementation commit: preferred minimal scope

Add:

```text
builder_core/bug_intelligence/callgraph.py
builder_core/tests/test_phase93_interprocedural_foundation.py
reports/phase93_interprocedural_foundation.md
```

The new module should be testable directly and remain observational.

### Optional second implementation commit: repository exposure

Modify only if repository-level exposure is needed after the direct tests pass:

```text
builder_core/bug_intelligence/engine.py
builder_core/bug_intelligence/agents.py
```

Permitted change:

- add an explicit opt-in repository graph API or thin `CallGraphAgent`;
- attach graph metadata without adding findings or changing default verdicts.

Do not change in Phase 93:

```text
builder_core/bug_intelligence/valueflow.py
builder_core/bug_intelligence/dataflow.py
builder_core/bug_intelligence/fact_detectors.py
builder_core/bug_intelligence/finding.py
builder_core/bug_intelligence/engine_benchmark.py
builder_core/bug_intelligence/patterns.py
builder_core/bug_intelligence/security.py
builder_core/semantic_reasoning.py
builder_core/benchmark.py
```

This keeps stable intraprocedural and legacy paths untouched.

## 11. Acceptance Criteria

Phase 93 foundation is complete only when:

1. a same-file direct-call graph exists as an additive, read-only component;
2. every resolved edge is exact and every unsupported call is recorded as
   unresolved;
3. function IDs are deterministic and include module path, qualified name, and
   definition line;
4. caller usage observations and callee return summaries are available without
   emitting new findings;
5. recursive graphs terminate within bounded propagation;
6. no analyzed target repository file is created, modified, or deleted;
7. no LLM, network, subprocess execution of analyzed code, or autonomous action
   is introduced;
8. `inconsistent_return` remains quarantined;
9. `BENCHMARK_VERDICT_KINDS` remains unchanged;
10. QuixBugs unified remains exactly `12 TP / 0 FP`;
11. holdout unified remains exactly `2 TP / 0 FP`;
12. all existing Builder Core tests pass plus the new Phase 93 tests;
13. legacy analyzer and legacy benchmark paths are untouched.

Phase 93 does not need to improve recall. It needs to make the next precision
improvement possible without weakening the current discipline.

## 12. Rollback Plan

The rollback should be mechanical:

### If only the first implementation commit lands

Remove:

```text
builder_core/bug_intelligence/callgraph.py
builder_core/tests/test_phase93_interprocedural_foundation.py
reports/phase93_interprocedural_foundation.md
```

No existing runtime path changes, so rollback restores the exact Phase 92B
behavior.

### If optional repository exposure lands

Also revert only the additive graph hook in:

```text
builder_core/bug_intelligence/engine.py
builder_core/bug_intelligence/agents.py
```

Rollback triggers:

- any QuixBugs or holdout false positive;
- any change to single-file findings;
- any unresolved call incorrectly presented as resolved;
- any non-termination or unbounded propagation;
- any target-repository write;
- any pressure to promote `inconsistent_return` without a separate measured
  gate.

The safe fallback is Phase 92B: keep `inconsistent_return` visible but
quarantined, retain `12 TP / 0 FP` QuixBugs and `2 TP / 0 FP` holdout, and defer
interprocedural reasoning until the graph can be trusted.
