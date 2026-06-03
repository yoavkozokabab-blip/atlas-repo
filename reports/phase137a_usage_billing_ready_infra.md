# Phase 137A — Usage + billing-ready infrastructure

## Summary

Phase 137A adds local usage tracking, configurable plans, cost estimation, API endpoints, and gated UI pages — with **no Stripe**, **no real payments**, and **no hard paywalls** unless `ATLAS_USAGE_ENFORCEMENT=true`.

## Module: `jarvis_desktop/usage/`

| File | Role |
|------|------|
| `models.py` | `UsageEvent` with full schema (user, workspace, repo, counts, token-equivalent, plan) |
| `store.py` | JSONL persistence under `ATLAS_USAGE_DATA_DIR` |
| `tracker.py` | Record events, user/admin summaries, billing UI flag |
| `plans.py` | FREE / PRO / TEAM / ENTERPRISE limits |
| `limits.py` | Advisory limit checks (enforcement off by default) |
| `estimator.py` | `estimate_repo_cost()` → scan units, token-equivalent, size tier, recommended plan |

## Tracked events

- `scan_started` / `scan_completed`
- `build_plan_created` / `investigation_created` / `impact_created` / `export_created`
- `repository_map_opened`

Wired in `api.py` at scan, planning, impact, export, and from the Repository Map UI.

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/usage/me` | User usage dashboard |
| GET | `/api/usage/admin` | Admin aggregates (local admin / `ATLAS_ADMIN=1`) |
| GET | `/api/plans` | Plan catalogue |
| GET | `/api/pricing` | Pricing page data (no checkout) |
| POST | `/api/usage/event` | Explicit event ingestion |

Legacy aliases: `/api/billing/*` → same payloads.

## UI (gated)

Set `ATLAS_BILLING_UI_ENABLED=true` to show:

- Nav links in the main app → `usage.html`, `pricing.html`, `billing_admin.html`
- Standalone pages powered by `billing.js`

CTAs are **Join beta** / **Contact us** only — no checkout.

## Flags

| Flag | Default | Effect |
|------|---------|--------|
| `ATLAS_BILLING_UI_ENABLED` | off | Show billing nav + pages |
| `ATLAS_USAGE_ENFORCEMENT` | off | Limits are advisory only |
| `ATLAS_ADMIN` | off | Local owner is admin by default on desktop |
| `ATLAS_USAGE_DATA_DIR` | `~/.jarvis_desktop/usage` | Storage path |

## Tests

```bash
py -3 -m pytest jarvis_desktop/tests/test_phase137a_usage_tracking.py -q
```

10 tests: event recording, aggregation, plans, pricing, admin, API routes, UI flag, no Stripe in usage module, estimator labels.

## Notes

- Token figures are **Atlas compute units (token-equivalent estimate)** — not billed OpenAI tokens.
- `jarvis_desktop/billing/` remains a thin adapter over `usage/` for backward compatibility.
