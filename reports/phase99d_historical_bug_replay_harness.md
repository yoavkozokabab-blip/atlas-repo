# Phase 99D — Historical Bug Replay Harness

**Status:** Infrastructure complete  
**Date:** 2026-05-31  
**Scope:** Replay measurement only — no detector or benchmark changes  
**Module:** `builder_core/historical_bug_replay/`

---

## Summary

Phase 99D adds a **historical bug replay harness** that compares buggy and fixed revisions through the full confirmation pipeline:

```text
analysis → contract review → verification evidence → confirmed-defect gate
```

The harness is **disabled by default** (`HISTORICAL_BUG_REPLAY_ENABLED = False`). Replay runs require explicit enablement (`--enable` on the CLI or `enabled=True` in API calls). During replay, the confirmed-defect gate is enabled **only inside the replay session**; the global gate flag returns to `False` afterward.

| Item | Value |
|------|-------|
| Package | `builder_core/historical_bug_replay/` |
| CLI | `py -3 -m builder_core.historical_bug_replay.cli run --manifest … --output … --enable` |
| Default flag | `HISTORICAL_BUG_REPLAY_ENABLED = False` |
| Tests added | 11 (`test_phase99d_historical_bug_replay.py`) |
| Full suite | **366 passed** |

---

## Inputs

Each manifest case requires:

| Field | Required | Description |
|-------|:--------:|-------------|
| `id` | yes | Stable case identifier |
| `buggy_revision` | yes* | Buggy snapshot spec |
| `fixed_revision` | yes* | Fixed snapshot spec |
| `description` | no | Human-readable summary |
| `fixed_files` | no | Files used for detected-on-target matching |
| `target_rules` | no | Rule filter (e.g. `["inconsistent_return"]`) |
| `test_documents` | no | Repository test AST documents for verification evidence |
| `pair_dir` | alt | Shorthand: directory containing `buggy.py` and `fixed.py` |

\* `pair_dir` expands to file revisions before validation.

### Revision kinds

| Kind | Fields | Use |
|------|--------|-----|
| `file` | `path`, optional `rel_path` | Read a Python file from disk |
| `inline` | `source`, optional `rel_path` | In-memory source (tests) |
| `git` | `repo_path`, `ref`, `file` or `files` | Read-only `git show ref:path` |

Example manifest fragment:

```json
{
  "schema_version": 1,
  "program_id": "phase99d-example",
  "cases": [
    {
      "id": "holdout_transfer_bfs",
      "description": "Holdout BFS empty-queue transfer pair",
      "pair_dir": "builder_core/benchmarks/holdout/pairs/transfer_bfs_empty_queue"
    }
  ]
}
```

---

## Pipeline (per revision)

For each resolved source file the harness runs `engine.analyze_source`, which already applies:

1. Unified analysis (logic, security, algorithm as configured)
2. Phase 96C contract enrichment (`contract_review`)
3. Phase 97A verification evidence (`verification_evidence`)
4. Phase 99A confirmed-defect gate (temporarily enabled for replay only)

Each finding record includes:

- `classification`: `detected` | `strong_suspect` | `review_lead` | `refuted` | `unknown`
- Full gate packet, contract review status, verification status

**Mapping:** gate `confirmed_defect` → output bucket **`detected`**.

---

## Outputs

Written to the requested output directory:

| Artifact | Contents |
|----------|----------|
| `results.json` | Per-case buggy/fixed findings, bucket counts, case summaries |
| `metrics.json` | Aggregate classification counts and case-level detected metrics |
| `report.md` | Human-readable summary |

### Classification buckets

| Bucket | Source gate class |
|--------|-------------------|
| `detected` | `confirmed_defect` |
| `strong_suspect` | `strong_suspect` |
| `review_lead` | `review_lead` |
| `refuted` | `refuted` |
| `unknown` | `unknown` / unclassified |

### Aggregate metrics

| Metric | Meaning |
|--------|---------|
| `cases_evaluated` | Manifest cases replayed |
| `buggy` / `fixed` | Finding counts per bucket |
| `cases_with_detected_on_buggy` | Cases with ≥1 detected finding on buggy revision |
| `cases_with_detected_on_fixed` | Cases with ≥1 detected on fixed (confirmation FP cases) |
| `cases_with_detected_buggy_only` | Detected on buggy, not on fixed |
| `detected_case_recall` | `cases_with_detected_on_buggy / cases_evaluated` |
| `detected_case_false_positive_rate` | `cases_with_detected_on_fixed / cases_evaluated` |
| `detected_case_purity` | `detected_buggy_only / detected_on_buggy` |

---

## Usage

```text
py -3 -m builder_core.historical_bug_replay.cli run \
  --manifest reports/phase99d_example_manifest.json \
  --output reports/phase99d_example_run \
  --enable
```

Without `--enable` and with `HISTORICAL_BUG_REPLAY_ENABLED = False`, the harness refuses to run.

---

## Constraints honored

- No detector changes
- No benchmark behavior changes (QuixBugs/holdout regression tests unchanged with gate default off)
- Replay is read-only (file read / `git show`; no execution of analyzed code)
- Global confirmed-defect gate remains disabled outside explicit replay sessions

---

## Relationship to Phase 99B

Phase 99B defines preregistered historical buggy/fixed corpora and confirmation evaluation gates. Phase 99D supplies the **replay machinery** to measure those cases once a manifest is locked. It does not preregister cases, label outcomes, or claim external-alpha readiness.

---

## Next steps (out of scope for 99D)

1. Lock a preregistered historical-bug manifest (parent/fix commits + fixed files).
2. Run replay on Phase 98A corpus candidates after historical cases are registered.
3. Tie replay metrics to Phase 99B confirmation score thresholds.
