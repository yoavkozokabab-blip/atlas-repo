# Builder Core CLI

Builder Core is a standalone, local-only repository analysis CLI. It does not
route through `main.py`, execute target code, modify source files, download
repositories, or auto-fix findings. Its only target-repository writes are index
files under `<project>/.jarvis_builder/`.

## Commands

```powershell
py -3 -m builder_core.cli init --project C:\Repos\QuixBugs
py -3 -m builder_core.cli ask --project C:\Repos\QuixBugs "Analyze python_programs/breadth_first_search.py for likely bugs and logic errors."
py -3 -m builder_core.cli risk-report --project C:\Repos\QuixBugs --top 10
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

`init` indexes README files, docs, source files, test files, Python AST signals,
and Git history when available. `ask` returns `ANSWER`, `FINDINGS`, `EVIDENCE`,
and `SOURCES`. `risk-report` ranks suspicious Python files using deterministic
static-analysis signals.

## Repository Understanding

The index stores a deterministic role for every indexed file:
`production_code`, `test`, `benchmark`, `dataset`, `generated`,
`report_history`, `architecture_doc`, `general_doc`, `config`, or `unknown`.
It also stores a top-level subsystem map with role counts, entry files, and
static Python import dependencies.

Architecture questions route to production code and architecture documents
before historical reports. Benchmark and dataset sources are excluded from
architecture answers. The CLI prints an `ASK QUALITY` section with production,
architecture, report-history, and benchmark source percentages.

## Semantic Bug Reasoning

Builder Core applies named algorithm profiles after its general AST scan. The
profiles cover BFS, DFS, shortest path, sorting, recursion, graph traversal,
tree traversal, and dynamic programming. Profile checks compare observed
behavior to algorithm invariants, such as FIFO queue use and queue-exhaustion
termination for BFS.

Indexed tests are used as read-only evidence. For example, a negative BFS
assertion establishes that an unreachable graph must return `False`; an
unconditional `while True` loop that dequeues with `popleft()` violates that
expectation when its frontier empties.

`benchmark-quixbugs` compares local `python_programs/` buggy files with their
`correct_python_programs/` counterparts. It reports true positives, false
positives, precision, recall, true-positive rate, and false-positive rate. It
never downloads QuixBugs automatically.

## QuixBugs Smoke

```powershell
py -3 scripts\smoke_phase82_builder_core.py
py -3 scripts\smoke_phase83b_semantic_reasoning.py
```

The smoke uses an existing local QuixBugs checkout. If none is present, it
prints the setup command and exits without downloading anything.
