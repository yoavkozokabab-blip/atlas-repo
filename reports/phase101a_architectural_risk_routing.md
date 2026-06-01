# Phase 101A — Architectural Risk Routing Fix

**Status:** Implemented and verified.
**Date:** 2026-06-01
**Goal:** Route architectural-risk queries to the deterministic **bottleneck**
mode (dependency-graph fan-in + cycles + central modules) instead of the keyword
retrieval fallback.

---

## 1. Why the router missed (root cause)

The failing query:

> "Rank the top architectural risk modules in this repository using dependency
> graph fan-in, module size, import cycles, and test coverage."

fell through to `_answer_retrieval` because of **two compounding bugs**.

### Bug 1 — no Tier-1 anchor for architectural-risk vocabulary
`question_understanding._TIER1` had **no pattern** for "architectural risk",
"risk modules", "blast radius", "fan-in", "import cycles", or "structural
fragility". The existing `bottleneck` anchor required the literal word
`bottleneck` / `architectural bottleneck` / `critical architectural` — none of
which appear. The `architecture` anchor used `\barchitecture\b`, which does **not**
match "architectur**al**" (the word boundary fails before `al`). So **no Tier-1
anchor fired.**

The question then fell to the Tier-2 weak lexicon, where it scored
`dependency_centrality = 2` (from "module" + "dependency") — a *fragile, accidental*
classification driven by incidental tokens, not by intent.

### Bug 2 — the graph router was anchor-gated, and the fallback dropped graph modes
`ask._route_ru3_answer` began with:

```python
if not str(detail.get("fired_rule", "")).startswith("anchor:"):
    return None        # Tier-2 matches never reach the graph handlers
```

So the Tier-2 `dependency_centrality` classification returned `None`, and control
fell to `public_answer_mode`, which returned `"dependency"`. But `answer()`'s
fallback dispatch only handled `"risk"` and `"architecture"`:

```python
if mode == "risk":        ...
elif mode == "architecture": ...
else:                     result = _answer_retrieval(...)   # <- everything else
```

`"dependency"` (and `"bottleneck"`, `"subsystem"`, `"production_layout"`,
`"impact"`) silently hit the `else` → **retrieval**. So even the weakly-correct
classification could never reach a graph handler.

**Net:** architectural-risk intent had no high-precision anchor, and the one path
that could have salvaged it (Tier-2 → graph mode) was severed by the anchor gate
plus an incomplete dispatch.

---

## 2. The fix

### 2.1 Added Tier-1 anchor coverage (→ category `bottleneck`)
Extended the `bottleneck` anchor in `question_understanding._TIER1` to cover the
architectural-risk vocabulary (weight 4, high precision):

```
bottleneck(s) · architectural bottleneck(s) · critical architectural ·
architectural risk · architecture risk · risk module(s) · riskiest module(s) ·
blast radius · fan-in / fan in · import cycle(s) · dependency cycle(s) ·
circular import(s)/dependencies · structural fragility · highly/most coupled ·
most depended
```

### 2.2 Fixed the `architecture` anchor regex
`\barchitecture\b` → `\barchitectur\w*\b` so "architectural" / "architectures" are
recognized. (The new bottleneck anchor at weight 4 still outranks the weight-2
architecture anchor, so "architectural risk" → `bottleneck`, while a plain
"system architecture overview" → `architecture`.)

### 2.3 Reinforced the Tier-2 bottleneck lexicon
Added `fan, cycle, cycles, coupled, coupling, blast` (architectural-only terms; no
generic "risk" term, to avoid hijacking ordinary risk questions).

### 2.4 Removed the anchor-only gate in `_route_ru3_answer`
Now routes on the **resolved category**. `classify_question_detail` already gates
low-confidence/ambiguous questions to `unknown` (which is not in the handler map
and falls through to coarse routing), so any concrete graph category — from a
Tier-1 anchor **or** a confident Tier-2 match — dispatches to its handler instead
of silently falling back to retrieval. This closes Bug 2 for all five graph
categories, not just architectural risk.

**Scope:** classifier patterns + one routing-gate change. No detector, finding,
benchmark, or graph-builder change.

---

## 3. Regression tests

`builder_core/tests/test_phase101a_architectural_risk_routing.py` (6 tests):

| Test | Asserts |
|---|---|
| `…classify_as_bottleneck` | all 9 architectural-risk phrasings → category `bottleneck`, `fired_rule` starts with `anchor:` (incl. the original failing question) |
| `…routes_to_bottleneck_not_retrieval` | `ask.answer(...)` mode is `bottleneck`, **not** the retrieval prose |
| `…cites_fanin_and_cycles` | on a synthetic repo (fan-in hub + `ring.x↔ring.y` cycle), the answer cites `fan-in`, `cycle`, and the `core` hub — i.e. real graph data |
| `…generic_risk…still_routes_to_risk` | "biggest risks in this codebase" still → `risk` mode (preserved) |
| `…architecture_overview_still_routes_to_architecture` | "system architecture overview" → `architecture` (not hijacked) |
| `…deterministic` | identical classification across repeated calls |

---

## 4. Verification

```
py -3 -m pytest builder_core/tests/test_phase101a_architectural_risk_routing.py -q
6 passed

py -3 -m pytest builder_core/tests/ -q
377 passed

py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
12 true positives, 0 false positives
```

End-to-end on the exact failing query:

```
category : bottleneck
fired    : anchor:bottleneck
pub mode : bottleneck
route    : bottleneck-handler
```

It now reaches `_answer_bottlenecks`. (On the full `local_jarvis` repo the
dependency graph still **degrades** — 7,539 `.py`, 5,984 under `data/`, over the
5,000-file cap — so the handler honestly returns *"Dependency graph degraded —
cannot compute architectural bottlenecks"* rather than the rich fan-in/cycle
ranking. That is the separate **Phase 100G** depgraph-scope issue, not a routing
defect: routing is fixed; the handler's output quality on large repos depends on
the 100G role-filter fix. On a normal-sized repo the handler produces the full
ranking, as the synthetic-repo test confirms.)

---

## 5. Files

```
Modified:
  builder_core/question_understanding.py   # bottleneck anchor + architecture regex + lexicon
  builder_core/ask.py                       # _route_ru3_answer routes on category (drop anchor gate)
Added:
  builder_core/tests/test_phase101a_architectural_risk_routing.py
  reports/phase101a_architectural_risk_routing.md
```

## 6. Safety

- No detector, finding schema, benchmark, or promotion change (QuixBugs 12/0,
  holdout unchanged; full suite 377 passed).
- Deterministic, evidence-based routing; generic risk and architecture-overview
  routing preserved.
- Honest degradation: the bottleneck handler reports the degraded graph rather
  than guessing — consistent with "unknown beats guessing".
