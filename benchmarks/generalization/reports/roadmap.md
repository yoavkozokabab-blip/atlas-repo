# Phase 136 — Atlas Cross-Repository Roadmap Analysis

Evidence base: **6** scored repositories, 28 recorded structural failures across 18 distinct failure patterns.

## Capability scores (mean across scored repos)

| Capability | Mean | Spread (σ) | Recoverable overall pts (→90) |
|---|---:|---:|---:|
| Repository Understanding | 93.0 | ±12.8 | 0.0 |
| Impact Analysis | 49.7 | ±25.5 | 12.1 |
| Investigation | 100.0 | ±0.0 | 0.0 |
| Build Plan | 96.9 | ±7.0 | 0.0 |

## What Atlas does consistently well

- Investigation (mean 100.0, spread ±0.0)
- Build Plan (mean 96.9, spread ±7.0)

## What Atlas does inconsistently

- Impact Analysis (mean 49.7, spread ±25.5)

## What completely breaks

- Universal fallback: Concept "the logging layer" not resolved (fallback)

## Most common failure class

- **semantic_routing_failure** — 23 occurrences (Impact Analysis).

## Most damaging failure class

- **IMPACT capability via resolver_failure/semantic_routing_failure** — largest recoverable overall gain (**12.1 pts** to the mean). Low capability mean (49.7) × heaviest unrealised weight.

## Highest confidence capability

- **Investigation** — mean 100.0, spread ±0.0.

## Lowest confidence capability

- **Impact Analysis** — mean 49.7, spread ±25.5.

## Top 10 improvements by expected score gain

Gain = estimated increase to the **mean overall** score if the fix lands across all affected repositories (model stated above).

| # | Improvement | Capability | Repos affected | Est. overall gain | Suggested phase |
|---:|---|---|---:|---:|---|
| 1 | Concept "the logging layer" not resolved (fallback) | Impact Analysis | 6 | +3.16 | Phase 137 |
| 2 | Concept "caching" not resolved (fallback) | Impact Analysis | 3 | +1.58 | Phase 137 |
| 3 | Concept "configuration" not resolved (fallback) | Impact Analysis | 3 | +1.58 | Phase 137 |
| 4 | Concept "authentication" not resolved (fallback) | Impact Analysis | 2 | +1.05 | Phase 137 |
| 5 | Concept "the impact engine" not resolved (fallback) | Impact Analysis | 1 | +0.53 | Phase 137 |
| 6 | Concept "the planning engine" not resolved (fallback) | Impact Analysis | 1 | +0.53 | Phase 137 |
| 7 | Concept "the architecture analyzer" not resolved (fallback) | Impact Analysis | 1 | +0.53 | Phase 137 |
| 8 | Concept "dependency injection" not resolved (fallback) | Impact Analysis | 1 | +0.53 | Phase 137 |
| 9 | Concept "request validation" not resolved (fallback) | Impact Analysis | 1 | +0.53 | Phase 137 |
| 10 | Concept "the database layer" not resolved (fallback) | Impact Analysis | 1 | +0.53 | Phase 137 |

**Combined estimated gain of the top 10:** +10.6 overall-mean points (current mean overall 82.5).

## Recommended next phase

The evidence points first at **Phase 137 — Semantic Generalization (universal concept inference beyond the HA-tuned map)**: it is both the most common failure class and the lever on Atlas's lowest-confidence, heaviest-weighted capability. Sequence the remaining phases (138–143) by the gains above.
