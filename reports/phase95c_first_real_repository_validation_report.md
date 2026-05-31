# Phase 95C - First Real Repository Validation Report

**Status:** Implemented and executed as an honest pilot-only run.
**Date:** 2026-05-31
**External-alpha verdict:** `HOLD`

## 1. Scope

Phase 95C executes the Phase 95B corpus protocol through the Phase 95A read-only harness.

This pass adds corpus orchestration, deterministic review exports, precision and usefulness workflow support, and aggregate readiness reporting. It does not modify detectors, finding schemas, benchmark logic, promotion logic, or target repositories.

The locally available repositories do not satisfy the approved 24-repository primary-corpus gate. The first execution therefore uses two transparent `pilot` entries with `primary_eligible: false`. It validates the harness workflow without claiming external-alpha readiness.

## 2. Frozen Candidate

| Field | Value |
| --- | --- |
| Builder Core commit | `e3b55a81c408ed4481ddf38eaed7b049079b6a0f` |
| `CROSS_FILE_ENABLED` | `true` |
| `CROSS_FILE_CONSUMPTION_ENABLED` | `false` |
| `INTERPROC_PROMOTION_ENABLED` | `true` |
| Grounded verdict kinds | `semantic`, `data_flow`, `value_flow`, `security` |

## 3. Implemented Workflow

The Phase 95C layer now supports:

- Manifest tracks: `primary`, `pilot`, and `stress`
- Explicit `primary_eligible` and eligibility notes
- Frozen repository commit checks through the existing read-only scan path
- Deterministic grounded-finding sampling from a preregistered seed
- Blinded Reviewer A, Reviewer B, and adjudication packets
- Deterministic negative-file samples
- Historical-bug review worksheets
- Conservative precision scoring with advisory findings separated
- Repository usefulness scoring
- Aggregate readiness gates with `PASS`, `HOLD`, and `FAIL`
- Deterministic JSON and Markdown exports outside target repositories

## 4. Pilot Corpus

| Repository | Pinned commit | Track | Python files | Python LOC | Outcome | Duration | Target writes |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| `openai-plugins-public-pilot` | `fef63ecfb600812a4dac8ef7c37ff79c85999948` | `pilot` | 101 | 32,776 | `success` | 12.749 s | 0 |
| `openai-skills-public-pilot` | `a8924c2a35cfa290458852c4fad17c9133054c2e` | `pilot` | 34 | 9,829 | `success` | 3.738 s | 0 |

Both checkouts were clean, public, already present locally, and pinned before scanning. They are not counted as primary-corpus repositories because repository-wide license scope was not established locally.

## 5. Finding Inventory

| Metric | Count |
| --- | ---: |
| Total exported findings | 720 |
| Grounded verdict-eligible review candidates | 202 |
| Advisory findings reported separately | 518 |
| Grounded `security` findings | 26 |
| Grounded `value_flow` findings | 176 |
| Advisory `pattern` findings | 518 |

No human review labels have been recorded yet. Strict precision, usefulness, and review-lead rates are therefore intentionally reported as unavailable rather than inferred.

## 6. Readiness Gate Result

The aggregate report correctly returns `HOLD`.

Passing operational gates:

- Unsafe outcomes: `0`
- Crash-free completion: `2/2`
- Modified tracked target files: `0`
- Parse errors: `0`
- Adjudication backlog: `0`

Open evidence gates:

- Primary repositories: `0/24`
- Historical bug cases: `0` across `0` repositories
- Human review: `202` grounded findings remain unlabeled
- Strict precision: unavailable until review completes
- Usefulness scoring: unavailable until review completes

## 7. Honest Local Exclusions

The local inventory did not contain an approved 24-repository corpus.

| Local checkout | Exclusion reason |
| --- | --- |
| `C:\Repos\QuixBugs` | Existing benchmark; prohibited as real-repository evidence |
| `C:\J.A.R.V.I.S\local_jarvis` | JARVIS repository; not independent and currently contains unrelated WIP |
| `data\external_benchmarks\BugsInPy_probe` | Benchmark probe; prohibited as real-repository evidence |
| Temporary `acme-api` checkout | Synthetic temporary repository with only three Python files |
| User-home Git checkout | Not a software repository |
| Memory repository | No eligible Python software surface |

## 8. Artifacts

The execution command was:

```powershell
py -3 -m builder_core.real_repo_validation.cli run `
  --manifest reports\phase95c_first_pilot_manifest.json `
  --output reports\phase95c_first_run
```

The local artifact directory contains the normalized manifest, full finding export, deterministic review sample, blinded reviewer packets, negative-file sample, historical worksheet, score template, metrics, and aggregate report.

The raw artifact directory remains local-only because reviewer packets include bounded source windows copied from the scanned public repositories. This report records the stable aggregate result without committing those generated source excerpts.

## 9. Verification

```text
py -3 -m pytest builder_core\tests\test_phase95a_real_repo_validation.py builder_core\tests\test_phase95c_real_repo_corpus.py -q -p no:cacheprovider
18 passed in 2.02s

py -3 -m pytest builder_core\tests\ -q -p no:cacheprovider
201 passed in 8.40s

py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
12 true positives, 0 false positives, precision 1.0000, recall 0.3000

py -3 scripts\run_phase84_holdout_benchmark.py
2 true positives, 0 false positives, precision 1.0000, recall 0.1667
```

## 10. Safety Confirmation

- No detector changed.
- No finding schema changed.
- No benchmark changed.
- No promotion logic changed.
- No target repository file changed.
- No target code executed.
- No dependency was installed.
- No external-alpha claim is made from the pilot run.

## 11. Next Execution Step

Assemble and preregister the approved 24-repository public corpus, resolve license scope before counting a repository as primary, register 20-30 historical cases across at least 10 repositories, then run the same frozen workflow and complete blinded human review.
