# Post-Benchmark ROI Analysis

Date: 2026-06-04

Input data:

- `benchmarks/overnight_validation/aggregate_results.json`
- `reports/overnight_repository_leaderboard.md`
- `reports/overnight_performance_analysis.md`
- `reports/overnight_failure_taxonomy.md`
- `reports/overnight_benchmark_report.md`

Scope:

- This is an audit of bottlenecks exposed by the overnight benchmark campaign.
- No production code was changed for this report.
- Score gain estimates are directional expected average benchmark-readiness gains on a 0-100 scale after re-benchmarking. They are not measured fixes.
- Effort is estimated implementation effort on a 1-10 scale, where 1 is small and 10 is multi-phase.
- ROI = estimated score gain / effort.

## Summary

The strongest product evidence is that Atlas measured 17 of 18 requested repositories and produced useful graph/context metrics for large repositories such as Home Assistant, VS Code, Django, Next.js, and React.

The biggest readiness gaps are not token economics. Token compression looked strong in the benchmark. The blockers are trust and repeatability:

- quality scoring is still proxy-based rather than human-validated;
- Build Plan quality is the weakest uniform score;
- graph health/unresolved details are not surfaced cleanly in the benchmark payload;
- Atlas self timed out;
- weak/no-edge graphs can still receive high downstream scores.

## ROI Ranking

| Rank | Bottleneck | Severity | Frequency | Affected repositories | Root cause | Est. score gain | Effort | ROI |
|---:|---|---|---:|---|---|---:|---:|---:|
| 1 | Proxy quality scoring, no human-reviewed correctness gate | Critical | 17/17 measured | All measured repositories | Overnight scores reward successful API shape and coarse evidence presence. They do not verify whether answers are correct, specific, or actionable. This is why many repos cluster at 85.00. | 6.0 | 2.0 | 3.00 |
| 2 | Build Plan output is the lowest repeated capability score | High | 17/17 measured | All measured repositories | Every measured repo had `build_score=60`. The scoring implies Build Plan lacks enough repository-specific target files, verification detail, or evidence-backed implementation boundaries. | 5.0 | 2.5 | 2.00 |
| 3 | Graph health and unresolved-import classification are missing from benchmark metrics | High | 17/17 measured | All measured repositories | `graph_health_label`, `unresolved_internal`, and `unresolved_external` were null in every measured raw result, even when unresolved imports were high. This weakens trust and makes partial graphs hard to interpret. | 3.5 | 2.0 | 1.75 |
| 4 | Atlas self-scan timed out | Critical | 1/18 attempted | Atlas self | The benchmark attempted the local workspace and timed out after 2400 seconds. Even with external repos excluded, current self-scan scope still includes too much dirty/generated/runtime material or triggers pathological scan cost. | 4.5 | 3.0 | 1.50 |
| 5 | Impact validation used auto-selected graph targets, not user-semantic tasks | High | 17/17 measured | All measured repositories | The benchmark selected top graph targets such as `homeassistant/const.py` and `django/conf/__init__.py`. That proves graph-target impact works, but not natural questions like "remove websocket support" or "add rate limiting". | 4.0 | 3.0 | 1.33 |
| 6 | Weak/no-edge graphs are over-scored downstream | High | 3/17 measured | QuixBugs, LangChain, Qdrant | These repos were marked with graph failures because they had zero dependency edges or effectively unusable graphs, yet impact/investigation/build still returned successful-looking proxy scores. The benchmark and product need stronger degraded-graph gating. | 3.0 | 2.5 | 1.20 |
| 7 | High unresolved import ratios reduce graph trust | High | 16/17 measured with ratio >= 0.40; 9/17 with >= 1000 unresolved imports | Home Assistant, VS Code, LangChain, OpenBB, Next.js, React, NestJS, Pydantic, Django, plus smaller high-ratio repos | The resolver leaves many imports unresolved and the benchmark cannot distinguish external dependencies, stdlib, optional imports, and true missing internal edges. VS Code had 67,338 unresolved imports; Home Assistant had 59,473. | 5.0 | 6.0 | 0.83 |
| 8 | Monorepo/package-layout dependency resolution gaps | High | 2/17 clear, 4/17 likely | LangChain, OpenBB; possibly Next.js and VS Code in deeper checks | LangChain produced 1,689 modules but 0 edges. OpenBB produced 1,062 modules but only 47 edges. This points to package layout, namespace, generated package, or JS/Python mixed-layout resolution gaps. | 3.0 | 5.0 | 0.60 |
| 9 | Large-repository scan performance is uneven | Medium | 6/17 scans > 20s; 1/17 > 120s | Home Assistant, Next.js, VS Code, LangChain, OpenBB, Django | Home Assistant took 494.804s and repository map took 13.768s. The scan can handle large repos, but production readiness needs bounded latency, progress, cancellation, cache reuse, and warm-run evidence. | 2.5 | 5.0 | 0.50 |
| 10 | Unsupported or weak non-Python/non-JS language coverage | Medium | 1/17 observed, high future risk | Qdrant | Qdrant is Rust-heavy and produced only 4 modules and 0 edges despite 1,607 counted code files. Atlas should either support Rust graph extraction or clearly label the repository as unsupported/partial. | 1.5 | 8.0 | 0.19 |

