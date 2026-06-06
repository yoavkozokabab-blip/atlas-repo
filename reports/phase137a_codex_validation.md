# Phase 137A Codex Validation - Usage/Billing Infra

Date: 2026-06-03

Verdict: **FAIL / NO-GO for strict Phase 137A acceptance**

Atlas has local usage tracking and billing-ready/mock pricing infrastructure. I did not find active real payment collection. The blockers are test execution failures in this environment, partial pricing-page gating, and incomplete admin dashboard coverage for "high-usage users".

## Pass/Fail Table

| Check | Result | Evidence |
|---|---:|---|
| No real payment integration | PASS | Focused search found no Stripe secret key usage, no `import stripe`, no checkout session creation, no payment intent, and no external payment API calls in `jarvis_desktop/usage`, `jarvis_desktop/billing`, `jarvis_desktop/api.py`, `jarvis_desktop/server.py`, or `jarvis_desktop/static`. Hits were display-only fields such as `price_display`. |
| Payment collection disabled | PASS | `jarvis_desktop/usage/plans.py` returns `payment_provider: None` and `checkout_enabled: False`; pricing page text says no payment is collected today; buttons route to `contact.html`, not checkout. |
| Usage event tracking | PASS | Manual API run recorded `scan_started`, `scan_completed`, `build_plan_created`, `investigation_created`, `impact_created`, and `export_created` in local JSONL usage events. |
| User usage page/API | PASS | `/api/usage/me` returns plan, scans, repositories, exports, token-equivalent compute units, and limits. `usage.html` renders those fields through `billing.js`. |
| Admin dashboard/API | PARTIAL | `/api/usage/admin` returns total scans, failed scans, largest repos, slowest scans, usage by plan, event counts, and highest-usage repos. It does not expose "high-usage users" as requested. |
| Pricing tiers | PASS | Free / Pro / Team / Enterprise exist. Prices are `$0`, `Coming soon`, `Coming soon`, and `Custom`; CTAs are beta/contact style. |
| Pricing hidden unless flag enabled | PARTIAL | `ATLAS_BILLING_UI_ENABLED` defaults false and the app nav wrapper is hidden by default, then shown only when health reports the flag. However `pricing.html`, `usage.html`, and `billing_admin.html` are still directly accessible static pages. |
| Required targeted tests | FAIL | Exact command fails with pytest temp permission errors before several tests execute. |
| Full desktop tests | FAIL | Exact full test command did not finish cleanly. |

## Manual Usage Verification

Command:

```powershell
$env:ATLAS_USAGE_DATA_DIR = (Join-Path (Get-Location) '.phase137a_usage_verify')
$env:JARVIS_DESKTOP_DATA = (Join-Path (Get-Location) '.phase137a_desktop_data')
$env:ATLAS_ADMIN='1'
py -3 - <<script body calling jarvis_desktop.api>>
```

Actions performed:

- Scan bundled small demo repo with `api.load_demo_mode("small")`
- Create Build Plan with `api.plan_change("add rate limiting")`
- Create Investigate with `api.investigate_symptom("why are duplicate events firing")`
- Create Impact with `api.change_impact_simulation("core/hub.py")`
- Export prompt with `api.context_export("claude", "compact")`
- Read `/api/usage/me` equivalent with `api.usage_me()`
- Read `/api/usage/admin` equivalent with `api.usage_admin()`
- Read pricing payload with `api.usage_pricing()`

Observed summary:

```json
{
  "scan_ok": true,
  "scan_files": 6,
  "scan_modules": 5,
  "scan_edges": 4,
  "build_ok": true,
  "investigate_ok": true,
  "impact_ok": true,
  "export_ok": true,
  "export_tokens": 294,
  "usage_ok": true,
  "usage": {
    "scans_used": 2,
    "repositories_used": 1,
    "exports_used": 1,
    "build_plans": 1,
    "investigations": 1,
    "impacts": 1,
    "token_equivalent_total": 1184
  },
  "admin_ok": true,
  "admin_total_scans": 2,
  "admin_failed_scans": 0,
  "admin_largest_count": 1,
  "admin_slowest_count": 2,
  "admin_usage_by_plan": {"FREE": 1},
  "pricing_checkout_enabled": false,
  "pricing_payment_provider": null,
  "billing_ui_enabled": false,
  "plans": ["Free", "Pro", "Team", "Enterprise"]
}
```

Event file proof:

- `scan_started`
- `scan_completed`
- `build_plan_created`
- `investigation_created`
- `impact_created`
- `export_created`

The usage events were written under `.phase137a_usage_verify/usage_events.jsonl`.

## No Real Payment Proof

Focused search command:

