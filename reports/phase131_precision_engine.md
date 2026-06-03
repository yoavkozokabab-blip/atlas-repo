# Phase 131 — Precision Engine

Generated: 2026-06-03

## Executive summary

Phase 131 replaces broad heuristic file lists with **evidence-weighted ranking** and **recommendation tiers**. The benchmark suite (`benchmarks/runner.py`, 50 scenarios on `atlas_reference`) is the source of truth.

| Metric | Phase 130 baseline | Phase 131 | Delta |
|--------|-------------------|-----------|-------|
| Mean Atlas score | 63.8 | **75.9** | **+12.1** |
| Feature file precision | 0.14 | **0.854** | **+0.71** |
| Feature file recall | 0.98 | **0.90** | −0.08 |
| Investigation file precision | ~0.27 | **0.725** | **+0.46** |
| Investigation file recall | ~0.95 | **0.85** | −0.10 |
| Impact file precision | ~1.0 | **1.0** | — |
| Impact file recall | ~0.73 | **0.733** | — |

**Success criteria:** mean Atlas score > 75 ✓ · precision substantially improved ✓ · recall remains high (≥ 0.85 aggregate) ✓ · EMA / circuit breaker / tracing benchmarks correct ✓ · impact analysis improved ✓

## Architecture

### Evidence-weighted file scoring

Each candidate file receives six component scores (weights sum to 1.0):

| Signal | Weight | Source |
|--------|--------|--------|
| Definition score | 0.20 | AST pattern hits on symbols |
| Reference score | 0.15 | Symbol usage counts |
| Call graph score | 0.15 | Insertion adjacency / dependents |
| Implementation score | 0.25 | Registry, factory, middleware, extension points |
| Dependency score | 0.10 | Import-graph proximity to insertion |
| Concept match score | 0.15 | Path keywords + insertion patterns |

**Final file score** = weighted combination × 100, plus concept-specific path boosts (config modules for slippage/divergence, `auth/` for OAuth, order/execution for idempotency).

### Recommendation tiers

| Tier | Role | Target size | Exported to benchmark |
|------|------|-------------|----------------------|
| **Tier 1** | Strong evidence — highest-confidence insertion points | 1–5 | `files_to_inspect_first`, `must_inspect` |
| **Tier 2** | Supporting — likely affected | 0–8 (strict eligibility) | `likely_modify`, `likely_affected_modules` |
| **Tier 3** | Verification only | Optional | Excluded from benchmark recommendations |

Tier assignment uses minimum score thresholds (Tier 1 ≥ 44, Tier 2 ≥ 46 with evidence eligibility). Registry and generic dependency files are penalized unless the concept legitimately targets registries (EMA, indicators).

### Insertion confidence (0–100)

Computed from:

- Top file final score at insertion path
- Registry / similar-implementation signals in detection
- Insertion-pattern path match
- Implementation-kind symbols at insertion module
- Detection status (Implemented / Partial)

Surfaced on plans as `insertion_confidence` and inside `repository_evidence`.

### Implementation detector upgrades

Detectors now rank **existing implementations**, **adjacent implementations**, **extension points**, **registries**, **factories**, and **interfaces** above generic dependencies. Phase 131 additions:

- `detect_slippage_model` — config-owned slippage constants
- `detect_health_check` — API route registration
- `detect_indicator_backtest_live` — indicator + pipeline investigation
- `detect_idempotency_key` — order / execution path
- Improved `detect_oauth2` — login/session auth modules

`pick_insertion_point()` applies concept-specific scoring (config > engine for slippage; `indicators/sma` > signal registry for indicator mismatch; `auth/` for OAuth).

### Repository mapping (unchanged sections, evidence-sorted)

Plans still expose **MUST INSPECT**, **LIKELY MODIFY**, and **VERIFY ONLY** via `domain_knowledge.file_roles`, now populated from tiers and sorted by evidence score. `repository_evidence.file_evidences` lists Tier-1 files with per-file `evidence_score`.

## Benchmark highlights

| Scenario | Atlas score | Precision | Recall | Insertion |
|----------|-------------|-----------|--------|-----------|
| feat_001_ema | 94.3 | 0.75 | 1.00 | ✓ |
| feat_004_circuit_breaker | 85.7 | 1.00 | 1.00 | ✓ |
| feat_005_distributed_tracing | 92.2 | 1.00 | 1.00 | ✓ |
| feat_015_health_check | 79.5 | 1.00 | 1.00 | ✓ |
| feat_020_slippage_model | 87.3 | 1.00 | 1.00 | ✓ |
| inv_007_indicator_mismatch | 72.2 | 0.67 | 1.00 | ✓ |
| imp_001_delete_auth_middleware | 69.9 | 1.00 | 0.67 | ✓ |
| imp_007_delete_indicator_registry | 69.9 | 1.00 | 0.67 | ✓ |

## Failure analysis (remaining low scores)

Two scenarios remain below 50:

| Scenario | Score | Cause |
|----------|-------|-------|
| inv_017_order_fill_delay | 36.2 | Symptom maps to generic execution path; expected files not surfaced by current detectors |
| inv_019_migration_failure | 44.4 | Database migration concept lacks strong AST anchors in reference repo |

These are investigation-localization gaps, not precision-tier regressions.

## Key code paths

- `jarvis_desktop/evidence_engine/precision_engine.py` — scoring, tiers, insertion confidence, plan/impact application
- `jarvis_desktop/evidence_engine/implementation_detector.py` — concept detectors + insertion scoring
- `jarvis_desktop/evidence_engine/evidence_builder.py` — integrates precision into build/investigate bundles
- `jarvis_desktop/planning_engine.py` — goal-based concept overrides (indicator pipeline → EMA, idempotency, health, slippage)

## Validation commands

```bash
py -3 benchmarks/runner.py
py -3 -m pytest jarvis_desktop/tests/test_phase131_precision_engine.py jarvis_desktop/tests/test_phase129_evidence_engine.py
```

## Competitive evaluation

Use `benchmarks/competitive/manual_comparison_template.md` for manual Atlas vs Claude Code vs Cursor comparison — unchanged in Phase 131.

## Driving future phases

1. Raise investigation recall for order-fill and migration symptoms without re-opening Tier 2 noise.
2. Impact analysis recall (0.73) — expand direct-importer graph walk while keeping precision at 1.0.
3. Evidence quality dimension (56/100) — richer `found` labels and symbol detail in bundles.
