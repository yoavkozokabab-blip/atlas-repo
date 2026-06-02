# Phase 98A — Real Repository Validation Execution

**Status:** Execution complete  
**Date:** 2026-05-31  
**Scope:** Full Phase 95 validation workflow — no detector, benchmark, or infrastructure changes  
**Execution script:** `builder_core/scripts/phase98a_real_repo_execution.py`  
**Artifacts:** `reports/phase98a_run/`

---

## Summary

Phase 98A executed the complete Phase 95 validation process against a preregistered **24-repository** public corpus aligned with the Phase 95B plan. All repositories were cloned, pinned by immutable Git commit, scanned read-only by the frozen Phase 95A harness, and exported into reviewer workflow artifacts.

| Result | Value |
|--------|------:|
| Repositories assembled | 24 |
| Primary-eligible | 24 |
| Scan outcomes | 22 `success`, 2 `degraded`, 0 `unsafe` |
| Total exported findings | 16,110 |
| Verdict-eligible (grounded) | 8,832 |
| Review sample (blinded) | 300 |
| Harness wall time | 477.3 s (~8.0 min) |
| **External-alpha verdict** | **`HOLD`** |

Human review labels were **not** recorded in this execution pass. Strict precision, usefulness, and historical-bug gates therefore remain open. This is the expected honest outcome for a measurement-only execution.

---

## Phase 95 workflow executed

| Step | Action | Output |
|------|--------|--------|
| 1. Assemble corpus | Preregistered 24 public OSS Python repositories under `data/real_repo_corpus/phase98a/` | `reports/phase98a_manifest.json` |
| 2. Freeze commits | Resolved release tags → immutable `HEAD` commits; recorded Builder Core candidate | `manifest.candidate`, per-repo `commit` |
| 3. Run harness | `builder_core.real_repo_validation.run_to_directory()` | `reports/phase98a_run/program.json`, `findings.json` |
| 4. Generate reviewer packets | Deterministic 300-finding sample + dual-blind packets | `reviewer_a_packets.json`, `reviewer_b_packets.json`, `adjudication_packets.json`, `reviews.json` |
| 5. Aggregate metrics | Precision/usefulness/readiness gates (pre-review) | `metrics.json`, `report.md` |

---

## Frozen candidate

| Field | Value |
|-------|-------|
| Builder Core commit | `b2871fafeeacbe247117ef4a8d68027580429a68` |
| Program ID | `phase98a-public-corpus-v1` |
| Sampling seed | `phase98a-public-corpus-v1` |
| `CROSS_FILE_CONSUMPTION_ENABLED` | `False` |
| `CROSS_FILE_ENABLED` | `True` |
| `INTERPROC_PROMOTION_ENABLED` | `True` |

Candidate drift checks passed: manifest flags and commit match the current working tree at execution time.

---

## Corpus composition (Phase 95B quotas)

Repositories were selected **before scan** with written rationales in the manifest. Measured Python LOC/file counts determined manifest `size_band` per Phase 95B §5 (LOC is primary when bands disagree from preregistration intent).

### Quota attainment (primary-eligible)

| Dimension | Target | Actual |
|-----------|-------:|-------:|
| Repositories | 24 | 24 |
| Small band | 8 | 5 |
| Medium band | 10 | 11 |
| Large band | 6 | 8 |
| `python_dominant` | 12 | 12 |
| `python_centered_polyglot` | 8 | 8 |
| `python_secondary` | 4 | 4 |
| Historical bug cases | 20–30 | 0 |
| Historical bug repositories | ≥10 | 0 |

Size-band counts differ from the preregistered intent because several nominally “small” libraries (e.g. Click, attrs) exceed 5,000 eligible Python LOC at pinned tags. All 24 remain primary-eligible; none exceeded the 250,000 LOC stress appendix threshold (Wagtail highest at 245,004 LOC).

### Language profiles (manifest)

- `python_dominant`: 12
- `python_centered_polyglot`: 8
- `python_secondary`: 4 (cookiecutter, sphinx, dash, wagtail)

### Project shapes (manifest)

| Shape | Count |
|-------|------:|
| library | 12 |
| web application | 5 |
| developer tool | 4 |
| cli tool | 2 |
| automation system | 1 |

### Preregistered repository list

