# Phase 94C — Resolution Gap Analysis

**Status:** Analysis complete (read-only; no resolver changes)  
**Date:** 2026-05-31  
**Repository:** `local_jarvis`  
**Method:** `depgraph.build_graph(.)` + AST re-classification of unresolved sites  
**Reproduce:** `py -3 -m builder_core.scripts.phase94c_gap_analysis` (from repo root)

---

## 1. Executive summary

The dependency graph on `local_jarvis` resolves **6,965** call edges (**10.4%** of observed call sites) and leaves **60,186** call sites unresolved. The gap is dominated by **three causes** that together explain **~83%** of the classified unresolved surface:

| Rank | Cause | Share of classified gap |
|------|-------|-------------------------|
| 1 | **Method / attribute calls** | 32.2% |
| 2 | **Symbol not found** (intra + cross-file) | 30.1% |
| 3 | **Shadowed names** (mostly cross-file) | 21.0% |

Conservative, category-specific improvements (excluding shadowed-by-design cases) could raise call resolution from **10.4% → ~37%** at an optimistic ceiling. The highest-yield single lever is **intra-file method call resolution** (~20.9k sites).

No detector, benchmark, or promotion logic was modified.

---

## 2. Baseline metrics (measured snapshot)

| Metric | Count |
|--------|------:|
| Resolved `calls` edges | 6,965 |
| Unresolved call sites (`calls_unresolved`) | 60,186 |
| Total call sites (resolved + unresolved) | 67,151 |
| **Call resolution rate** | **10.37%** |
| Unresolved `references` (base class / decorator) | 539 |
| Unresolved external `imports` | 3,349 |

> **Note:** An earlier snapshot cited ~6,854 resolved / ~58,942 unresolved. This report uses a fresh graph build on the current tree (`graph summary --project .`).

---

## 3. Raw unresolved reason codes (call channel)

Before taxonomy roll-up, `calls_unresolved` breaks down as:

| Raw reason (depgraph / cross_file) | Count | % of call unresolved |
|-----------------------------------|------:|---------------------:|
| `intra_file_unresolved` | 39,021 | 64.8% |
| `shadowed` | 13,264 | 22.0% |
| `dynamic_or_complex` | 3,233 | 5.4% |
| `third_party_or_unknown_module` | 2,944 | 4.9% |
| `symbol_not_found` | 1,724 | 2.9% |
| **Total** | **60,186** | **100%** |

`intra_file_unresolved` is a bucket, not a semantic cause — Phase 94C sub-classifies it via AST inspection (§4).

---

## 4. Unified taxonomy (requested categories)

Mapping rules (deterministic):

| Category | Includes |
|----------|----------|
| **method_calls** | Intra-file `ast.Attribute` calls (`self.foo()`, `obj.method()`, chained attributes) |
| **symbol_not_found** | Cross-file `symbol_not_found` + intra-file bare `Name()` calls to unknown/module-level-missing symbols |
| **shadowed** | Cross-file `shadowed` + intra-file calls where callee name is locally bound |
| **dynamic_dispatch** | Cross-file `dynamic_or_complex` + intra-file non-Name/non-Attribute call targets |
| **imports** | Cross-file `third_party_or_unknown_module` at call sites + all `imports_external` module edges |
| **inheritance** | `references_unresolved` with `kind=base_class` |
| **decorators** | `references_unresolved` with `kind=decorator` |

### 4.1 Distribution (all classified unresolved relationships)

Counts include call sites plus reference/import gaps mapped to the same semantic categories:

| Category | Count | Share |
|----------|------:|------:|
| **method_calls** | 20,864 | 32.17% |
| **symbol_not_found** | 19,545 | 30.14% |
| **shadowed** | 13,586 | 20.95% |
| **imports** | 6,324 | 9.75% |
| **dynamic_dispatch** | 3,247 | 5.01% |
| **inheritance** | 298 | 0.46% |
| **decorators** | 241 | 0.37% |
| **Total classified** | **64,105** | **100%** |

### 4.2 Call-channel-only view (60,186 sites)

