# Phase 102B — Architectural Risk Ranking Trust Hardening

**Status:** Implemented and verified.
**Date:** 2026-06-01
**Goal:** Make Phase 102 rankings **trustworthy** — deduped graph metrics, canonical
cycles, AST-backed test evidence, separated evidence channels, LOC gated on real
risk signals, removal of dead `component_root` scoring, and per-module diagnostics.

---

## 1. Trust fixes (summary)

| Issue (102) | 102B fix |
|---|---|
| Duplicate import edges inflated fan-in | Count each `(importer, imported)` pair once |
| Duplicate / rotated cycle nodes | Canonicalize cycles; expose `import_cycles_canonical` |
| Substring “tested” via `_test_corpus` | AST: `import` / `import from` / qualified refs / resolved calls only |
| All static findings → `contract_evidence` | Split `contract_evidence`, `static_findings`, `test_evidence` |
| Large isolated files outranking hubs | `module_size_loc` only when blast-radius or safety-gap signals fire |
| Dead `component_root` (union-all graph) | Removed from scoring |
| Opaque totals | `rank_diagnostics[]` per ranked module |

**Engine:** `phase102b-v1` · **Schema:** `2`

---

## 2. Evidence channels

### `contract_evidence`
- Contract-shaped **index findings** only (`wrong_return_shape`, etc.).
- Optional `contract_facts.extract_module_contracts` when those findings exist (no whole-repo parse).

### `static_findings`
- Other `python_analysis` findings (excludes contract rules and `missing_test_reference`).

### `test_evidence`
- Negative weight (`-1.5`) when AST test binding exists.
- `untested_module` (+3.0) when no binding.

Test files are read from disk when indexed (chunks are often partial).

### LOC gate (`module_size_loc`)
Applies only when at least one of:
- `fan_in ≥ 1` or `fan_out ≥ 2`
- import-cycle member
- no AST test reference
- subsystem cross fan-in ≥ 2
- `contract_evidence > 0` or `static_findings > 0`

---

## 3. Structured payload additions

```json
{
  "engine_version": "phase102b-v1",
  "schema_version": 2,
  "deduped_import_pairs": 1654,
  "import_cycles_canonical": [["module:a.py", "module:b.py"]],
  "ranked_modules": [{
    "rank_diagnostics": [
      "fan-in=206 unique importers → +206.0",
      "test reference binds → -1.5"
    ],
    "score_breakdown": {
      "fan_in": 206.0,
      "test_evidence": -1.5,
      "static_findings": 0.0,
      "contract_evidence": 0.0
    }
  }]
}
```

`component_root` removed from `score_breakdown`.

---

## 4. Verification

| Suite | Result |
|---|---|
| `test_phase102b_architectural_risk_trust.py` (8 tests) | pass |
| `test_phase102_architectural_risk_ranking.py` | pass (schema 2 keys) |
| Full `builder_core/tests` | **400 passed** |

### Exact query E2E (`local_jarvis`, cached index)

```
Rank the top architectural risk modules in this repository using dependency
graph fan-in, module size, import cycles, and test coverage.
```

| Check | Result |
|---|---|
| `mode` | `bottleneck` |
| `engine_version` | `phase102b-v1` |
| `degraded` | `False` |
| Deduped fan-in | `config` **206** (was 212 duplicate edges) |
| Top module | `config` total **212.8** with `test_evidence=-1.5` |
| Diagnostics | Present on each ranked row |

### QuixBugs

```
true positives: 12 | false positives: 0 (unchanged)
```

---

## 5. Files

| File | Change |
|---|---|
| `builder_core/architectural_risk.py` | 102B trust logic |
| `builder_core/tests/test_phase102b_architectural_risk_trust.py` | New regressions |
| `builder_core/tests/test_phase102_architectural_risk_ranking.py` | Updated breakdown keys |

---

## 6. Notes

- Import fan-in on full `local_jarvis` drops slightly after dedup (expected).
- `test_evidence` reduces scores for well-tested hubs; hubs with high fan-in still dominate.
- Contract-facts extraction is gated on contract-shaped findings to keep ranking fast on large repos.
