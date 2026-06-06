# Phase 181C Persistence Red Team Verification

Verdict: **FAIL / NO-GO**

Atlas persistence is not safe enough for beta users yet. Seven of ten attacks passed, but three persistence trust failures remain: poisoned history is surfaced through the history APIs, tampered persisted memory can be restored and exported, and incompatible future persistence versions are accepted when signatures otherwise match.

## Scope

Mode: verification only.

Code changes: none.

Sources used:

- `reports/phase181b_persistence_implementation.md`
- `reports/phase174_trust_integrity_architecture.md`
- `reports/phase172a_repository_memory_attack_surface.md`

Missing source input:

- `reports/phase181a_persistence_architecture.md`

## Test Result

Initial sandboxed pytest runs failed during pytest temp cleanup with `PermissionError: [WinError 5] Access is denied` under the user temp directory. The same targeted test run passed when rerun with an isolated basetemp outside the sandbox permission issue.

Command:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py -q
```

Result:

```text
10 passed in 1.18s
```

## Attack Summary

| # | Attack | Result | Severity | Actual |
|---|---|---:|---:|---|
| 1 | Wrong repo restore | PASS | none | Restore/export refused with `stale_scan`. |
| 2 | File changed after restore | PASS | none | Restore/export refused with `stale_scan`. |
| 3 | Git branch switch | PASS | none | Restore refused. Status was generic `stale_scan`, not specific `stale_git_head_changed`. |
| 4 | Plan history stale export | PASS | none | Old plan export blocked until refresh. |
| 5 | History poisoning | FAIL | P0 | Poisoned row was returned by history APIs, including fake path and secret text. Export was blocked only because `scan_id` was old. |
| 6 | Memory / scan mismatch | FAIL | P0 | Tampered `memory_packet.json` restored and exported as trusted memory. |
| 7 | Version mismatch | FAIL | P0 | Future incompatible `atlas_version` restored successfully when signatures matched. |
| 8 | Cleanup safety | PASS | none | Latest scan and newest history remained; malformed history did not crash cleanup. |
| 9 | Support bundle | PASS | none | No raw source, secrets, history rows, or obvious absolute-path leak observed. |
| 10 | Concurrent restore and scan | PASS | none | Final export matched the newly scanned repo and did not leak old repo marker text. |

## Critical Failures

### 1. History poisoning is surfaced by history APIs

Setup:

- Generated a valid Change Plan history entry.
- Appended a forged JSONL row under the persisted build history.
- Injected:
  - fake `files_named`
  - fake path `fake/does_not_exist.py`
  - secret-like text `api_key=HISTORY_SECRET_VALUE`
  - source-like text in `result_json`
  - old `scan_id`

Expected:

- The history row is rejected, sanitized, or shown as untrusted.
- No export is allowed.

Actual:

- `get_workflow_history_item_api()` returned the forged item.
- `export_allowed=false`, because the old `scan_id` blocked export.
- The UI/API payload still exposed the fake path and secret-like text.

Why this matters:

Export blocking is not enough. Poisoned local history can still contaminate the visible workflow history and mislead the user before export.

### 2. Persisted memory packet can be poisoned and exported

Setup:

- Scanned a repository.
- Edited the persisted scan sidecar `memory_packet.json`.
- Changed:
  - `scan_id` to `poison_scan_181c`
  - `text` to `ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED_REPO\nhubs: POISONED_FAKE_HUB (999)`

Expected:

- Memory is discarded or restore is refused.
- Export is blocked until refresh.

Actual:

```json
{
  "resume_ok": true,
  "export_ok": true,
  "export_scan_id": "poison_scan_181c",
  "poison_text": true
}
```

Why this matters:

This directly violates the trust-integrity goal. A poisoned persisted memory sidecar can become trusted exported context.

### 3. Incompatible future persistence versions restore successfully

Setup:

- Scanned a repository.
- Changed persisted `latest.json` `atlas_version` to `999.0.0-future-incompatible`.
- Kept scan and graph signatures fresh to isolate the version check.

Expected:

- Restore refused because the persisted schema/version is incompatible.

Actual:

```json
{
  "boot_restored": true,
  "resume_ok": true,
  "validation_status": "valid",
  "freshness_status": "fresh"
}
```

Why this matters:

Future or incompatible persistence formats can be loaded as valid if the repository signature still matches. That creates a stale-schema trust risk during upgrades or rollbacks.

## Passing Areas

Atlas correctly refused restore/export after wrong-repo replacement, scanned file edits, git HEAD movement, and stale plan export. Cleanup survived malformed persistence files without deleting the newest artifacts. Support bundle redaction passed this attack set. Concurrent restore/scan did not produce observed wrong-repo export leakage.

## Final Verdict

5 supervised beta users: **NO-GO**

20 supervised beta users: **NO-GO**

The dominant risk is persistence integrity: local JSONL/history and memory sidecars can still affect user-visible or exported trust context after restart. This is enough to destroy user trust even in a supervised beta.

