# Phase 129 — Repository Evidence Engine

## Summary

Atlas now grounds Build Plan and Investigate recommendations in **AST-backed repository evidence**, not path-name heuristics alone.

## Architecture

```
jarvis_desktop/evidence_engine/
├── evidence_models.py      — SymbolRecord, FileEvidence, RepositoryEvidenceBundle
├── ast_scanner.py          — Python AST: defs, imports, calls, inheritance, decorators
├── symbol_index.py         — Repository-wide symbol index (cached on scan)
├── call_graph.py           — Function-level callers/callees
├── implementation_detector.py — Concept detectors (EMA, circuit breaker, tracing, …)
└── evidence_builder.py     — Build store, analyze concepts, merge into plans
```

## Scan integration

After graph + index build, `api.scan_repository` runs `build_evidence_store()` and stores:

- `_STATE["evidence_store"]` — serializable symbol index + call graph
- Scan cache includes `evidence_store` for cache hits

## Plan integration

Build Plan and Investigate:

1. Classify concept (Knowledge Engine)
2. Run implementation detector against AST index
3. Merge file roles by **evidence score** (over path keywords)
4. Emit `repository_evidence` block with Found / Missing / Recommended insertion / Score

## Evidence types collected

Functions, classes, methods, imports, decorators, inheritance, registries, middleware, config/feature flags, retry loops, HTTP clients, auth boundaries.

## Detectors (initial set)

| Concept | Finds | Missing signal |
|---------|-------|----------------|
| EMA | SMA, registry, signal pipeline | EMA implementation |
| Circuit breaker | HTTP client, retry | Breaker state |
| Distributed tracing | request_id, logging middleware | trace/span propagation |
| Retry/backoff | retry loops, sleep | jitter (optional) |
| Feature flags | FEATURE_* config | rollout evaluator |
| JWT/auth | authenticate, middleware | validation hardening |
| Backtest divergence | slippage/fill mismatch across paths | aligned config |

## UI / exports

- Build Plan and Investigate show **Repository Evidence** panel
- Markdown exports include `REPOSITORY EVIDENCE` section with score and per-file symbols

## Constraints

- Local-only: no LLM, no API, no web retrieval
- Python AST primary (JS/TS via existing import graph only)

## Tests

`jarvis_desktop/tests/test_phase129_evidence_engine.py`

## Success criteria

Atlas can answer **"Why this file?"** with:

- file path
- symbol names found in AST
- what is implemented vs missing
- evidence score / confidence
