# Phase 181F Final Persistence Red Team

Verdict: **FAIL / NO-GO**

Atlas persistence is safer than Phase 181C in several important paths, but it is not safe enough for beta users. The final red-team run found two P0 persistence-integrity failures:

1. Forged workflow history can pass integrity verification if the deterministic hash is recomputed.
2. Persisted memory text can be poisoned and exported when the attacker preserves scan_id and signature metadata.

## Scope

Mode: verification only.

Production code changes: none.

Reports written:

- `reports/phase181f_final_persistence_red_team.md`
- `reports/phase181f_attack_results.json`
- `reports/phase181f_remaining_blockers.md`

## Commands

Red-team harness:

```powershell
py -3 -
```

The harness was run as an inline Python verifier using temporary repositories and temporary `ATLAS_DESKTOP_DATA` folders under the Windows temp directory. The first sandboxed attempt could not create Windows temp folders, so the harness was rerun with elevated filesystem access against temporary folders only.

Regression tests:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py -q -p no:cacheprovider
```

Result:

```text
18 passed in 1.78s
```

## Summary

| Set | Attacks | Passed | Failed |
|---|---:|---:|---:|
| Phase 181C rerun | 10 | 8 | 2 |
| New Phase 181F attacks | 10 | 10 | 0 |
| Total | 20 | 18 | 2 |

Failed attacks:

- #5 `181C-05 history poisoning`
- #6 `181C-06 memory / scan mismatch`

## Attack Table

| # | Attack | Result | Notes |
|---:|---|---|---|
| 1 | Wrong repo restore | PASS | Same-path replacement refused with `stale_scan`; no repo A export. |
| 2 | File changed after restore | PASS | Restore/export refused with `stale_scan`. |
| 3 | Git branch switch | PASS | Restore/export refused with `stale_scan`. |
| 4 | Plan history stale export | PASS | Old plan export blocked until refresh. |
| 5 | History poisoning | FAIL | Recomputed deterministic history hash allows forged rows to be trusted; current-scan forged row had `export_allowed=true`. |
| 6 | Memory / scan mismatch | FAIL | Mismatched scan_id is blocked, but same-scan memory text tamper exported poisoned memory. |
| 7 | Version mismatch | PASS | Future version refused with `version_mismatch`. |
| 8 | Cleanup safety | PASS | Corrected cleanup probe kept newest scan and did not crash on malformed history. |
| 9 | Support bundle | PASS | No tested secrets, source snippets, history rows, or absolute paths leaked. |
| 10 | Concurrent restore and scan | PASS | No observed mixed old/new final export. |
| 11 | Corrupted scan JSON | PASS | No restore/export from corrupted `latest.json`. |
| 12 | Corrupted history JSONL | PASS | Malformed row ignored; valid history still listed. |
| 13 | Deleted graph file | PASS | Resume refused with `partial_scan`; no export. |
| 14 | Deleted memory file | PASS | No poisoned or mismatched memory exported. |
| 15 | Partial write file | PASS | Leftover `.tmp` file ignored; valid latest scan restored. |
| 16 | Repo renamed | PASS | Restore refused with `path_missing`; no export. |
| 17 | Repo replaced at same path | PASS | Restore/export refused with `stale_scan`; no repo A leak. |
| 18 | Branch switch | PASS | Restore/export refused with `stale_scan`. |
| 19 | Fake scan_id | PASS | Memory rejected and export blocked. |
| 20 | Concurrent restore + scan + export | PASS | Final export matched the newly scanned repo; no mixed-state marker observed. |

## Failure 1: History Poisoning

Setup:

- Scan a repository.
- Generate a Change Plan history row.
- Manually append forged history JSONL.
- Set fake paths and secret-like strings in `files_named`, `summary_markdown`, and `result_json`.
- Recompute `integrity_hash` using the local deterministic hash function.

Observed:

- Old-scan forged row:
  - `item_ok=true`
  - `export_allowed=false`
  - fake path and secret text still surfaced.
- Current-scan forged row:
  - `item_ok=true`
  - `export_allowed=true`
  - fake path and secret text surfaced.

Expected:

- Poisoned history rejected, sanitized, or shown as untrusted.
- No poisoned history export.

Actual:

- A forged row can pass integrity verification if the hash is recomputed.
- With current scan metadata, the forged row becomes export-allowed.

Root cause:

- The history `integrity_hash` is deterministic and not keyed. It detects accidental edits and naive tampering, but not adversarial local edits.

Severity: **P0**

## Failure 2: Persisted Memory Text Poisoning

Setup:

- Scan a repository.
- Edit persisted `memory_packet.json`.
- Preserve `repo_id`, `scan_id`, and scan signatures.
- Replace only the exported `text` field with poisoned repository memory.

Observed:

```json
{
  "resume_ok": true,
  "memory_rejected": null,
  "export_ok": true,
  "poison_exported": true
}
```

Expected:

- Poisoned or mismatched persisted memory discarded.
- No poisoned memory export.

Actual:

- Metadata-preserving memory text tamper restored and exported.

Root cause:

- Session memory packet validation checks repo_id, scan_id, and signatures, but does not authenticate the packet text itself.

Severity: **P0**

## What Improved Since 181C

- Future/incompatible version restore is now blocked.
- Mismatched memory scan_id is now blocked.
- Fake scan_id blocks export through memory rejection.
- Deleted graph sidecar blocks restore as partial scan.
- Corrupted scan JSON does not restore.
- Renamed/replaced repositories do not restore stale exports.
- Support bundle redaction passed this attack set.

## Final Verdict

5 supervised beta users: **NO-GO**

20 supervised beta users: **NO-GO**

The remaining failures are local persistence trust failures. They do not require external code execution or network access; they require only local file tampering. That is still enough to damage beta trust because Atlas can surface or export forged repository context as if it were trusted.

