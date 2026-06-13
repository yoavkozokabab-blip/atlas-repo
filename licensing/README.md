# Atlas Desktop Licensing

Local enforcement of the **Free / Trial / Pro** plans, talking to the Atlas
website's `/api/license` and `/api/track` endpoints. Standard-library only — no
new pip dependencies.

## What it does

| Plan  | Repos | Files/repo | Pro features* |
|-------|-------|-----------|---------------|
| Free  | 1     | 50        | ❌ |
| Trial | ∞     | ∞         | ✅ (7 days) |
| Pro   | ∞     | ∞         | ✅ |

\* Pro features = Impact Analysis, AI Context Compression, Investigation Mode,
Architecture Risk Detection, Priority Support. Dependency Graph is on every plan.

## Files

- `client.py` — `LicenseClient`: fetch `/api/license?email=…`, cache for 24h in
  the app data dir, fall back to the last-known status when offline.
- `gates.py` — `feature_gate()`, `enforce_scan_limit()`, `can_add_repo()`.
- `integration.py` — opt-in glue used by `jarvis_desktop/api.py`.

## Enabling it

Gating is **off by default** so existing behaviour and tests are unchanged. It
activates only when the env flag is set (because it needs a deployed backend and
a way to know the user's email):

```bash
ATLAS_LICENSING_ENABLED=1
ATLAS_SITE_URL=https://your-atlas-domain.com   # where /api/license lives
# optional: ATLAS_LICENSE_CACHE=C:\path\to\license_cache.json
```

Then, once you have the signed-in user's email (e.g. from the account flow):

```python
from licensing import licensing
licensing.set_email(user_email)
status = licensing.refresh()          # cached 24h; offline-safe
if status.banner:
    show_trial_banner(status.banner)  # "5 days left in your Pro trial"
```

## Wiring already in place (`jarvis_desktop/api.py`)

- `impact()` → gated behind `impact_analysis` (returns `code: upgrade_required`).
- `investigate_symptom()` → gated behind `investigation`.
- `scan_repository()` → emits `repo_scanned`; attaches `result["license_notice"]`
  for Free users above the 50-file cap.

To gate more entry points, add at the top of the function:

```python
from licensing.integration import require_feature
_gate = require_feature("context_compression")  # or risk_detection
if _gate is not None:
    return _gate
```

## Hard file-cap enforcement (optional, deeper)

`scan_repository` currently surfaces a *notice* when a Free user exceeds 50
files. To hard-truncate at discovery instead, call
`licensing.integration.apply_scan_limit(discovered_files)` where the file list is
first built inside the scan pipeline and scan only the returned subset.
