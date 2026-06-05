# Phase 169 — Export Regression Report

**Date:** 2026-06-05  
**Repo:** `benchmarks/repos/atlas_reference`  
**Suite:** `jarvis_desktop/tests/test_phase169_export_regression.py` (+ Phase 164/164D trust)

## Test results

| Suite | Result |
| --- | --- |
| `test_phase169_export_regression.py` (7) | **7 passed** |
| `test_phase164_surgical_trust_fixes.py` (15) | **15 passed** |
| `test_phase164d_kubernetes_impact_refusal.py` (9) | **9 passed** |

## FULL_EXPORT vs MINIMAL_EXPORT

Token estimates use `len(text) / 4` (same as Atlas API).

### Session (once per scan)

| Metric | Value |
| --- | ---: |
| Session tokens | 81 |
| Budget (Phase 168 spec) | ≤350 |
| Pass | ✅ |

### Per-workflow (reference repo)

| Workflow | Full tokens | Minimal tokens | Reduction | Fidelity | Quality loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| Build | 1,904 | 106 | **94.4%** | 100% | 0.0% |
| Investigate | 2,208 | 298 | **86.5%** | 100% | 0.0% |
| Impact | 286 | 29 | **89.9%** | 100% | 0.0% |

**Aggregate reduction (workflows only):** 90.3% average  
**Target:** ≥40% → **PASS**

**Quality loss:** max 0.0% (structural proxy)  
**Target:** ≤5% → **PASS**

## Fidelity checks (structural proxy)

For each workflow, `quality_fidelity_score()` verifies:

- Top canonical file paths appear in minimal export
- Confidence string preserved
- Minimal token count < full token count

All three workflows: `confidence_preserved = true`, `minimal_smaller = true`.

## Removed-content verification

Minimal exports must not contain (case-insensitive):

- `rollback`
- `how to work safely`
- `how to use`
- `concept understanding`
- `repository evidence`

**Result:** No forbidden phrases in build/investigate/impact minimal bodies.

## Trust regression

| Check | Result |
| --- | --- |
| Confidence in minimal export | ✅ Present for build, investigate, impact |
| `bug_investigation` no mock success | ✅ Phase 164 |
| Legacy `impact()` unresolved → not ok | ✅ Phase 164 |
| Shallow impact refusal (`validation/missing.py`) | ✅ `ok=false`, no mock bypass |
| JS trust block retained for legacy fallback | ✅ `zfTrustBlock` still defined |

## Impact regression

| Check | Result |
| --- | --- |
| Impact analysis still returns direct/indirect lists | ✅ |
| Export blocks attached on successful impact | ✅ `export`, `export_full`, `export_minimal` |
| Refused impact skips rich export (no false ok) | ✅ |

## UI regression

| Check | Result |
| --- | --- |
| `zfServerExportText` uses API export | ✅ |
| Session prefix once per copy | ✅ `zfSessionPrefix` |
| Default mode `MINIMAL_EXPORT` | ✅ |

## Conclusion

Phase 169 meets all success criteria on the reference repository benchmark:

1. **≥40% reduction** — achieved 86–94% per workflow  
2. **≤5% quality loss** — 0% on structural fidelity proxy  
3. **No trust regression** — Phase 164/164D green  
4. **No impact regression** — analysis and refusal behavior unchanged  

Production default is `MINIMAL_EXPORT` with session context sent once per scan, matching the Phase 168 minimal export spec.
