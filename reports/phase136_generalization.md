# Phase 136 — Atlas Multi-Repository Generalization Report

Generated across 6 target repositories (6 scored, 0 not checked out locally).

## Mean scores (scored repositories)

| Understanding | Impact | Investigation | Build | Overall |
|---:|---:|---:|---:|---:|
| 93.0 | 49.7 | 100.0 | 96.9 | 82.5 |

## Failure categories (all repositories)

| Category | Count |
|---|---:|
| semantic_routing_failure | 23 |
| build_plan_failure | 3 |
| graph_failure | 1 |
| architecture_failure | 1 |

## Per-repository overall

| Repository | Overall | Modules | Status |
|---|---:|---:|---|
| Home Assistant | 96.2 | 9709 | ok |
| Django | 89.5 | 929 | ok |
| VS Code | 88.6 | 7551 | ok |
| Atlas (local_jarvis) | 84.5 | 10680 | ok |
| FastAPI | 75.2 | 73 | ok |
| QuixBugs | 61.2 | 4 | ok |

## Honest findings

- Scores measure OUTPUT ROBUSTNESS (grounded, non-fallback, non-noisy output), not
  gold-standard correctness — there is no answer key for arbitrary external repos.
- Impact resolution depends on the curated concept map; generic concepts (auth, caching,
  configuration) that a repo does not expose register as honest fallbacks, not crashes.
- TypeScript/JS and non-Python repos exercise the JS depgraph + import resolution; gaps
  there surface as graph_failure / resolver_failure rows.
- The framework is reproducible: `py -3 benchmarks/generalization/runner.py` re-runs every
  available repo; checking out the remaining targets (set `ATLAS_BENCH_<ID>` or place them
  under a search root) extends coverage to the full 11 with no code changes.
