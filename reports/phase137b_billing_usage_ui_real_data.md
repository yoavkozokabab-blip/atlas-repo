# Phase 137B — Billing / Usage UI Real Data Polish

## What was broken

1. **Usage page** showed “Usage unavailable” when fetch failed or response shape was unexpected; empty states were not helpful.
2. **Pricing page** kept a dominant “Coming soon / private beta” banner and did not render full plan cards from `/api/pricing`.
3. **Admin page** could surface raw API errors (including “Unknown endpoint”) when routes failed; disabled admin messaging was terse.
4. **`billing.js`** loaded page data only after `/api/health`, had no legacy endpoint fallbacks, and crashed sections when optional fields were missing.
5. **Admin API** lacked several dashboard fields requested for SaaS-style summaries (build plans, investigations, recent events, compute units, etc.).

## Endpoints fixed / extended

| Endpoint | Change |
|----------|--------|
| `GET /api/usage/me` | Added `billing_status`, `payments_active`, `has_usage_data`, `empty_state_message`, `recent_events`, `estimated_atlas_compute_units` |
| `GET /api/usage/admin` | Extended payload: `total_repositories`, `total_build_plans`, `total_investigations`, `total_impacts`, `high_usage_users`, `recent_events`, compute/token totals; cleaner `admin_disabled` response |
| `GET /api/usage/admin_summary` | **New alias** → same handler as `/api/usage/admin` |
| `GET /api/plans`, `/api/pricing` | Unchanged; frontend now renders them fully |

Legacy aliases still supported in UI: `/api/billing/usage`, `/api/billing/admin`, `/api/billing/plans`.

## UI changes

- **`billing.js`** — robust multi-endpoint fetch, number/duration formatters, graceful empty states, no raw error text.
- **`billing.css`** — shared dashboard styling (cards, grids, tables, banners).
- **`usage.html`** — plan hero, metrics grid, limits, largest repos, recent activity, upgrade placeholder.
- **`pricing.html`** — four plan render targets; real cards from API; non-payment CTAs.
- **`billing_admin.html`** — full admin dashboard sections with disabled-state copy referencing `ATLAS_ADMIN=1`.

Feature flag behavior unchanged:

- `ATLAS_BILLING_UI_ENABLED=true` → main app nav shows Usage / Pricing / Admin.
- `ATLAS_BILLING_UI_ENABLED=false` → pages still reachable; flag note shows preview-only message.

## Manual verification notes

Start Atlas:

```powershell
$env:ATLAS_BILLING_UI_ENABLED="true"
$env:ATLAS_ADMIN="1"
py -3 run_jarvis_desktop.py
```

Open:

- http://127.0.0.1:8777/pricing.html — plan cards for Free / Pro / Team / Enterprise
- http://127.0.0.1:8777/usage.html — dashboard or empty-state guidance
- http://127.0.0.1:8777/billing_admin.html — admin metrics or clean disabled message without `ATLAS_ADMIN=1`

Expected: no “Unknown endpoint”, no “Usage unavailable” as sole content, no payment checkout.

## Tests run

```text
py -3 -m pytest jarvis_desktop/tests/test_phase137b_billing_usage_ui.py -q
py -3 -m pytest jarvis_desktop/tests/test_phase137a_usage_tracking.py -q
py -3 -m pytest jarvis_desktop/tests -q
```

## Remaining limitations

- Single local user / mock workspace — no multi-tenant auth.
- Plan enforcement remains off unless `ATLAS_USAGE_ENFORCEMENT=true`.
- Prices are placeholders (“Private beta”, “Coming soon”, “Custom”).
- Admin “users” count is mock/local-only.

## Confirmation

- **No Stripe**
- **No real checkout or payment URLs**
- **No hard paywalls** in this phase
- **No changes** to Phase 136 semantic benchmark work or core Atlas intelligence
