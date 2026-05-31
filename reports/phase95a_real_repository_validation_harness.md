# Phase 95A - Real Repository Validation Harness

**Status:** Implemented and verified
**Date:** 2026-05-31
**Scope:** Infrastructure only. Builder Core intelligence remains frozen.

## Summary

Phase 95A adds a standalone, read-only validation harness around the existing unified Builder Core engine. It prepares the infrastructure needed to run the Phase 95 real-repository program without changing detectors, benchmarks, finding schemas, or promotion logic.

The harness is intentionally separate from the analysis engine:

```text
builder_core.real_repo_validation
```

The compatibility import:

```text
builder_core.bug_intelligence.validation_harness
```

delegates to that separate package so validation infrastructure remains outside detector ownership.

## Implemented Requirements

### 1. Repository Manifest Format

Added:

```text
builder_core/real_repo_validation/manifest.example.json
```

The JSON manifest preregisters:

- Program ID
- Frozen Builder Core commit
- Frozen feature flags
- Repository ID
- Local checkout path
- Pinned repository commit
- License
- Size band
- Language profile
- Project shape
- Selection rationale
- Optional Python LOC and file counts
- Optional historical bug cases with parent commit, fix commit, description, and fixed files

A run refuses to proceed when the current Builder Core commit or flags differ from the preregistered candidate.

### 2. Evaluation Runner

The runner:

- Validates the manifest
- Sorts repositories by stable ID
- Confirms each checkout matches its pinned Git commit
- Captures read-only before/after safety snapshots
- Calls the existing `engine.analyze_repository()` unchanged
- Isolates repository failures
- Classifies each run as `success`, `degraded`, `failed`, `unsafe`, or `unavailable`
- Refuses artifact directories inside target repositories

### 3. Finding Export Format

`findings.json` contains deterministic records with:

- Existing unified finding payload
- Stable cross-repository `record_id`
- Repository ID
- Verdict eligibility
- Size band
- Language profile
- Project shape
- Optional Python size metadata
- Sampling probability
- Bounded source window

Real-repository review includes all grounded product kinds:

```text
semantic
data_flow
value_flow
security
```

This differs deliberately from the algorithm-benchmark verdict, which excludes security only because security is out of band for that paired algorithm corpus.

### 4. Review Workflow Support

The harness exports:

```text
reviews.json
repository_scores.json
```

Each finding review has:

- `reviewer_a`
- `reviewer_b`
- `adjudication`

Matching independent labels resolve automatically. Disagreement remains pending until adjudication. Repository scoring records usefulness, willingness to use again, and a short reason.

### 5. Precision Measurement Support

Metrics include:

- Conservative strict precision
- Weighted strict precision for sampled review sets
- Review-lead rate
- Misleading rate
- Undecidable rate
- Unreviewed count
- Adjudication-needed count
- Breakdowns by rule, kind, severity, size band, and language profile
- Advisory findings reported separately from verdict-eligible findings

### 6. Usefulness Scoring Support

Metrics include:

- Per-finding usefulness distribution
- Mean finding usefulness
- Repositories with a score-3-or-higher finding
- Median repository usefulness
- Would-use-again count and rate

### 7. Report Generation

The harness writes:

```text
manifest.normalized.json
program.json
findings.json
reviews.json
repository_scores.json
findings.reviewed.json
metrics.json
report.md
```

After human review, regenerate metrics and the report with:

```powershell
py -3 -m builder_core.real_repo_validation.cli report --run-dir C:\Validation\phase95
```

### 8. Deterministic Outputs

Outputs use:

- Stable repository ordering
- Stable finding ordering
- Stable cross-repository record IDs
- Sorted JSON keys
- Normalized manifest export
- Newline-terminated JSON
- Deterministic report rendering from stored artifacts

Operational durations remain measured observations and may differ between runs.

## Usage

Run a preregistered local corpus:

```powershell
py -3 -m builder_core.real_repo_validation.cli run `
  --manifest C:\Validation\phase95_manifest.json `
  --output C:\Validation\phase95_run
```

The output directory must remain outside every target repository.

## Files Added

```text
builder_core/bug_intelligence/validation_harness.py
builder_core/real_repo_validation/__init__.py
builder_core/real_repo_validation/cli.py
builder_core/real_repo_validation/harness.py
builder_core/real_repo_validation/manifest.example.json
builder_core/tests/test_phase95a_real_repo_validation.py
reports/phase95_real_repository_validation_design.md
reports/phase95a_real_repository_validation_harness.md
```

## Tests

Focused harness suite:

```powershell
py -3 -m pytest builder_core\tests\test_phase95a_real_repo_validation.py -q -p no:cacheprovider
```

Result:

```text
11 passed in 1.75s
```

Full Builder Core regression suite:

```powershell
py -3 -m pytest builder_core\tests\ -q -p no:cacheprovider
```

Result:

```text
194 passed in 8.44s
```

QuixBugs unified regression:

```powershell
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

Result:

```text
buggy files analyzed: 40
correct files analyzed: 40
true positives: 12
false positives: 0
precision: 1.0000
recall: 0.3000
```

Unified holdout regression:

```powershell
py -3 scripts\run_phase84_holdout_benchmark.py
```

Result:

```text
cases analyzed: 12
true positives: 2
false positives: 0
false negatives: 10
true negatives: 12
precision: 1.0000
recall: 0.1667
accuracy: 0.5833
```

## Safety Confirmation

Phase 95A does not modify:

- Detectors
- Benchmarks
- Finding schema
- Promotion logic
- Target repository source files
- Voice, browser, trading, website, or router code

The harness does not:

- Execute target code
- Install target dependencies
- Run target tests
- Clone repositories
- Write inside target repositories

The real 24-repository Phase 95 corpus run is intentionally not part of Phase 95A. This commit supplies the frozen, deterministic infrastructure for that separate validation execution.
