# Phase 96A — Contract Facts Infrastructure

**Status:** Implemented  
**Date:** 2026-05-31  
**Scope:** Contract extraction infrastructure only  
**Design:** `reports/phase96_contract_analysis_design.md`  
**Constraints:** no confirmed bugs, no detector promotion, no benchmark behavior changes

---

## Summary

Phase 96A adds a **findings-free contract fact layer** to the Builder Intelligence
Engine. Contract facts are extracted deterministically from seven source classes,
bucketed into five contract types, and attached to `AnalysisResult.facts["contracts"]`
for inspection and future confirmation evaluators (Phase 96B+).

**Nothing in this phase:**

- emits new findings;
- promotes review leads to confirmed defects;
- changes detector or benchmark behavior;
- is consumed by any detector.

---

## Deliverables

| Item | Location |
|------|----------|
| Contract model + extractors | `builder_core/bug_intelligence/contract_facts.py` |
| Engine wiring (additive augmenter) | `builder_core/bug_intelligence/agents.py` (`ContractFactsAgent`) |
| Analysis pipeline registration | `builder_core/bug_intelligence/engine.py` (`_fact_augmenters`) |
| CLI inspection hook | `EvidenceFormatterAgent` → `CONTRACT FACTS` section |
| Regression tests | `builder_core/tests/test_phase96a_contract_facts.py` (19 tests) |

Feature flag: `contract_facts.CONTRACT_FACTS_ENABLED = True` (set `False` to omit).

---

## Contract model

Each fact is a JSON-serializable record:

```text
{
  "contract_type": "return_contract" | "argument_contract" | "nullability_contract"
                   | "exception_contract" | "state_mutation_contract",
  "subject": {"file": "...", "qualname": "...", "slot": "return" | "param:name" | ...},
  "obligation": "return.non_none" | "arg.non_none" | "null.forbidden" | ...,
  "confidence": "explicit" | "inferred_strong" | "inferred_weak" | "unknown",
  "sources": ["type_hint", "docstring", ...],
  "evidence_refs": [{"source": "...", "line": N, ...}],
  "scope": "intra_file" | "repository",
  "exceptions": []
}
```

### Output shape (`module_facts["contracts"]`)

```text
{
  "enabled": true,
  "return_contracts": [...],
  "argument_contracts": [...],
  "nullability_contracts": [...],
  "exception_contracts": [...],
  "state_mutation_contracts": [...],
  "statistics": {
    "total": N,
    "by_kind": {...},
    "by_confidence": {...},
    "by_source": {...}
  }
}
```

---

## Sources implemented

| Source | Extracts | Default confidence |
|--------|----------|-------------------|
| **type_hint** | Return/param annotations → return/arg/null obligations | `explicit` (or `unknown` for `Any`) |
| **docstring** | `Returns:`, `Args:`, `Raises:` sections | `explicit` |
| **assert** | `assert x is not None`, `assert self._f is not None` | `explicit` |
| **test** | `test_expectations` from fact model | `inferred_weak` |
| **caller_behavior** | Call-graph usage: deref vs null-check per callee | `inferred_strong` / `inferred_weak` |
| **callee_behavior** | Param deref without guard; `__init__` field reads | `inferred_strong` / `inferred_weak` |
| **guard** | `is None` / `is not None` branches; valueflow nullability facts | `inferred_strong` |

Caller behavior requires Phase 93A `interproc.call_graph` (attached before contract extraction).

---

## Confidence levels

| Level | Used when |
|-------|-----------|
| `explicit` | Type hint, structured docstring, assert |
| `inferred_strong` | All resolved deref callers and no null-check; callee param deref; dominating guards |
| `inferred_weak` | Mixed caller usage; test expectations; `__init__` field read inference |
| `unknown` | Non-optional annotation ambiguous (`Any`, unresolved union) |

No record uses a `confirmed_bug` category. Confirmation is explicitly deferred to Phase 96B+.

---

## Integration

### Pipeline order

```text
FactExtractionAgent
  -> InterproceduralAgent (93A call graph)
  -> ContractFactsAgent (96A)   # NEW
  -> [optional cross_file facts in project mode]
  -> detectors (unchanged; do NOT read contracts)
```

### Inspection

**Programmatic:**

```python
from builder_core.bug_intelligence import engine
res = engine.analyze_source(text, "m.py")
contracts = res.facts["contracts"]
```

**CLI formatter:**

```text
CONTRACT FACTS
- total=5 by_kind={'return_contract': 2, ...} by_confidence={'explicit': 3, ...}
```

---

## Verification

| Criterion | Result |
|-----------|--------|
| Full suite | **303 passed** |
| Phase 96A tests | **19 passed** |
| New findings | **None** (finding count unchanged on fixtures) |
| Confirmed bug category | **None** |
| Detector changes | **None** (detectors do not read `contracts`) |
| QuixBugs (mini fixture) | 1 TP / 0 FP unchanged |
| QuixBugs (full corpus, when present) | 12 TP / 0 FP unchanged |
| Holdout (when present) | 2 TP / 0 FP unchanged |

---

## Example (synthetic)

```python
def helper() -> str:
    return "ok"

def caller():
    return helper().upper()
```

Extracted facts include:

- `helper` → `return.non_none` (`explicit`, `type_hint`)
- `helper` → `return.non_none` (`inferred_strong`, `caller_behavior`) from deref in `caller`
- `helper` → `null.forbidden` on return (`inferred_strong`, `caller_behavior`)

---

## Non-goals (deferred)

| Deferred to | Item |
|-------------|------|
| Phase 96B+ | Contract violation evaluation |
| Phase 96B+ | Confirmation verdict / promotion |
| Phase 96B+ | Guard-aware path feasibility for null-deref leads |
| Phase 96C+ | Cross-file caller contract strengthening |
| Future | LLM or heuristic docstring NLP |

---

## Reproducibility

```powershell
cd local_jarvis
py -3 -m pytest builder_core/tests/test_phase96a_contract_facts.py -q
py -3 -m pytest builder_core/tests -q
py -3 -c "import textwrap; from builder_core.bug_intelligence import engine; r=engine.analyze_source('def f()->int:\n return 1\n','m.py'); print(r.facts['contracts']['statistics'])"
```

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| Five contract type buckets | Done |
| Seven sources | Done |
| Four confidence levels | Done |
| Facts only (no confirmation) | Done |
| Attached to analysis output | Done |
| No detector consumption | Done |
| Synthetic fixture tests | Done |
| Report | Done |
| Full suite / QuixBugs / Holdout unchanged | Verified |
