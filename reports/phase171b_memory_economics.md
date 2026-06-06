# Phase 171B — Memory Economics

**Date:** 2026-06-05

## Token reduction summary

| Scenario | Tokens | vs P169 minimal |
| --- | ---: | ---: |
| Phase 169 minimal (per question) | 364 | baseline |
| Phase 171B memory+delta (per question) | ~107 | **-68.8%** |
| Phase 169 FULL (per question, Phase 170) | 1770 | -79% already (P169) |

## Per-repository 20-question session

| Repo | Current (session + 20× minimal) | Memory model | Reduction |
| --- | ---: | ---: | ---: |
| fastapi | 5,514 | 2,464 | 55.3% |
| django | 5,887 | 2,525 | 57.1% |
| vscode | 10,289 | 2,813 | 72.7% |
| home_assistant | 7,875 | 2,773 | 64.8% |

**Memory model** = RMO once + 20 × (delta + memory_ref).

## Structural overhead still in minimal exports

| Workflow | P169 minimal avg | Pure delta budget | Removable overhead |
| --- | ---: | ---: | ---: |
| build | 322 | 95 | 227 |
| investigate | 501 | 110 | 391 |
| impact | 269 | 75 | 194 |

## Break-even improvement (Phase 167 baseline)

| Repo | Scan (s) | Tokens saved/Q | Latency saved (ms/Q) | Session tok reduction |
| --- | ---: | ---: | ---: | ---: |
| fastapi | 2.58 | 165 | 8.2 | 55.3% |
| django | 17.52 | 183 | 9.2 | 57.1% |
| vscode | 26.95 | 399 | 20.0 | 72.7% |
| home_assistant | 334.05 | 281 | 14.1 | 64.8% |

Break-even questions improve marginally (export serialization is already fast).
**Primary economic win is token cost**, not wall-clock — especially for VS Code where
per-question exports remain large (506 tokens minimal → ~127 with memory+delta).

## Claude total path (Phase 170 baseline)

- MINIMAL total (export + response): **575** tokens/Q
- Projected memory+delta total: **~220–280** tokens/Q (export portion −70%; response unchanged)

## VS Code exception

VS Code sees the largest memory win (**71%** session reduction) because minimal exports
remain verbose (investigate avg 651 tokens). Memory+delta removes repeated scaffolding
that Phase 169 could not strip without losing UI markdown structure.
