# Phase 95D — Human Review Support Tooling

Date: 2026-05-31

Scope: Review workflow tooling only. No detector, engine, benchmark, or target-repository changes.

## Goal

Make the Phase 95C blinded human review process easy, deterministic, and hard to mess up.

## What Was Inspected

| Artifact | Role |
| --- | --- |
| `builder_core/real_repo_validation/harness.py` | Phase 95A/95C scan + review schema (`reviews.json`, packets, precision) |
| `builder_core/real_repo_validation/cli.py` | `run` / `report` for validation artifacts |
| `reports/phase95c_first_run/` | Pilot artifact directory (202 grounded findings) |
| `reports/phase95c_first_real_repository_validation_report.md` | Phase 95C execution summary |
| `reviewer_a_packets.json` | Blinded packet list (metadata + bounded source window) |
| `reviews.json` | Dual-reviewer + adjudication template |

Existing harness labels (`confirmed_actionable`, `misleading`, …) remain the source of truth for aggregate reporting. Phase 95D adds reviewer-friendly labels and guards around them.

## Implementation

### Modules

| File | Purpose |
| --- | --- |
| `builder_core/real_repo_validation/review_tool.py` | Core workflow: load run dir, validate, decide, resume, CSV, progress metrics |
| `builder_core/real_repo_validation/review_cli.py` | CLI entry point |

### CLI

```powershell
cd C:\J.A.R.V.I.S\local_jarvis

# Validate artifact completeness before review
py -3 -m builder_core.real_repo_validation.review_cli validate `
  --run-dir reports\phase95c_first_run `
  --slot reviewer_a

# List pending / reviewed ids (stable sample order)
py -3 -m builder_core.real_repo_validation.review_cli list `
  --run-dir reports\phase95c_first_run `
  --slot reviewer_a

# Show next pending item (metadata + source window)
py -3 -m builder_core.real_repo_validation.review_cli resume `
  --run-dir reports\phase95c_first_run `
  --slot reviewer_a

# Record a decision (requires --reviewer)
py -3 -m builder_core.real_repo_validation.review_cli decide `
  --run-dir reports\phase95c_first_run `
  --record-id RR-937189fed10f53c7 `
  --label false_positive `
  --fp-reason "argv is constant list; no shell" `
  --reviewer alice `
  --slot reviewer_a

# Progress + estimates for the slot
py -3 -m builder_core.real_repo_validation.review_cli report `
  --run-dir reports\phase95c_first_run `
  --slot reviewer_a

# Deterministic CSV export (local only; do not commit)
py -3 -m builder_core.real_repo_validation.review_cli export-csv `
  --run-dir reports\phase95c_first_run `
  --slot reviewer_a
```

Slots: `reviewer_a`, `reviewer_b`, `adjudication`.

### Reviewer labels (Phase 95D)

| Reviewer label | Harness label | Default usefulness |
| --- | --- | ---: |
| `true_positive` | `confirmed_actionable` | 4 |
| `useful_advisory` | `useful_review_lead` | 3 |
| `unclear` | `undecidable` | 2 |
| `not_useful` | `benign_or_intended` | 1 |
| `false_positive` | `misleading` | 0 |

Invalid labels are rejected. `--reviewer` is required for `decide`.

### Deterministic outputs

Written inside the run directory (local artifacts — **do not commit**):

| File | Content |
| --- | --- |
| `reviews.json` | Updated slot with mapped harness labels (stable JSON via harness writer) |
| `review_decisions.<slot>.json` | Audit trail with Phase 95D labels + timestamps |
| `review_decisions.<slot>.csv` | Flat export via `export-csv` |

Resume behavior:

- Items are processed in the same order as `review_sample.json`.
- `resume` / `show --next` returns the first slot-local pending `record_id`.
- Existing decisions are **not** overwritten unless `--edit` is passed.

### Validation

`validate` checks:

- Required packet fields present
- Packet count matches review sample
- Every sample id exists in packets and `reviews.json`
- No duplicate packet ids
- Harness review schema validity
- Decision audit file schema + label validity + duplicate record ids

### Report command

`report` prints slot-local:

- reviewed / pending counts
- label histogram
- precision estimate: `TP / (TP + FP)` among decisive labels
- usefulness mean (0–4)
- harness strict precision from mapped labels
- top false-positive reasons (from `--fp-reason` / notes)

After review completes, regenerate the aggregate validation report with the existing harness:

```powershell
py -3 -m builder_core.real_repo_validation.cli report --run-dir reports\phase95c_first_run
```

## Safety Boundaries

- Read-only with respect to scanned target repositories.
- Does not invoke the analysis engine.
- Does not change benchmark logic or scoring rules in the harness.
- Does not modify detector code.

## Tests

```powershell
py -3 -m pytest builder_core\tests\test_phase95d_review_tooling.py -q
py -3 -m pytest builder_core\tests\ -q
```

Synthetic tiny packets only; no dependency on the full Phase 95C pilot corpus in CI.

## Recommended Review Flow

1. Run Phase 95C harness (`run`) into a local artifact directory outside target repos.
2. `validate --run-dir … --slot reviewer_a`.
3. Loop: `resume` → inspect → `decide --reviewer …`.
4. `report` for progress checks.
5. Reviewer B repeats with `--slot reviewer_b` on blinded `reviewer_b_packets.json` (identical content, separate slot file).
6. Resolve disagreements in `--slot adjudication`.
7. `builder-core-validation report --run-dir …` for aggregate readiness metrics.

## Acceptance

| Check | Status |
| --- | --- |
| Existing suite passes | Verified via pytest |
| New Phase 95D tests pass | `test_phase95d_review_tooling.py` |
| No engine/intelligence files changed | Review tooling + docs only |
| No target source files changed | Tool reads artifacts only |
| Deterministic review outputs | Stable JSON sort + CSV row order |
| Local paths/artifacts not committed | Decision/CSV files remain under run dir only |
