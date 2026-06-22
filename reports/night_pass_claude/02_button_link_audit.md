# 02 — Button / Link Audit

**Date:** 2026-06-20. Classified by crawling rendered HTML + reading handlers (`_components/client.tsx`, `site.tsx`). Legend: Works · Works-but-confusing · Broken · Fake · Placeholder · Dangerous · Owner-only · Not-tested.

| Button / link | Target / action | Class |
|---|---|---|
| Header logo | `/` | Works |
| Features / Pricing / Docs / FAQ | `/features` `/pricing` `/docs` `/faq` | Works |
| Sign in | `/login` | Works |
| Download / Download for Windows | `/download` | Works |
| Hero "See it work" | `#see-it-work` (anchor exists) | Works |
| Join the beta | `/download` (and `#waitlist` form) | Works |
| Contact / Contact sales | `/contact` | Works |
| Privacy / Terms | `/privacy` `/terms` | Works |
| Download Atlas (authed) | `/download/atlas` → 302 installer | Works (Owner-only to make live: needs `ATLAS_INSTALLER_URL`) |
| Create a free account to download (anon) | `/login?next=/download` | Works |
| Create account / Login (form) | `/api/auth/register` / `login` | Works (surfaces errors, disables while busy) |
| Forgot password | `/api/auth/forgot` | Works (always-generic response; anti-enumeration) |
| Sign out | `/api/auth/logout` → `/` | Works |
| Delete account | `/api/account/delete` (requires typing DELETE) | Works (guarded; Dangerous-by-design but gated) |
| Upgrade to Pro | only if `PAID_PLANS_ENABLED` (off) → **not rendered**; free-beta shows "Billing" → `/account/billing` | Not rendered (intentional) |
| Manage billing / Cancel / Renew (CheckoutButton etc.) | `/api/checkout`/`/billing/*` | **Not reachable in free beta** (account/billing renders the free-beta branch; `/checkout/plan/*`→`/pricing`). If reached, `/api/checkout`→403 no-op. |
| Footer support mailto | `mailto:$NEXT_PUBLIC_SUPPORT_EMAIL` | Works **iff env email correct** (currently a personal Gmail — verify) |
| Submit beta application (DESKTOP) | `/api/accounts/register` (local) | **Works-but-confusing / stale** — see report 05; raw validation error fixed this pass |

## Summary
- **Broken: 0 · Fake: 0 · Placeholder: 0 · Dangerous(ungated): 0** (`href="#"` = 0 confirmed).
- **Owner-only:** the live download link depends on `ATLAS_INSTALLER_URL`.
- **Confusing:** the desktop beta-application form (stale onboarding — report 05).
- **Intentionally absent:** all paid/checkout buttons (free beta).
