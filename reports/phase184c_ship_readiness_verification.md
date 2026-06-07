# Phase 184C - Ship Readiness Verification

Date: 2026-06-07

Scope: Audit only. No source changes. This report verifies the current source tree and the currently built beta artifacts.

## Decision

| Target | Decision |
| --- | --- |
| 5 supervised beta users | NO-GO |
| 20 supervised beta users | NO-GO |

Reason: the current source tree passes the ship-readiness checks, but the distributable `dist/Atlas/Atlas.exe` / installer artifact is stale and still reports an internal pre-fix version. A beta ship should use the artifact, not only the source tree.

## Verification Summary

| Area | Source-tree result | Artifact result |
| --- | --- | --- |
| Load Sample | PASS | BLOCKED BY STALE ARTIFACT |
| Scan | PASS | BLOCKED BY STALE ARTIFACT |
| Change Plan | PASS | BLOCKED BY STALE ARTIFACT |
| Debug | PASS | BLOCKED BY STALE ARTIFACT |
| What Breaks | PASS | BLOCKED BY STALE ARTIFACT |
| Copy for Claude | PASS | BLOCKED BY STALE ARTIFACT |
| Resume scan | PASS | BLOCKED BY STALE ARTIFACT |
| Persistence restore | PASS | BLOCKED BY STALE ARTIFACT |
| Trust integrity | PASS | BLOCKED BY STALE ARTIFACT |
| Offline mode | PASS | BLOCKED BY STALE ARTIFACT |
| Feedback | PASS | BLOCKED BY STALE ARTIFACT |
| Update check | PASS | BLOCKED BY STALE ARTIFACT |
| Admin operations | PASS | BLOCKED BY STALE ARTIFACT |

## Evidence

### Automated regression gate

Command:

```powershell
py -3 -B -m pytest jarvis_desktop/tests/test_phase184b_beta_ship_blockers.py jarvis_desktop/tests/test_phase184_ux_consistency.py jarvis_desktop/tests/test_phase179_beta_ship_blockers.py jarvis_desktop/tests/test_phase182_beta_operations.py jarvis_desktop/tests/test_phase182a_operations_security.py jarvis_desktop/tests/test_phase181b_persistence.py jarvis_desktop/tests/test_phase181g_persistence_signing.py jarvis_desktop/tests/test_phase181k_final_regressions.py -q -p no:cacheprovider --tb=short --basetemp phase184c_pytest_escalated
```

Result:

```text
216 passed in 5.01s
```

Coverage from that gate:

- Phase 184B: Load Sample readiness, Copy for Claude non-empty payload, beta version source, local vendor assets.
- Phase 184 UX: canonical Change Plan / Debug / What Breaks labels and user-facing copy cleanup.
- Phase 179: sample to export workflow, update banner defaults/configured path, feedback local/remote paths, support redaction.
- Phase 182/182A: feedback inbox, update hardening, admin insights, crash/feedback minimization, operations security.
- Phase 181B/G/K: scan persistence, resume/restore, signed history/memory, stale export blocking, trust rejection.

### Direct API smoke

The direct API smoke was run against the current source tree with persistence writes allowed. Result:

| Check | Observed result |
| --- | --- |
| Load Sample | `ok=true`, small demo loaded, 6 files / 5 modules |
| Scan | `ok=true`, summary available after sample scan |
| Change Plan | `ok=true`, plan and export text present |
| Debug | `ok=true`, 3 hypotheses, formatted output present |
| What Breaks | `ok=true`, export text present for `core/hub.py` |
| Copy for Claude | `ok=true`, 17 non-metadata body lines |
| Resume scan | `ok=true` |
| Persistence restore | `ok=true`, `restored=true`, resume card valid/fresh |
| Trust integrity | `Fresh` before and after restore |
| Offline mode | `index.html` uses local `vendor/three.min.js` and `vendor/3d-force-graph.min.js`; no `unpkg.com` in `index.html` |
| Feedback | `ok=true`, `remote_sent=false` when no remote URL is configured |
| Update check | `configured=false`, `update_available=false`, `trust_level=trusted` |
| Admin operations | no-admin returns `admin_disabled`; `ATLAS_ADMIN=1` returns `ok=true` |

### Built artifact check

Current built files:

```text
dist/Atlas/Atlas.exe                         2026-06-04 19:34:27
installer/output/Atlas_Setup.exe             2026-06-04 19:34:57
packaging/installer/output/Atlas_Setup.exe   2026-06-04 19:34:57
```

Current source/package metadata:

```text
packaging/installer/generated_version.iss -> MyAppVersion "0.1.0-beta"
```

Packaged app health check:

```powershell
dist\Atlas\Atlas.exe --host 127.0.0.1 --port 8789 --no-browser
GET http://127.0.0.1:8789/api/health
```

Result:

```json
{
  "ok": true,
  "product": "ATLAS",
  "version": "phase146b-true-beta-blocker-fixes",
  "repository_open": false
}
```

This is not the verified source version (`0.1.0-beta`). It matches the old internal phase version found in Phase 184A and proves the shipped executable/installer were not rebuilt from the verified source tree.

## Real Remaining Blockers

1. Stale distributable artifact: `dist/Atlas/Atlas.exe` and both installer outputs are from 2026-06-04 and the packaged health endpoint still reports `phase146b-true-beta-blocker-fixes`. The current source tree passes the Phase 184C readiness gate, but the artifact a beta user would install does not represent that verified state.

