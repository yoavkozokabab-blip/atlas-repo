# Phase 90 Codex Verification Audit

Date: 2026-05-30

## Verdict

**NOT SAFE TO COMMIT as a completed "unified Builder Core" Phase 90.**

The new engine is a safe, read-only orchestration layer and the requested tests
and smokes pass. However, unification is incomplete:

1. `benchmark-quixbugs` still bypasses the unified engine.
2. The unified fact model is extracted, but the detector stages do not consume
   it as their authoritative input. Logic, security, and semantic stages rerun
   legacy analysis independently.
3. The unified engine emits one primary output schema, but multiple active
   legacy finding schemas remain behind adapters.

This is a partial migration with good safety properties, not yet a single
analysis engine.

## Requested Questions

### 1. Does CLI `analyze-file` use the unified engine?

**Yes.** `builder_core/cli.py:_cmd_analyze_file` calls
`bi_engine.analyze_file`, which routes into
`builder_core/bug_intelligence/engine.py:analyze_source`.

### 2. Does CLI `security-scan` use the unified engine?

**Yes.** `builder_core/cli.py:_cmd_security_scan` calls
`bi_engine.security_findings`. That calls unified-engine repository analysis
with `include_algorithm=False` and filters unified findings by category.

### 3. Does CLI `bug-scan` use the unified engine?

**Yes.** `builder_core/cli.py:_cmd_bug_scan` calls
`bi_engine.analyze_repository` and `bi_engine.rank_files`.

### 4. Does `benchmark-quixbugs` use the unified engine?

**No.** `builder_core/cli.py:_cmd_benchmark_quixbugs` calls
`builder_core/benchmark.py:evaluate_quixbugs`, which calls
`builder_core/python_analysis.py:analyze_python`, then
`builder_core/semantic_reasoning.py:analyze_semantics`.

The holdout benchmark also remains on this old path through
`builder_core/external_benchmark.py`.

### 5. Are there now two finding schemas or one primary schema?

There is **one primary unified engine output schema**:
`builder_core/bug_intelligence/finding.py:Finding`.

There are still multiple active internal legacy shapes:

- `builder_core/bug_intelligence/findings.py:Finding` for pattern detectors.
- `builder_core/bug_intelligence/security.py:Finding89` for security findings.
- Dictionary findings returned by `builder_core/semantic_reasoning.py`.

`builder_core/bug_intelligence/finding.py` converts these shapes through
`from_pattern_finding`, `from_security_finding`, and `from_semantic_finding`.

### 6. Which old modules remain active?

- `builder_core/semantic_reasoning.py`: active in both the unified
  `AlgorithmAgent` and the old benchmark path.
- `builder_core/python_analysis.py`: active in QuixBugs benchmark, holdout
  benchmark, indexing, `ask`, and `risk-report`.
- `builder_core/benchmark.py`: active for CLI `benchmark-quixbugs`.
- `builder_core/bug_intelligence/patterns.py`: active inside unified
  `LogicBugAgent`.
- `builder_core/bug_intelligence/findings.py`: active schema used by patterns.
- `builder_core/bug_intelligence/security.py`: active inside unified
  `SecurityAgent`.
- `builder_core/bug_intelligence/valueflow.py`: active in fact extraction and
  security analysis.
- `builder_core/bug_intelligence/dataflow.py`: active in fact extraction,
  pattern analysis, and semantic reasoning.

### 7. Which old modules are compatibility-only?

- `builder_core/bug_intelligence/analyzer.py`: no longer the CLI bug-scan path;
  retained as a legacy API and as the walker used by the legacy
  `security.scan_repository` helper.
- `builder_core/bug_intelligence/ranking.py`: no longer the CLI bug-scan
  ranking path; retained as a legacy API.
- `DataFlowAgent` and `ValueFlowAgent` in
  `builder_core/bug_intelligence/agents.py`: thin wrappers that are currently
  unused by the unified engine.
- CLI imports `bug_analyzer`, `bug_ranking`, and `bug_security` are stale and
  unused.

### 8. Are detectors still bypassing the fact model?

**Yes. This is the main architectural blocker.**

`engine.analyze_source` extracts `module_facts`, but calls detector stages
without passing those facts:

- `LogicBugAgent.run` calls `patterns.run_all`, which re-walks AST and reruns
  `dataflow.analyze_source` for one rule.
- `SecurityAgent.run` calls `security.analyze_source`, which reruns
  `valueflow.analyze_source`.