| Category | Call sites | % of 60,186 |
|----------|----------:|------------:|
| method_calls | 20,864 | 34.7% |
| symbol_not_found | 19,545 | 32.5% |
| shadowed | 13,586 | 22.6% |
| dynamic_dispatch | 3,247 | 5.4% |
| imports (call-time third-party) | 2,944 | 4.9% |
| *(intra misc / unclassified in raw bucket)* | 743 | 1.2% |

Reference-only items (inheritance 298, decorators 241) and module import edges (3,349) add **+878** relationships outside the call-site counter but belong in the same semantic taxonomy.

---

## 5. Ranked top causes

### 5.1 By volume (classified gap)

1. **Method calls** — 20,864  
   - Example: `actions/app_actions.py:33 caller=_app_query func=str(request.params.get('app') or ...)`
   - Root cause: `callgraph` / `cross_file` only resolve bare `Name()` to module-level functions; attribute dispatch is intentionally unresolved.

2. **Symbol not found** — 19,545  
   - Intra-file: 17,821 bare-name calls to symbols that are not module-level functions in the same file.  
   - Cross-file: 1,724 imported symbols missing from the module-level export index.  
   - Example (cross-file): imported alias resolves to module but qualname not in `{func_name: (file, qual)}` index.

3. **Shadowed** — 13,586  
   - Almost entirely cross-file (13,264): imported name rebound locally before call.  
   - Example: `actions/diagnostics_actions.py:37 caller=_run func=fn` where `fn` shadows an import.

4. **Imports** — 6,324  
   - 2,944 call-time third-party/unknown module handles.  
   - 3,349 module `imports_external` (stdlib / PyPI / unmapped paths).  
   - By design: external packages are not expanded.

5. **Dynamic dispatch** — 3,247  
   - Lambda calls, computed callables, complex attribute bases.  
   - Example: `getattr(_browser, 'is_connected', lambda: False)()`.

6. **Inheritance** — 298 unresolved base-class references.  
7. **Decorators** — 241 unresolved decorator name references.

### 5.2 By *actionable* recall potential

| Category | Safe to resolve? | Rationale |
|----------|------------------|-----------|
| method_calls | **High yield** | Deterministic for `self`/known receiver types; largest bucket |
| symbol_not_found (cross-file) | **Medium yield** | Expand export index (re-exports, class methods) |
| symbol_not_found (intra) | **Low–medium** | Many are builtins / non-function calls / nested defs |
| inheritance | **Medium** | Map resolved `references` base_class edges (partially present) |
| decorators | **Medium** | Same as import-table symbol resolution |
| imports (external) | **Low** | Third-party bodies out of scope by policy |
| shadowed | **None (by policy)** | Conservative correctness — shadowing is ambiguous |
| dynamic_dispatch | **Very low** | Requires unsafe guessing |

---

## 6. Intra-file bucket deep dive

The 39,021 `intra_file_unresolved` sites decompose as:

| Sub-cause | Count | % of intra bucket |
|-----------|------:|------------------:|
| method_calls | 20,864 | 53.5% |
| symbol_not_found (bare Name) | 17,821 | 45.7% |
| shadowed (local rebound) | 322 | 0.8% |
| dynamic_dispatch | 14 | <0.1% |
| other | 743 | 1.9% |

**Key insight:** resolving **method calls alone** addresses more than half of the opaque intra-file bucket and ~35% of all call unresolved sites.

---

## 7. Cross-file bucket deep dive

Cross-file unresolved call attempts (from `cross_file.build_project_context`):

| Reason | Count |
|--------|------:|
| shadowed | 13,264 |
| dynamic_or_complex | 3,233 |
| third_party_or_unknown_module | 2,944 |
| symbol_not_found | 1,724 |

Cross-file **resolved** edges are already working for direct `func()` and `module.func()` patterns; the remaining gap is dominated by shadowing policy and non-exported symbols.

---

## 8. Reference channel (inheritance & decorators)

| Kind | Count | Top patterns |
|------|------:|--------------|
| `base_class` | 298 | `ReadOnlyPhase45Action`, Pydantic bases, ABC mixins |
| `decorator` | 241 | `@property`, `@staticmethod`, `@dataclass`, custom decorators |

These affect **`references`** edges (impact Q5 / class hierarchy), not call edges, but share the same import-table resolver limits.

---

