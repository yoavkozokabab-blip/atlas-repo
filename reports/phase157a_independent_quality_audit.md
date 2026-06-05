# Phase 157A - Independent Quality Audit

Date: 2026-06-05

Scope: external-reviewer quality audit only. Atlas was treated as feature complete. No Atlas source code, benchmark logic, detectors, routing, or product behavior were modified.

## Final Verdict

Can Atlas outputs be trusted?

**PARTIALLY**

Atlas can be trusted as a first-pass repository orientation aid when a developer reviews every claim. It cannot yet be trusted as an authoritative planning, root-cause, or impact system. The dominant failure is not wild hallucination on every result; it is thin grounding plus confidence presentation that can make weak evidence sound stronger than it is.

## Sampling

- 50 Build Plans
- 50 Investigations
- 50 Impact Analyses
- Repositories: Home Assistant, Django, FastAPI, VS Code, Airflow, Celery, TypeORM, Kubernetes
- Distribution: Home Assistant and Django received 7 samples per workflow; the other six repositories received 6 samples per workflow.
- Classification scale: CORRECT, MOSTLY_CORRECT, PARTIALLY_CORRECT, MISLEADING, WRONG.

## Accuracy Summary

| Workflow | Samples | CORRECT | MOSTLY_CORRECT | PARTIALLY_CORRECT | MISLEADING | WRONG | Actionable % | Usable with review % | Unsafe % | Trust score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build | 50 | 0 | 0 | 46 | 4 | 0 | 0.0 | 92.0 | 8.0 | 42.2 |
| investigation | 50 | 0 | 0 | 44 | 6 | 0 | 0.0 | 88.0 | 12.0 | 40.8 |
| impact | 50 | 12 | 3 | 28 | 2 | 5 | 30.0 | 86.0 | 14.0 | 54.4 |
| ALL | 150 | 12 | 3 | 118 | 12 | 5 | 10.0 | 88.7 | 11.3 | 45.8 |

Interpretation:

- High-confidence actionable quality, defined as CORRECT or MOSTLY_CORRECT, was only **10.0%** overall.
- Usable-with-review quality, defined as CORRECT through PARTIALLY_CORRECT, was **88.7%** overall.
- Unsafe output, defined as MISLEADING or WRONG, was **11.3%** overall.
- Weighted user trust score: **45.8/100**.

## Repository Scan Context

| Repo | Scan seconds | Files | Modules | Edges | Health | Unresolved imports | Unresolved ratio |
|---|---:|---:|---:|---:|---|---:|---:|
| home_assistant | 462.382 | 25893 | 9709 | 36013 | partial | 59473 | 0.6228 |
| django | 30.755 | 6870 | 929 | 2915 | watch | 1377 | 0.3208 |
| fastapi | 7.656 | 2753 | 73 | 159 | watch | 560 | 0.7789 |
| vscode | 112.287 | 14892 | 7563 | 13228 | partial | 67338 | 0.8358 |
| airflow | 128.352 | 12341 | 4332 | 835 | watch | 31640 | 0.9743 |
| celery | 7.723 | 810 | 215 | 575 | healthy | 1035 | 0.6429 |
| typeorm | 20.291 | 3738 | 569 | 2735 | watch | 288 | 0.0953 |
| kubernetes | 17.359 | 24860 | 3 | 0 | healthy | 14 | 1.0 |

Kubernetes is the clearest graph-quality red flag: Atlas scanned 24,860 files but produced only 3 modules while graph health was reported as healthy. That mismatch directly caused five WRONG Impact results.

## Main Findings

1. Build Plans are directionally useful but rarely evidence-complete. All 50 Build Plans were either PARTIALLY_CORRECT or MISLEADING; none reached CORRECT/MOSTLY_CORRECT under the reviewer rubric.
2. Investigations are the least trustworthy workflow for root cause. They often choose plausible subsystems, but root-cause lines can name syntactic tokens or irrelevant files.
3. Impact is the strongest workflow when the repository is a supported Python/TypeScript graph. FastAPI, Airflow, Celery, and TypeORM produced the best Impact samples.
4. Go/Kubernetes support is not demo-safe for Impact. Existing Go target files returned target-not-found mock responses with `ok=true`.
5. Curated concept selection can leak unrelated domain knowledge. Multiple Build Plans for Home Assistant, Django, and TypeORM mapped ordinary engineering asks to EMA / Trading Systems.
6. Confidence and success semantics are sometimes too optimistic. Several weak or target-not-found outputs returned `ok=true`, medium confidence, or high risk labels without enough evidence.

## Trust Tables

| Repo | Workflow | Samples | CORRECT | MOSTLY_CORRECT | PARTIALLY_CORRECT | MISLEADING | WRONG | Trust score |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| home_assistant | build | 7 | 0 | 0 | 5 | 2 | 0 | 35.0 |
| home_assistant | investigation | 7 | 0 | 0 | 3 | 4 | 0 | 25.0 |
| home_assistant | impact | 7 | 0 | 0 | 6 | 1 | 0 | 40.0 |
| django | build | 7 | 0 | 0 | 6 | 1 | 0 | 40.0 |
| django | investigation | 7 | 0 | 0 | 7 | 0 | 0 | 45.0 |
| django | impact | 7 | 0 | 0 | 6 | 1 | 0 | 40.0 |
| fastapi | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| fastapi | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| fastapi | impact | 6 | 4 | 1 | 1 | 0 | 0 | 87.5 |
| vscode | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| vscode | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| vscode | impact | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| airflow | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| airflow | investigation | 6 | 0 | 0 | 4 | 2 | 0 | 33.3 |
| airflow | impact | 6 | 4 | 1 | 1 | 0 | 0 | 87.5 |
| celery | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| celery | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| celery | impact | 6 | 2 | 1 | 3 | 0 | 0 | 69.2 |
| typeorm | build | 6 | 0 | 0 | 5 | 1 | 0 | 39.2 |
| typeorm | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| typeorm | impact | 6 | 2 | 0 | 4 | 0 | 0 | 63.3 |
| kubernetes | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| kubernetes | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| kubernetes | impact | 6 | 0 | 0 | 1 | 0 | 5 | 7.5 |

## Failure Taxonomy

| Failure category | Count | Meaning |
|---|---:|---|
| thin_grounding | 118 | Thin repo-specific grounding |
| repo_grounded | 12 | Strong repo-grounded output |
| irrelevant_target_pollution | 7 | Irrelevant/fallback/config pollution |
| nonsensical_root_cause | 5 | Weak syntax/import token treated as root cause |
| target_resolution_failure | 5 | Existing target not resolved |
| repo_grounded_with_limits | 3 | Repo-grounded but incomplete |


## Top Hallucination Sources

1. EMA / Trading Systems concept leakage into unrelated Build Plans.
2. Mock impact fallback reporting `ok=true` on unresolved Kubernetes targets.
3. Root-cause extraction that promotes imports or syntax helpers as causes.
4. Production-scope pollution from scripts/docs/config-style files.
5. Graph-health mismatch, especially for unsupported language coverage.

## Final Assessment

Atlas should be positioned as a context compressor and repository navigation aid, not as a trusted defect confirmer or authoritative architecture analyst. A developer can use it to decide where to look next. They should not accept its Build Plans, Investigation root causes, or Impact outputs without checking the named files and evidence.
