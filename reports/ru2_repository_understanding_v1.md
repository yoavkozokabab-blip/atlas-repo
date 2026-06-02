# RU-2 - Repository Understanding V1

**Status:** Implemented and verified.
**Date:** 2026-05-31
**Priority:** Repository understanding before bug detection.

## 1. Scope

RU-2 adds deterministic repository structure to the standalone Builder Core
index and ask path. It does not change detectors, finding schemas, benchmarks,
promotion rules, target repository source files, or target code execution.

The implementation uses path roles and static Python imports only. It does not
add LLM reasoning, semantic inference, or speculative dependency edges.

## 2. File Role Index

Every indexed file now stores one role:

| Role | Purpose |
| --- | --- |
| `production_code` | Ordinary source files outside test, benchmark, and generated paths |
| `test` | Test modules and test directories |
| `benchmark` | Holdout, BugsInPy, QuixBugs, and benchmark paths |
| `dataset` | Indexed data artifacts |
| `generated` | Generated, cache, backup, and temporary paths |
| `report_history` | Historical reports |
| `architecture_doc` | Architecture, design, and overview documents |
| `general_doc` | README and ordinary documentation |
| `config` | Common configuration files |
| `unknown` | Indexed files without a stronger deterministic role |

The prior `readme`, `docs`, `src`, and `test` categories remain alongside roles
for compatibility with existing risk consumers.

## 3. Architecture Retrieval Routing

Architecture questions prefer:

```text
README_ARCHITECTURE.md
README.md
main.py
core/**
voice/**
browser/**
autonomy/**
memory/**
conversation/**
project_intelligence/**
builder_core/**
```

Architecture retrieval applies these caps:

| Source type | Cap |
| --- | ---: |
| Reports | At most 20% |
| Benchmarks and datasets | 0% |
| Production code plus architecture docs | At least 50% when available |

Risk questions and file-specific bug analysis retain their existing paths.

## 4. Deterministic Subsystem Map

`index.json` schema version `2` stores a `subsystems` list. Every top-level
subsystem record contains:

```text
name
role
file_count
entry_files
dependencies
role_counts
```

Dependencies come only from module-level Python imports whose first path
segment matches another indexed top-level subsystem. Unknown and dynamic
relationships are omitted rather than guessed.

Generated scratch trees such as `tests_tmp/`, `.pytest_tmp/`, and `backups/`
are pruned from indexing so stale runtime artifacts do not become production
subsystems.

## 5. Ask Quality Metrics

Every Builder Core `ask` result now includes:

```text
total_sources
source_distribution
production_percent
architecture_percent
reports_percent
benchmark_percent
```

The CLI prints the same fields under `ASK QUALITY`.

## 6. Real `local_jarvis` Measurement

The measurement built an in-memory index only. It did not write a new
`.jarvis_builder/index.json`.

### Indexed Roles

| Metric | Count |
| --- | ---: |
| Indexed files | 4,060 |
| Indexed chunks | 6,000 |
| Production code | 665 |
| Tests | 152 |
| Benchmarks | 1,873 |
| Report history | 1,361 |
| Architecture docs | 1 |
| General docs | 3 |
| Config | 5 |

### Largest Production Subsystems

| Subsystem | Production files | Example entry files | Static dependencies |
| --- | ---: | --- | --- |
| `voice` | 133 | `voice/voice_loop.py`, `voice/wakeword.py` | `core`, `vision` |
| `actions` | 65 | `actions/__init__.py`, `actions/app_actions.py` | Multiple runtime subsystems |
| `scripts` | 62 | `scripts/create_shortcut.ps1`, `scripts/gen_phase80_samples.py` | Multiple runtime subsystems |
| `builder_core` | 47 | `builder_core/cli.py`, `builder_core/bug_intelligence/engine.py` | None detected |
| `assistant` | 27 | `assistant/__init__.py`, `assistant/continuity_engine.py` | `core`, `diagnostics`, `operating`, `runtime`, `services` |
| `conversation` | 22 | `conversation/semantic_stream/engine.py`, `conversation/__init__.py` | `assistant`, `core`, `vision`, `voice` |
| `investigation` | 21 | `investigation/__init__.py`, `investigation/causality_trace.py` | `core` |
| `brain` | 20 | `brain/router.py`, `brain/__init__.py` | `actions`, `core`, `integrations`, `tools`, `tooluse` |
| `core` | 20 | `core/app.py`, `core/__init__.py` | `brain`, `voice` |

### Required Ask Regression Questions

| Question | Production | Architecture | Reports | Benchmarks |
| --- | ---: | ---: | ---: | ---: |
| What are the most important subsystems? | 100.00% | 0.00% | 0.00% | 0.00% |
| What happens when a user speaks a voice command? | 83.33% | 16.67% | 0.00% | 0.00% |
| Which folders contain production code? | 100.00% | 0.00% | 0.00% | 0.00% |
| List the top directories and explain them. | 100.00% | 0.00% | 0.00% | 0.00% |

The voice question cites:

```text
voice/voice_loop.py
voice/wakeword.py
voice/__init__.py
voice/engines/__init__.py
voice/providers/__init__.py
README_ARCHITECTURE.md
```

It does not cite BugsInPy, pandas, thefuck, QuixBugs, or holdout sources.

## 7. Verification

```text
py -3 -m pytest builder_core\tests\test_builder_core.py builder_core\tests\test_ru2_repository_understanding.py tests\test_phase82_builder_core_cli.py -q -p no:cacheprovider
27 passed

py -3 -m pytest builder_core\tests\ tests\test_phase82_builder_core_cli.py -q -p no:cacheprovider
233 passed in 11.30s

py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
12 true positives, 0 false positives, precision 1.0000, recall 0.3000

py -3 scripts\run_phase84_holdout_benchmark.py
2 true positives, 0 false positives, precision 1.0000, recall 0.1667

py -3 -m builder_core.scripts.smoke_builder_core
SMOKE PASSED
```

The first smoke attempt failed because the sandbox denied access to its Windows
temporary directory. The identical smoke passed when rerun outside the sandbox.

## 8. RU-2 Files

Added:

```text
builder_core/repository_understanding.py
builder_core/tests/test_ru2_repository_understanding.py
reports/ru2_repository_understanding_v1.md
```

Modified for RU-2:

```text
builder_core/indexer.py
builder_core/retrieval.py
builder_core/ask.py
builder_core/cli.py
builder_core/README.md
```

## 9. Dirty-Tree Isolation

The worktree already contains unrelated Phase 94 dependency-graph and Phase 95D
review-tooling work. In particular, concurrent Phase 94 CLI graph commands are
present in `builder_core/cli.py`. RU-2 did not create, remove, or redesign that
work. RU-2's CLI edits are limited to the index subsystem count and `ASK QUALITY`
rendering.

## 10. Safety Confirmation

- No detector changed.
- No benchmark changed.
- No promotion rule changed.
- No finding schema changed.
- No target code was executed.
- No target source file was modified by indexing.
- Benchmark content is not eligible for architecture answers.
- Dynamic or ambiguous dependencies are omitted rather than inferred.