```powershell
rg -n "STRIPE_SECRET|STRIPE_API|sk_live|sk_test|import stripe|stripe\.checkout|checkout\.sessions|https://api\.stripe\.com|/v1/checkout|payment_intent|billing portal|price_[A-Za-z0-9]" jarvis_desktop\usage jarvis_desktop\billing jarvis_desktop\api.py jarvis_desktop\server.py jarvis_desktop\static -g "*.py" -g "*.js" -g "*.html"
```

Result:

- No Stripe secret usage.
- No Stripe SDK import.
- No checkout session creation.
- No payment intent creation.
- No external payment API call.
- Only display-only `price_display` strings were found.

Relevant static/API evidence:

- `jarvis_desktop/usage/plans.py`: `payment_provider` is `None`; `checkout_enabled` is `False`.
- `jarvis_desktop/static/pricing.html`: says no payment is collected today.
- `jarvis_desktop/static/billing.js`: plan buttons link to `contact.html`, not a payment provider.

## UI/API Surface

Routes verified by code inspection:

- `GET /api/usage/me`
- `GET /api/usage/admin`
- `GET /api/plans`
- `GET /api/pricing`
- `POST /api/usage/event`
- compatibility aliases under `/api/billing/*`

Static pages verified by file inspection:

- `jarvis_desktop/static/usage.html`
- `jarvis_desktop/static/pricing.html`
- `jarvis_desktop/static/billing_admin.html`

Important caveat:

- `jarvis_desktop/static/index.html` contains `usage.html`, `pricing.html`, and `billing_admin.html` inside a hidden billing nav wrapper.
- `jarvis_desktop/static/app.js` calls `applyBillingNav(!!h.billing_ui_enabled, true)` and only fetches `/api/usage/me` when the flag is enabled.
- Direct static navigation to pricing/admin pages is still possible even when `ATLAS_BILLING_UI_ENABLED=false`.

## Test Results

Exact targeted command:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase137a_usage_tracking.py -q
```

Result:

```text
5 passed, 5 errors, 2 warnings
Exit code: 1
```

Primary error:

```text
PermissionError: [WinError 5] Access is denied:
C:\Users\babi2\AppData\Local\Temp\pytest-of-babi2
```

Workspace-local pytest temp retry:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase137a_usage_tracking.py -q -p no:cacheprovider --basetemp "reports\phase137a_pytest_tmp\focused"
```

Result:

```text
EE..EEE...
PermissionError: [WinError 5] Access is denied:
C:\J.A.R.V.I.S\local_jarvis\reports\phase137a_pytest_tmp\focused
Exit code: 1
```

Exact full desktop test command run during this validation pass:

```powershell
py -3 -m pytest jarvis_desktop/tests -q
```

Observed result:

```text
6 failed, 343 passed, 6 skipped, 2 warnings, 123 errors in 2747.82s (0:45:47)
Exit code: non-zero
```

Notable failures/errors included:

- Pytest temp/cache `PermissionError` failures.
- Route/documentation expectation drift.
- Older billing/pricing tests expecting stricter hidden-page behavior and no `stripe` string even in "No Stripe" copy.

Because the exact required pytest commands do not pass, Phase 137A cannot be accepted as PASS from Codex verification.

## Screenshots

Screenshots were not captured. This validation used API execution plus static HTML/JS inspection. The current blockers are visible from code/API/test evidence without needing a browser screenshot.

## Remaining Risks

1. **Admin dashboard is repo-centric, not user-centric.** It shows highest-usage repositories, but the requirement asks for high-usage users.
2. **Admin access is effectively local-owner/admin by default.** `UsageStore.ensure_local_user()` creates the local owner with admin role even when `ATLAS_ADMIN` is not set. That may be acceptable for local desktop, but it is not a real multi-user admin gate.
3. **Billing/pricing static pages are directly reachable.** Nav is hidden by default, but the static pages are still served.
4. **Two local billing namespaces remain.** `jarvis_desktop/usage` is active for Phase 137A, while `jarvis_desktop/billing` remains as a compatibility adapter/local mock surface. This is not payment-risky, but it can confuse future maintenance.
5. **Pytest temp permissions block clean verification.** Required tests cannot be certified until the local temp/pytest permission issue is resolved.
6. **Verification generated untracked local data.** `.phase137a_usage_verify/`, `.phase137a_desktop_data/`, `.phase137a_pytest_tmp/`, and related probe dirs are local verification artifacts and should not be committed.

## Final Assessment

Phase 137A is **billing-safe** in the narrow payment sense: no active real payment collection was found.

Phase 137A is **not yet externally beta-ready under the requested acceptance criteria** because the exact tests do not pass, admin reporting is missing high-usage users, and billing UI/page gating is only partial.