## 9. Potential recall gain (call-site resolution)

Assumptions are **conservative engineering estimates**, not measured fixes. Shadowed sites are assigned **0%** (intentionally unresolved).

| Category | Sites | Assumed recoverable fraction | Est. new resolved calls | Cumulative resolved rate |
|----------|------:|-----------------------------:|------------------------:|-------------------------:|
| *(baseline)* | — | — | — | **10.37%** |
| method_calls | 20,864 | 45% | +9,389 | 24.35% |
| symbol_not_found | 19,545 | 35% | +6,841 | 34.54% |
| shadowed | 13,586 | 0% | +0 | 34.54% |
| imports (call) | 2,944 | 15% | +441 | 35.95% |
| dynamic_dispatch | 3,247 | 5% | +162 | 36.20% |
| inheritance† | 298 | 70% | +209† | — |
| decorators† | 241 | 60% | +145† | — |

†Reference edges, not call sites — listed for completeness.

### 9.1 Scenarios

| Scenario | Description | Est. call resolution rate |
|----------|-------------|--------------------------:|
| **A — Method resolution only** | Resolve `self.method()` + simple receiver typing | ~24% (+14 pts) |
| **B — A + export index** | Add class methods / re-exports to cross-file index | ~35% (+25 pts) |
| **C — Optimistic ceiling** | All safe categories at assumed fractions | ~37% (+27 pts) |
| **D — Shadow lifting** | Resolve shadowed imports (unsafe) | Not recommended |

**Recommended Phase 94D priority:** Scenario **A** first (deterministic, largest bucket, no import guessing), then targeted **symbol_not_found** export indexing (Scenario B partial).

---

## 10. What not to chase

1. **Shadowed (13,586)** — Correct to stay unresolved; resolving would require flow-sensitive alias analysis.
2. **Third-party imports (3,349 module + 2,944 call)** — Out of repo scope unless stub index added.
3. **Dynamic dispatch (3,247)** — `getattr`, lambdas, computed handlers; high false-positive risk.
4. **Intra symbol_not_found (17,821)** — Mix of builtins (`str`, `len`), type constructors, nested closures; many are not graph edges.

---

## 11. Recommendations (analysis only — no code in 94C)

| Priority | Target | Expected gain | Risk |
|----------|--------|---------------|------|
| P0 | Intra-file method call edges (`self.x()`, known class receivers) | +9k–13k calls | Low |
| P1 | Module export index: class methods + `__init__.py` re-exports | +1k–3k cross-file | Medium |
| P2 | Decorator / base_class `references` via import table | +300–400 references | Low |
| P3 | Same-file nested function calls (non-shadowed) | +500–1k calls | Medium |
| Defer | Shadowed / dynamic / third-party | — | High FP |

Each improvement should preserve the **resolved-only assertion** contract used by impact analysis (Phase 94B).

---

## 12. Reproducibility

Analysis script (read-only):

```
builder_core/scripts/phase94c_gap_analysis.py
```

Run:

```powershell
cd local_jarvis
py -3 -c "import sys; sys.path.insert(0,'.'); from builder_core.scripts.phase94c_gap_analysis import analyze; import json; print(json.dumps(analyze('.'), indent=2))"
```

Inputs consumed read-only:

- `depgraph.build_graph`
- `cross_file.build_project_context`
- `callgraph` AST helpers

---

## 13. Acceptance checklist

| Criterion | Status |
|-----------|--------|
| Categorize unresolved reasons | Done (§3–§4) |
| Distribution over requested categories | Done (§4.1) |
| Rank top causes | Done (§5) |
| Measure potential recall gain | Done (§9) |
| No detector changes | Verified |
| No benchmark changes | Verified |

---

## Appendix A — Policy reminder

Current resolver contract (Phase 93A–94A):

- **Resolve:** same-file module-level `Name()`, cross-file `func()` / `module.func()` with unambiguous import-table evidence.
- **Do not resolve:** method calls, shadowed names, star/ambiguous imports, dynamic callables, third-party modules.

Phase 94C quantifies the cost of that contract: **~90% of call sites remain unresolved**, by design. Closing the gap requires **narrow, deterministic extensions** — not blanket heuristic resolution.