## Evidence Notes

### Uniform score clustering

The leaderboard shows most measured repositories at exactly 85.00 overall:

- understanding: 90
- impact: 100
- investigation: 90
- build: 60

This clustering is a measurement trust issue. Production readiness needs a benchmark that can distinguish "API returned" from "developer can rely on the result".

### Graph failures

Recorded failure taxonomy:

- `graph_failure`: QuixBugs, LangChain, Qdrant
- `performance_failure`: Atlas self
- `semantic_routing_failure`: 0 recorded
- `impact_failure`: 0 recorded
- `investigation_failure`: 0 recorded
- `build_failure`: 0 recorded

The absence of semantic failures should not be over-interpreted because the benchmark did not run natural semantic prompts per repository.

### High unresolved import examples

| Repository | Unresolved imports | Unresolved ratio |
|---|---:|---:|
| VS Code | 67,338 | 0.8358 |
| Home Assistant | 59,473 | 0.6228 |
| LangChain | 10,126 | 1.0000 |
| OpenBB | 6,889 | 0.9932 |
| Next.js | 4,103 | 0.4502 |
| React | 3,643 | 0.5389 |
| NestJS | 1,813 | 0.4397 |
| Pydantic | 1,538 | 0.8233 |
| Django | 1,377 | 0.3208 |

The important problem is not just volume. The benchmark payload did not include internal/external/stdlib/dynamic categorization, so a developer cannot tell whether the graph is incomplete or merely seeing external packages.

### Performance examples

| Repository | Scan seconds | Map seconds | Files | Modules | Edges |
|---|---:|---:|---:|---:|---:|
| Home Assistant | 494.804 | 13.768 | 25,893 | 9,709 | 36,013 |
| Next.js | 42.851 | 0.090 | 27,487 | 3,114 | 5,010 |
| VS Code | 33.238 | 0.791 | 14,892 | 7,563 | 13,228 |
| LangChain | 26.603 | 0.022 | 2,779 | 1,689 | 0 |
| OpenBB | 26.462 | 0.017 | 2,086 | 1,062 | 47 |
| Django | 21.467 | 0.013 | 6,870 | 929 | 2,915 |

Home Assistant is the main observed performance blocker. Atlas self is more severe because it did not complete.

## Recommended Fix Order

1. Add human-reviewable evidence capture and stricter quality scoring.
2. Improve Build Plan specificity and evidence-backed verification sections.
3. Surface graph health and unresolved import buckets in every benchmark/product result.
4. Create a safe Atlas self benchmark scope that completes reliably.
5. Add semantic task probes per repository rather than only auto-selected graph targets.
6. Gate downstream scores and UI confidence when graph edges are missing.
7. Improve unresolved import resolution/classification for high-ratio repositories.
8. Address monorepo/package-layout edge resolution, starting with LangChain and OpenBB.
9. Add large-repo performance budgets, warm-cache reporting, and progress/cancellation evidence.
10. Decide whether Rust and other unsupported languages are explicitly out of scope or need first-class graph support.

## Production-Readiness Interpretation

Atlas is strong at producing compact repository context and fast post-scan API responses on many repositories. The next production-readiness step is not more marketing evidence. It is trust hardening:

- prove result correctness with human review;
- refuse or downgrade confidence on partial graphs;
- make graph health explainable;
- make benchmark runs reproducible;
- ensure Atlas can dogfood its own repository without timing out.