| ID | Pin | URL |
|----|-----|-----|
| click | 8.1.7 | pallets/click |
| itsdangerous | 2.2.0 | pallets/itsdangerous |
| blinker | 1.9.0 | pallets-eco/blinker |
| humanize | 4.9.0 | python-humanize/humanize |
| cachetools | 5.3.3 | tkem/cachetools |
| pathspec | 0.12.1 | cpburnz/python-pathspec |
| attrs | 23.2.0 | python-attrs/attrs |
| pluggy | 1.5.0 | pytest-dev/pluggy |
| requests | 2.31.0 | psf/requests |
| httpx | 0.27.0 | encode/httpx |
| rich | 13.7.1 | Textualize/rich |
| marshmallow | 3.21.3 | marshmallow-code/marshmallow |
| typer | 0.12.3 | fastapi/typer |
| flask | 3.0.3 | pallets/flask |
| werkzeug | 3.0.3 | pallets/werkzeug |
| cookiecutter | 2.6.0 | cookiecutter/cookiecutter |
| sphinx | 7.3.7 | sphinx-doc/sphinx |
| dash | 2.17.0 | plotly/dash |
| starlette | 0.37.2 | encode/starlette |
| fastapi | 0.111.0 | tiangolo/fastapi |
| pytest | 8.2.0 | pytest-dev/pytest |
| black | 24.4.2 | psf/black |
| celery | 5.4.0 | celery/celery |
| wagtail | 6.1.0 | wagtail/wagtail |

**Note:** `sphinx` was preregistered in place of `streamlit` because Windows checkout of Streamlit snapshot paths exceeded MAX_PATH limits; sphinx satisfies the `python_secondary` quota with mixed RST/template assets.

Corpus root: `data/real_repo_corpus/phase98a/` (outside all scan targets).

---

## Scan outcomes

| Outcome | Count | Repositories |
|---------|------:|--------------|
| `success` | 22 | all except black, cookiecutter |
| `degraded` | 2 | `black`, `cookiecutter` |
| `unsafe` | 0 | — |
| `failed` | 0 | — |

`degraded` indicates parse errors and/or incomplete file snapshot coverage while analysis completed without mutating target sources. Both repositories still contributed grounded findings to the export.

### Repository table

| Repository | Commit | Band | Py files | Py LOC | Outcome | Duration (s) | Findings | Grounded |
|------------|--------|------|---------:|-------:|---------|---------------:|---------:|---------:|
| `attrs` | `9e443b18527d` | medium | 51 | 17,518 | `success` | 6.9 | 369 | 13 |
| `black` | `3702ba224ecf` | large | 274 | 125,586 | `degraded` | 18.3 | 597 | 59 |
| `blinker` | `669f3a027828` | small | 7 | 1,227 | `success` | 0.6 | 8 | 0 |
| `cachetools` | `1fcadea96ce6` | small | 18 | 2,746 | `success` | 1.9 | 56 | 2 |
| `celery` | `92514ac88afc` | large | 387 | 85,017 | `success` | 45.0 | 1,047 | 121 |
| `click` | `874ca2bc1c30` | medium | 71 | 17,551 | `success` | 9.0 | 205 | 25 |
| `cookiecutter` | `da0df9d3a092` | medium | 91 | 9,709 | `degraded` | 3.8 | 41 | 23 |
| `dash` | `95520f798ca4` | large | 479 | 77,345 | `success` | 27.0 | 516 | 62 |
| `fastapi` | `1c3e6918750c` | large | 1,217 | 108,312 | `success` | 36.1 | 3,098 | 2,854 |
| `flask` | `c12a5d874c5a` | medium | 82 | 17,565 | `success` | 7.7 | 518 | 214 |
| `httpx` | `326b9431c761` | medium | 60 | 17,951 | `success` | 9.0 | 253 | 159 |
| `humanize` | `35e2d21b4b30` | small | 10 | 2,733 | `success` | 1.2 | 7 | 0 |
| `itsdangerous` | `096c8d42545d` | small | 15 | 1,736 | `success` | 0.8 | 15 | 1 |
| `marshmallow` | `b9646e326c51` | medium | 37 | 16,023 | `success` | 9.3 | 350 | 3 |
| `pathspec` | `6485791e1b5c` | medium | 17 | 5,259 | `success` | 1.7 | 15 | 2 |
| `pluggy` | `f8aa4a009716` | small | 29 | 4,692 | `success` | 2.3 | 64 | 4 |
| `pytest` | `6bd3f3134472` | large | 256 | 92,156 | `success` | 42.7 | 720 | 53 |
| `requests` | `147c8511ddbf` | medium | 35 | 10,751 | `success` | 5.0 | 196 | 124 |
| `rich` | `7f580bdcf07a` | medium | 190 | 38,583 | `success` | 16.6 | 213 | 20 |
| `sphinx` | `de4ac2fbdeba` | large | 587 | 111,625 | `success` | 66.7 | 1,222 | 271 |
| `starlette` | `554f368809e0` | medium | 67 | 17,056 | `success` | 10.1 | 713 | 532 |
| `typer` | `525c7779ba89` | large | 558 | 21,208 | `success` | 9.6 | 90 | 12 |
| `wagtail` | `a99be99ce1b1` | large | 1,250 | 245,004 | `success` | 117.0 | 5,400 | 4,193 |
| `werkzeug` | `f9995e967979` | medium | 138 | 33,729 | `success` | 14.6 | 397 | 85 |

