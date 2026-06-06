# Phase 181J Final Persistence Verification

Verdict: **FAIL / NO-GO**

Phase 181J did not reach the requested 20/20 PASS. The core persistence poisoning fixes are working, and trusted memory export after restore now works, but two beta-blocking issues remain:

1. Support bundles still include the literal `persistence_secret` marker when it appears in logs.
2. Fresh scan export still fails with `memory_untrusted`.

## Scope

Mode: verification only.

Code changes by Codex: none.

Current working tree note:

- `jarvis_desktop/repository_memory.py` had a pre-existing unstaged source modification before this verification pass.
- Codex did not stage or modify that source file.
- Only the Phase 181J reports were created.

## Commands

Combined runtime verifier:

```powershell
py -3 -
```

The verifier created temporary repositories and temporary `ATLAS_DESKTOP_DATA` folders under Windows temp. It was run with elevated filesystem access because sandboxed Windows temp creation previously hit permission errors.

Regression tests:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py jarvis_desktop/tests/test_phase181g_persistence_signing.py -q -p no:cacheprovider
```

Result:

```text
29 passed in 3.29s
```

No separate `test_phase181i_*` file exists in `jarvis_desktop/tests` at verification time, so Phase 181I cases were covered by explicit runtime regression checks in the verifier.

## Results

| Group | Total | Pass | Fail |
|---|---:|---:|---:|
| Phase 181F attacks | 20 | 19 | 1 |
| Phase 181I regression checks | 4 | 3 | 1 |

Failed attack:

- `181F-09 support bundle no secret markers or paths`

Failed regression:

- `181I-01 fresh scan export works`

## Required Checks

| Requirement | Result | Evidence |
|---|---|---|
| Fresh scan export works | FAIL | `session_export_packet()` returned `memory_untrusted` immediately after a successful scan. |
| Trusted memory exports work | PASS | Valid signed persisted memory restored and exported `ATLAS_REPOSITORY_MEMORY v1`. |
| Forged history fails | PASS | Forged recomputed-hash history was not listed; item lookup failed; fake path/secret did not surface. |
| Poisoned memory fails | PASS | Preserved-signature memory text tamper was rejected; export returned `memory_untrusted`; poison text did not export. |
| Support bundle contains no secret markers | FAIL | Bundle log payload still contained `persistence_secret`. |
| Support bundle contains no secret paths | PASS | Forced `C:\Users\demo\secret.py` path was redacted; no path leak found in this probe. |

## Failure 1: Support Bundle Marker Leak

Setup:

- Scanned a temporary repo.
- Forced persistence secret creation.
- Wrote the following canaries into `launcher.log`:
  - `api_key=SUPPORT_SECRET_VALUE`
  - `Authorization: Bearer SUPPORT_BEARER`
  - `JWT SUPPORT_JWT_TOKEN`
  - `persistence_secret`
  - `C:\Users\demo\secret.py`
- Exported the support bundle and inspected all zip entries.

Expected:

- No secret markers.
- No secret values.
- No raw persistence secret bytes.
- No absolute paths.
- No history content.

Actual:

```json
{
  "bundle_ok": true,
  "marker_leaks": ["persistence_secret"],
  "secret_bytes_present": false,
  "path_leaks": []
}
```

Assessment:

- Secret values and the forced absolute path were redacted.
- The literal `persistence_secret` marker still leaked through `logs/launcher.log`.
- This repeats the Phase 181H failure.

## Failure 2: Fresh Scan Export Still Fails

Setup:

- Created a new temporary repo.
- Ran `api.scan_repository(repo)`.
- Immediately ran `api.session_export_packet()`.

Expected:

- Fresh scan should produce usable Atlas context.

Actual:

```json
{
  "scan_ok": true,
  "export_ok": false,
  "export_status": "memory_untrusted",
  "export_error": "Session export failed integrity check.",
  "has_memory_hmac": false,
  "packet_version": null
}
```

Assessment:

- Trusted persisted memory after restart does export correctly.
- Fresh in-memory session export remains unsigned or otherwise fails memory validation.
- This is a first-use blocker because Copy/Export can fail immediately after a scan.

## Passing Areas

- Wrong repo restore refused.
- File edits after restore refused.
- Branch switch refused as stale.
- Stale plan history export blocked.
- Forged recomputed-hash history rejected.
- Preserved-signature memory text poisoning rejected.
- Future-version restore refused.
- Cleanup kept newest scan and survived malformed history.
- Corrupted scan JSON did not restore.
- Corrupted history JSONL ignored malformed rows.
- Deleted graph sidecar refused restore/export.
- Deleted memory file did not export poison.
- Partial write file ignored.
- Repo rename refused.
- Same-path repo replacement refused.
- Fake scan_id blocked export.
- Legacy unsigned history and memory cannot export.
- Concurrent restore/scan/export did not leak stale or wrong-repo context.
- Valid signed persisted memory exports after restore.

## Final Verdict

5 supervised beta users: **NO-GO**

20 supervised beta users: **NO-GO**

Reason:

- Required support bundle redaction is incomplete.
- Fresh scan export remains broken with `memory_untrusted`.

