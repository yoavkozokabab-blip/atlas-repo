# Phase 104B Context Generation Profile

**Profiling version:** `phase104b-v1`
**Tasks profiled:** 3

> Instrumentation only — no optimization, no scoring or ask-behavior changes.
> Token figures use the Phase 104A chars/4 estimator on stage artifact text.

## Method

Each benchmark task is profiled by running read-only Builder Core stages 
sequentially. `context_assembly` executes `ask.answer` and formats the offline 
JARVIS packet. Other stages measure their artifact size and wall time even when 
that artifact is not fully duplicated in the final packet.

## Aggregate by stage

| Stage | Samples | Avg elapsed (ms) | Avg tokens | Avg % of profiled tokens |
|---|---:|---:|---:|---:|
| index_loading | 3 | 0.001 | 0.0 | 0.0 |
| repository_understanding | 3 | 0.055 | 603.0 | 19.65 |
| dependency_graph | 3 | 12588.138 | 60.0 | 1.957 |
| impact_analysis | 3 | 22.393 | 107.0 | 3.487 |
| architectural_risk | 3 | 11908.305 | 285.0 | 9.29 |
| contract_facts | 3 | 55.737 | 850.0 | 27.707 |
| verification_evidence | 3 | 4844.868 | 464.0 | 15.12 |
| serialization | 3 | 0.017 | 158.333 | 5.16 |
| context_assembly | 3 | 39.192 | 542.0 | 17.633 |

## Top 20 largest token contributors

| Rank | Stage | Avg tokens | Avg % of profiled tokens |
|---:|---|---:|---:|
| 1 | contract_facts | 850.0 | 27.707 |
| 2 | repository_understanding | 603.0 | 19.65 |
| 3 | context_assembly | 542.0 | 17.633 |
| 4 | verification_evidence | 464.0 | 15.12 |
| 5 | architectural_risk | 285.0 | 9.29 |
| 6 | serialization | 158.333 | 5.16 |
| 7 | impact_analysis | 107.0 | 3.487 |
| 8 | dependency_graph | 60.0 | 1.957 |
| 9 | index_loading | 0.0 | 0.0 |

## Top 20 slowest contributors

| Rank | Stage | Avg elapsed (ms) | Avg tokens |
|---:|---|---:|---:|
| 1 | dependency_graph | 12588.138 | 60.0 |
| 2 | architectural_risk | 11908.305 | 285.0 |
| 3 | verification_evidence | 4844.868 | 464.0 |
| 4 | contract_facts | 55.737 | 850.0 |
| 5 | context_assembly | 39.192 | 542.0 |
| 6 | impact_analysis | 22.393 | 107.0 |
| 7 | repository_understanding | 0.055 | 603.0 |
| 8 | serialization | 0.017 | 158.333 |
| 9 | index_loading | 0.001 | 0.0 |

## Sample packet record

- Task: `ru01_subsystems` (`repository_understanding`)
- Ask mode: `architecture`
- Packet tokens: 610
- Total profiled elapsed: 29952.759799998603 ms

| Stage | ms | tokens | % |
|---|---:|---:|---:|
| index_loading | 0.001 | 0 | 0.0 |
| repository_understanding | 0.060 | 603 | 19.22 |
| dependency_graph | 12639.512 | 60 | 1.91 |
| impact_analysis | 22.522 | 107 | 3.41 |
| architectural_risk | 12245.308 | 285 | 9.09 |
| contract_facts | 61.470 | 850 | 27.1 |
| verification_evidence | 4942.973 | 464 | 14.79 |
| serialization | 0.017 | 158 | 5.04 |
| context_assembly | 40.896 | 610 | 19.45 |
