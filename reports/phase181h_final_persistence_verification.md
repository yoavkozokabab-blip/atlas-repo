# Phase 181H Final Persistence Verification

Verdict: **FAIL / NO-GO**

The two Phase 181F persistence poisoning blockers are fixed:

- Forged history with recomputed deterministic hash is rejected.
- Memory text poisoning with preserved signatures is rejected.

However, Phase 181H did **not** reach the requested 20/20 clean pass because the support bundle can still include the literal `persistence_secret` marker when it appears in logs. A separate sanity probe also found a fresh normal scan export regression: `session_export_packet()` returns `memory_untrusted` immediately after a successful scan.

## Scope

Mode: verification only.

Code changes by Codex: none.

Current working tree note:

- `jarvis_desktop/persistence.py`
- `jarvis_desktop/repository_memory.py`
- `jarvis_desktop/install_support.py`

were already modified before this verification pass and were treated as the candidate Phase 181H fixes. They were inspected and tested but not staged by this verification.

## Commands

Red-team harness:

```powershell
py -3 -
```

The harness created temporary repositories and temporary `ATLAS_DESKTOP_DATA` folders under Windows temp. It was run with elevated filesystem access because sandboxed temp creation hit Windows permission errors.

Regression tests:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase181b_persistence.py jarvis_desktop/tests/test_phase181e_persistence_red_team_fixes.py jarvis_desktop/tests/test_phase181g_persistence_signing.py -q -p no:cacheprovider
```

Result:

```text
29 passed in 7.53s
```

## Required Attack Result

| Group | Count | Pass | Fail |
|---|---:|---:|---:|
| Exact Phase 181F attacks | 20 | 19 | 1 |
| Specific Phase 181H checks | 5 | 4 | 1 |

Attack #9 failed:

- `181C-09 support bundle and persistence_secret redaction`

The concurrency attacks returned safe `memory_untrusted` refusals rather than stale or mixed exports. I counted them as PASS for the stated safety requirement because they did not export stale, poisoned, or wrong-repo context. They still expose a usability/export regression described below.

## Specific Checks

| Check | Result | Evidence |
|---|---|---|
| Forged history with recomputed hash fails | PASS | Forged row was not listed; item lookup returned `ok=false`; fake path and secret text did not surface. |
| Memory text poisoning with preserved signatures fails | PASS | Restore set `persistence_memory_rejected=true`; export returned `memory_untrusted`; poisoned text was not exported. |
| `persistence_secret` not present in support bundle | FAIL | Raw 32-byte secret was absent, but the literal marker `persistence_secret` appeared in the support bundle log payload. |
| Legacy unsigned history cannot export | PASS | Row became `historical_only=true`, `export_allowed=false`. |
| Legacy unsigned memory cannot export | PASS | Restore marked memory rejected and export returned `memory_untrusted`. |

## Failure 1: Support Bundle Leaks `persistence_secret` Marker

Setup:

- Scan a temporary repo.
- Force persistence secret creation.
- Write `persistence_secret` into `launcher.log` with other secret-like strings.
- Export support bundle.
- Inspect all files inside the zip.

Expected:

- No raw source.
- No secrets.
- No absolute paths.
- No history content.
- No raw persistence secret bytes.
- No `persistence_secret` marker.

Actual:

```json
{
  "bundle_ok": true,
  "leaks": ["persistence_secret"],
  "secret_bytes_present": false
}
```

Assessment:

- Secret bytes did not leak.
- The literal marker still leaked through logs.
- Root cause appears to be that support payload JSON sanitation redacts `persistence_secret`, but collected log text uses `_redact_support_text()` directly and does not apply the same marker redaction.

Severity: **P0** because the user explicitly required `persistence_secret` not to appear in the support bundle.

## Additional Regression: Fresh Scan Export Is Blocked

Setup:

- Create a new temporary repo.
- Run `api.scan_repository(repo)`.
- Immediately call `api.session_export_packet()`.

Expected:

- A normal successful scan should produce a usable Atlas context export.

Actual:

```json
{
  "scan_ok": true,
  "export_ok": false,
  "export_status": "memory_untrusted",
  "export_error": "Session export failed integrity check.",
  "session_export_has_memory_hmac": false
}
```

Assessment:

- This is not stale export, but it blocks normal export after scan.
- The likely cause is that persisted memory sidecars are HMAC-signed, but the in-memory `session_export` packet created during scan does not include `memory_hmac` before `session_export_packet()` validates it.
- The Phase 181G tests pass, but they do not catch this direct fresh scan -> export regression.

Severity: **P0/P1** for beta readiness because Copy for Claude / export is a core first-user path.

## What Passed

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
- Deleted memory file did not export poisoned memory.
- Partial write file ignored.
- Repo rename refused.
- Same-path repo replacement refused.
- Fake scan_id blocked export.
- Legacy unsigned history and memory cannot export.
- Concurrent restore/scan/export did not leak stale or wrong-repo context.

## Final Verdict

5 supervised beta users: **NO-GO**

20 supervised beta users: **NO-GO**

Reason:

- Required support-bundle `persistence_secret` redaction is incomplete.
- Normal fresh scan export currently fails as `memory_untrusted`.

