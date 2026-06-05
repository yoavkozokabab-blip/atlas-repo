# Phase 164D — Final Kubernetes Impact Refusal Fix

Date: 2026-06-05  
Scope: Impact engine only. No changes to Build Plan, Investigation, concept matching, UI, website, installer, billing, or benchmarks.

## Problem (Trust Audit v2 blocker)

Trust Score v2: **89.3/100** — all checks passed except **Kubernetes Impact refusals 5/6**.

| ID | Target | Before | Issue |
| --- | --- | --- | --- |
| P-KU-01..05 | Go kubelet/scheduler/controller paths | `ok=false` | Correct |
| **P-KU-06** | `staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go` | **`ok=true`, `status=resolved`** | **WRONG** |

Kubernetes scan state: **24,860 files**, **3 modules**, **0 edges**, graph health **`unsupported_language_limited`**.

## Root cause

P-KU-06 path contains the segment `/validation/`. The impact engine's generic concept lexicon matches **`validation`** via `resolve_generic_concept()` → `match_concept(query)`.

That semantic fallback scored the few indexed Python hack scripts (`hack/boilerplate/boilerplate.py`, etc.) and returned a fake blast radius (including symbol-name pollution like `argumentparser`, `abspath`).

P-KU-01..05 paths did **not** trigger a generic concept match, so they correctly returned `target_not_resolved`.

**Trace path:** `analyze_impact` → `_find_target` miss → `resolve_semantic_target` → `resolve_generic_concept("validation")` → synthetic `primary_node` → `ok=true` with garbage `affected_files`.

Not caused by legacy `/api/impact` route — modern `impact_engine.analyze_impact` only.

## Fix

**File:** `jarvis_desktop/impact_engine/engine.py`

Added shallow-graph guard (`P164D`):

1. `_is_shallow_impact_graph(scan)` — true when `graph_health == unsupported_language_limited` OR `files > 1000` and `modules < 25`.
2. On shallow graphs, **disable** semantic/concept/basename resolution.
3. Allow `ok=true` only when:
   - Target path **exactly** exists in the production graph, **and**
   - Target has **resolved import edges** OR **symbol-index evidence** for that exact path.
4. Otherwise return `_shallow_graph_impact_refusal()`:
   - `ok=false`
   - `status=unsupported_language_limited` or `target_not_resolved`
   - `confidence=low`
   - Empty `direct_impact`, `affected_files`, `architectural_blast_radius=0`
   - Clear message that graph support is too shallow

## Before / After (P-KU-06)

**Before:**
```json
{
  "ok": true,
  "status": "resolved",
  "affected_files": ["hack/boilerplate/boilerplate.py", "argumentparser", "..."],
  "architectural_blast_radius": 9
}
```

**After:**
```json
{
  "ok": false,
  "status": "unsupported_language_limited",
  "confidence": "low",
  "direct_impact": [],
  "affected_files": [],
  "message": "Impact analysis is unavailable ... graph support is too shallow ..."
}
```

## Tests

**New:** `jarvis_desktop/tests/test_phase164d_kubernetes_impact_refusal.py`

- All 6 P-KU impact targets → `ok=false`
- P-KU-06 regression: no `hack/boilerplate` fake resolution
- Shallow exact Python path without edges → refuses
- Healthy Python graph → semantic/exact resolution still works

**Validation:**
```
py -3 -m pytest jarvis_desktop/tests/test_phase164_surgical_trust_fixes.py -q   → 15 passed
py -3 -m pytest jarvis_desktop/tests/test_phase164d_kubernetes_impact_refusal.py -q → 9 passed
```

## Expected Trust Audit v2 impact

Kubernetes Impact refusals: **6/6** (was 5/6).  
Trust Score v2 should clear the final blocker without changing other workflows.