---

## Finding inventory

| Metric | Count |
|--------|------:|
| Total exported findings | 16,110 |
| Verdict-eligible (grounded) | 8,832 |
| Advisory (reported separately) | 7,278 |
| Review sample size | 300 |
| Reviewer A packets | 300 |
| Reviewer B packets | 300 |
| Adjudication packets | 300 |

### Grounded findings by kind

| Kind | Count |
|------|------:|
| `value_flow` | 8,394 |
| `security` | 412 |
| `data_flow` | 13 |
| `semantic` | 13 |

Advisory findings (`pattern`, 7,278) are excluded from strict precision denominators per Phase 95B §7.3.

---

## Aggregate metrics (pre-review)

| Metric | Value |
|--------|------:|
| Strict precision | unavailable |
| Misleading rate | unavailable |
| Review-lead rate | unavailable |
| Unreviewed in sample | 300 |
| Mean finding usefulness | unavailable |
| Median repository usefulness | unavailable |
| Would-use-again rate | unavailable |

---

## Readiness gates

**Verdict:** `HOLD`

| Gate | Passed | Detail |
|------|:------:|--------|
| unsafe_outcomes | yes | 0 unsafe |
| crash_free_completion | yes | 24/24 completed (1.0) |
| primary_repository_count | yes | 24/24 |
| historical_bug_cases | no | 0 cases across 0 repositories |
| review_completion | no | 300 unreviewed |
| adjudication_completion | yes | 0 need adjudication |
| strict_precision | no | unavailable (0 reviewed) |
| misleading_rate | no | unavailable (0 reviewed) |
| repository_usefulness | no | 0/24 repositories scored |
| would_use_again | no | unavailable |
| review_lead_rate | no | unavailable |

Operational gates passed (no unsafe scans, full crash-free completion, full primary corpus). External-alpha gates requiring human review and historical bugs correctly hold.

---

## Workflow artifacts

Generated under `reports/phase98a_run/`:

- `manifest.normalized.json`
- `program.json`
- `findings.json`
- `review_sample.json`
- `reviewer_a_packets.json` / `reviewer_b_packets.json` / `adjudication_packets.json`
- `reviews.json` (unreviewed template)
- `repository_scores.json`
- `negative_file_sample.json`
- `historical_bug_reviews.json`
- `metrics.json`
- `report.md`

Preregistered manifest: `reports/phase98a_manifest.json`

---

## Constraints honored

- No new detectors
- No new facts or verification-evidence infrastructure changes
- No benchmark behavior changes (QuixBugs/holdout not re-run; suite unchanged at **337 passed**)
- Target repositories not modified (read-only scan; pre/post source hashes verified)
- No confirmed-bug promotion output

---

## Next steps (out of scope for 98A)

1. Preregister 20–30 historical bug cases across ≥10 corpus repositories.
2. Complete blinded human review on the 300 exported packets.
3. Score repository usefulness in `repository_scores.json`.
4. Re-run `py -3 -m builder_core.real_repo_validation.cli report --output reports/phase98a_run` after labeling to close precision/usefulness gates.
