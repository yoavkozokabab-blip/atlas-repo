# RU-3 — Architectural Question Understanding (Implementation)

**Status:** Implemented  
**Date:** 2026-05-31  
**Design:** `reports/ru3_architectural_question_understanding_design.md`

---

## Summary

Added a deterministic question-understanding layer that routes architectural repository questions to graph/index-backed handlers while preserving the public `ask.classify()` coarse contract (`risk` / `architecture` / `retrieval`).

No changes to detectors, benchmarks, promotion logic, depgraph, impact engine, or retrieval ranking.

---

## Compatibility strategy

| Layer | Behavior |
|-------|----------|
| `ask.classify()` | Unchanged coarse values via `question_understanding.coarse_classify()` |
| RU-2 architecture battery | Still returns `mode == "architecture"` |
| RU-3 specialized questions | New answer modes: `production_layout`, `dependency`, `subsystem`, `bottleneck`, `impact` |
| Internal taxonomy | `question_understanding.classify_question_detail()` |

Architecture-family questions that are not RU-3 specialized (including the four RU-2 regression questions) continue to use the RU-2 subsystem-map handler with `mode="architecture"`.

---

## Deliverables

| Artifact | Path |
|----------|------|
| Classifier | `builder_core/question_understanding.py` |
| Routing + handlers | `builder_core/ask.py` |
| Feature flag | `QUESTION_UNDERSTANDING_ENABLED = True` |
| RU-2 regressions | `builder_core/tests/test_ru2_repository_understanding.py` (unchanged expectations) |
| RU-3 tests | `builder_core/tests/test_ru3_architectural_question_understanding.py` |
| Report | `reports/ru3_architectural_question_understanding_implementation.md` |

---

## Routing map

| Question (acceptance) | Detail category | Answer mode | Evidence source |
|-----------------------|-----------------|-------------|-----------------|
| Highest incoming dependencies | `dependency_centrality` | `dependency` | depgraph reverse `imports` + statistics cross-check |
| Most central production subsystems | `subsystem_centrality` | `subsystem` | depgraph cross-subsystem import fan-in |
| Critical architectural bottlenecks | `bottleneck` | `bottleneck` | import fan-in + import cycles + largest components |
| Highest production concentration | `production_layout` | `production_layout` | index subsystems `role_counts` density ranking |

Additional routes (design-ready, not acceptance-critical):

- `impact` → `impact.analyze_impact()` when a file target is named
- `execution_path`, generic `architecture`, `subsystem` → fall back to coarse mode (RU-2 compatible)

---

## Handler details

### production_layout

Ranks `production_subsystems` by `production_code / file_count` (density), then absolute production count. Evidence cites subsystem map lines only — no generic retrieval prose.

### dependency_centrality

Builds depgraph once; counts resolved reverse `imports` edges per module; ranks modules; cites importer `path:line` edges. Cross-checks top module against `statistics.top_imported_modules` when present.

### subsystem_centrality

Rolls resolved `imports` edges to top-level subsystems; fan-in = distinct importing subsystems; ranks `(fan-in desc, fan-out asc, name)`.

### bottleneck

Scores modules by import fan-in, bonus for import-cycle membership and largest-component roots; ranks deterministically.

Degraded/missing graph → explicit “cannot compute” answer with `support_confidence: unknown` (no guessing).

---

## Public API

```python
from builder_core import ask, question_understanding

ask.classify(question)  # "risk" | "architecture" | "retrieval"
detail = question_understanding.classify_question_detail(question)
# {"category", "confidence", "fired_rule", "alternatives", "coarse_mode"}
result = ask.answer(index, question)
# adds question_detail; RU-3 modes when specialized
```

---

## Verification

| Check | Result |
|-------|--------|
| RU-2 tests | Pass unchanged |
| RU-3 tests (4 acceptance questions) | Pass |
| Full `builder_core` suite | Pass |
| QuixBugs / Holdout (via existing benchmark tests) | Unchanged |

---

## Rollback

Set `QUESTION_UNDERSTANDING_ENABLED = False` to restore exact RU-2 routing (`classify` + three handlers only). Delete `question_understanding.py` and RU-3 tests for hard rollback.
