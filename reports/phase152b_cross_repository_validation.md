# Phase 152B Cross-Repository Validation Campaign

Generated: 2026-06-04T19:55:26

## Summary

- Repositories attempted: 23
- Completed measured scans: 22
- Result directory: benchmarks/validation_campaign/results/
- Per-repo timeout for new live scans: 300s

## Best Results

| Repo | Language | Overall | Modules | Edges |
| --- | --- | --- | --- | --- |
| airflow | Python | 92.5 | 4332 | 835 |
| typeorm | TypeScript | 88.5 | 569 | 2735 |
| celery | Python | 86.0 | 215 | 575 |
| turborepo | TypeScript | 86.0 | 218 | 335 |
| django | Python | 85.0 | 929 | 2915 |

## Worst Results

| Repo | Language | Status | Overall | Failures |
| --- | --- | --- | --- | --- |
| gin | Go | measured | 61.0 | graph_failure, language_support_gap |
| spring_boot_example | Java | measured | 61.0 | graph_failure, language_support_gap |
| kubernetes | Go | measured | 71.0 | unresolved_import_explosion |
| aspnet_example | C# | measured | 72.25 | language_support_gap |
| langchain | Python | measured | 81.25 | unresolved_import_explosion |

## Cross-Language Performance

| Language | Repos | Measured | Avg overall | Avg modules | Avg edges |
| --- | --- | --- | --- | --- | --- |
| C# | 1 | 1 | 72.25 | 1.0 | 0.0 |
| Go | 2 | 2 | 66.0 | 1.5 | 0.0 |
| Java | 1 | 1 | 61.0 | 0.0 | 0.0 |
| Python | 12 | 11 | 78.31 | 1567.73 | 3768.36 |
| Rust | 1 | 1 | 81.25 | 4.0 | 0.0 |
| TypeScript | 6 | 6 | 85.75 | 2409.5 | 4455.83 |

## Biggest Limitations

- unresolved_import_explosion: 6 repo(s) - airflow, kubernetes, langchain, pydantic, qdrant, vscode
- language_support_gap: 3 repo(s) - aspnet_example, gin, spring_boot_example
- graph_failure: 3 repo(s) - atlas_self, gin, spring_boot_example
- build_plan_failure: 1 repo(s) - atlas_self
- impact_failure: 1 repo(s) - atlas_self
- investigation_failure: 1 repo(s) - atlas_self
- partial_graph: 1 repo(s) - atlas_self
- scan_timeout: 1 repo(s) - atlas_self

## Recommended Next Engineering Priorities

- Improve non-Python/TypeScript graph extraction where language_support_gap appears.
- Reduce unresolved import explosions before making stronger impact-analysis claims.
- Add scan timeout/degraded-result UX so large repos produce useful partial evidence instead of silent long waits.
- Separate centrality, risk, and partial-coverage confidence in benchmark-facing reports.
- Re-run live scans on overnight-reused repositories when a full unattended window is available.

## Measurement Notes

- This campaign did not modify Atlas intelligence or product code.
- Existing overnight evidence from 2026-06-04 was reused for repositories already measured there; newly cloned Phase 152B additions were measured live.
- Marketing claims are limited to the measured evidence above.
