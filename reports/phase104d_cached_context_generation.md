# Phase 104D — Cached Context Generation for Speed

**Status:** Implemented  
**Cache version:** `phase104d-v1`

## Goal

Speed up benchmark JARVIS context generation by caching expensive read-only stages, without changing analysis results, scoring, or ask/ranking behavior.

## Cached stages

| Stage | Artifact |
|---|---|
| `repository_understanding` | Production subsystem list |
| `dependency_graph` | Full production depgraph JSON |
| `architectural_risk` | `rank_modules` ranking payload |
| `contract_facts` | Contract probe JSON text |
| `verification_evidence` | Verification probe JSON text |

## Cache key

Disk entries live under `<repo>/.jarvis_builder/benchmark_context_cache/` and include:

- Repository absolute path (hashed id prefix)
- Stage name and `production` graph scope
- Packet format (`prose` | `compact`)
- Engine/schema version digest (framework, depgraph, architectural risk, compact instrumentation, feature flags)
- Repo fingerprint from indexed `.py` production/test files (`path:mtime_ns:size`)

## Enable

```bash
set JARVIS_BENCHMARK_CONTEXT_CACHE=1
# or
python -m builder_core.benchmark_framework generate --context-cache ...
python -m builder_core.benchmark_framework profile-context --context-cache --reuse-index ...
```

## Diagnostics

`context_profile.json` in each generated task directory includes a `cache` block with per-stage `hits`, `misses`, `last_hit`, and `last_elapsed_ms` when caching is enabled.

## Correctness guarantees

- Fingerprint changes when tracked files change → new cache key (miss, recompute).
- Repo path is part of the key → no cross-repo pollution.
- `prose` and `compact` use separate version digests and filenames → no format mixing.

## Wiring

- `BenchmarkContextSession` shared per repo+format in `runner.get_benchmark_context_session`.
- `compact_packets` builders reuse session graph/ranking/subsystems when provided.
- `context_profiling.profile_jarvis_context` uses the same session when env cache is on.
- `ask.answer` is unchanged; only benchmark packet assembly paths are cached.

## Tests

`builder_core/tests/test_phase104d_cached_context_generation.py`

## Out of scope

- Scoring logic
- Ask/ranking behavior
- Caching inside `ask.answer` itself