- `AlgorithmAgent.run` calls `semantic_reasoning.analyze_semantics`, which
  re-walks AST and reruns `dataflow.analyze_source` for frontier analysis.

The fact model is currently returned as metadata, not used as the canonical
detector input.

### 9. Did any unsafe execution path get added?

**No.** The new engine and detector layers perform local static AST/text
analysis. They do not execute analyzed code, call network services, or invoke
tools against a target repository.

`valueflow.py` has a method named `eval`, but it is an internal abstract AST
evaluator, not Python `eval`.

The pre-existing `gitutil.py` invokes fixed read-only `git` inspection
commands. Explicit legacy `init` and `remember` commands write only under
`<project>/.jarvis_builder/`.

### 10. Are target repos modified?

**Not by `analyze-file`, `bug-scan`, `security-scan`, benchmarks, or the Phase
89 smoke.**

Evidence:

- `builder_core/tests/test_phase90_unified_engine.py` snapshots a temporary
  target repository before and after all three unified CLI commands.
- A live QuixBugs before/after check showed identical status and identical
  hashes for all Python files under `python_programs/` and
  `correct_python_programs/`.
- QuixBugs had an existing untracked `.jarvis_builder/index.json` before the
  audit benchmark and the same untracked file afterward.

Explicit legacy `init` and `remember` commands intentionally write only below
`.jarvis_builder/`.

## Must-Fix Before Completed Phase 90 Commit

1. Route `benchmark-quixbugs` and the holdout benchmark through the unified
   engine, or explicitly narrow Phase 90's completion claim and defer benchmark
   migration.
2. Pass the extracted unified fact model into detector stages and make it the
   canonical input where facts are available. Avoid rerunning independent
   `dataflow` and `valueflow` analysis inside detector adapters.
3. Decide whether legacy finding schemas are temporary compatibility adapters
   or still supported APIs. Document and test that boundary.
4. Add a regression test proving the benchmark uses the intended engine path.
5. Add tests proving fact-backed detector stages consume the extracted fact
   model rather than recomputing it independently.

## Requested Verification Results

### Builder Core tests

Command:

```text
py -3 -m pytest builder_core/tests/ -q
```

Result:

```text
91 passed in 3.70s
```

Focused Phase 90 confirmation:

```text
py -3 -m pytest builder_core/tests/test_phase90_unified_engine.py -q -p no:cacheprovider
13 passed in 0.53s
```

### QuixBugs benchmark

Command:

```text
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

Result:

```text
buggy files analyzed: 40
correct files analyzed: 40
excluded support pairs: 10
true positives: 12
false positives: 0
precision: 1.0000
recall: 0.3000
true positive rate: 0.3000
false positive rate: 0.0000
```

### External holdout benchmark

Command:

```text
py -3 scripts/run_phase84_holdout_benchmark.py
```

Result:

```text
cases analyzed: 12
true positives: 2
false positives: 0
false negatives: 10
true negatives: 12
precision: 1.0000
recall: 0.1667
accuracy: 0.5833
```

### Phase 89 value/data-flow smoke

Command:

```text
py -3 builder_core/scripts/smoke_phase89_value_dataflow_taint.py
```

Result after rerun outside the Windows sandbox temp ACL boundary:

```text
SMOKE PASSED
vulnerable.py: security categories detected
safe.py: 0 findings
```

The initial sandboxed run failed while creating its temporary directory with
`PermissionError: [WinError 5] Access is denied`; the outside-sandbox rerun
passed.

## Git Scope

Tracked `git diff --name-only` for the Phase 90 audit scope is empty because
the Builder Core files are currently untracked.

Scoped untracked files inspected:

```text
builder_core/bug_intelligence/agents.py
builder_core/bug_intelligence/dataflow.py
builder_core/bug_intelligence/engine.py
builder_core/bug_intelligence/facts.py
builder_core/bug_intelligence/finding.py
builder_core/bug_intelligence/security.py
builder_core/bug_intelligence/valueflow.py
builder_core/cli.py
builder_core/python_analysis.py
builder_core/semantic_reasoning.py
builder_core/tests/test_phase90_unified_engine.py
reports/phase90_codex_verification.md
```

Because the entire Builder Core tree is untracked, Git alone cannot prove
which of these files were introduced or modified specifically by Phase 90.
Use explicit file staging when the architectural blockers are resolved.
