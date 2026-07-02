# 02 — Beta Gates (every place access could be blocked)

**Date:** 2026-06-20. Searched: approve/approved/approval/pending/beta/invite/allowlist/BETA_MODE/BETA_ALLOWLIST/application/waitlist/status across the repo.

## A. Website — `betaApproved` (THE production gate) — **REMOVED this change**
- File: `websites/jarvis-landing/app/_lib/auth.ts`, Function: `betaApproved` (was lines 147–151).
- **Was:** `if betaMode==="open" return true; if admin return true; return betaAllowlist.includes(email)` → in `BETA_MODE=invite`, non-allowlisted users got `approved:false` + "not approved for the Atlas beta yet."
- Triggered by: `entitlement()`, returned by `/api/auth/desktop/{register,login,me}` → read by the desktop.
- **Now:** `return u.status !== "suspended"` — **open access**. `BETA_MODE`/`BETA_ALLOWLIST` no longer gate anything. `entitlement.message` is always `null`.

## B. Website config — `BETA_MODE` / `BETA_ALLOWLIST` — **now inert**
- File: `app/_lib/config.ts:33–37` — still readable but **no longer consulted by `betaApproved`**. Setting `BETA_MODE=invite` in Vercel now has **no effect** on access. (Left in place to avoid churn; safe to delete later.)

## C. Website status block — **kept (intended)**
- `loginUser` (auth.ts:119) and `currentUser` (auth.ts:70,139): block `status === "suspended"`. **Kept** — suspension/ban is the only access control, per the mandate.

## D. Local `accounts_service` (FastAPI/SQLite) — **legacy, dev-only, NOT the production path**
- File: `accounts_service/routers/auth.py:146` — register creates `status="pending"`; invite_code → `status="beta"` (160–166). Login blocks `BLOCKED_STATUSES=("suspended","banned")` (36); pending users get a token but a "pending" license.
- **This is the legacy local approval workflow.** The **packaged/frozen desktop does NOT use it** (`accounts_client.auth_mode()` → `website` when frozen). It is reachable only in source/dev mode (`ATLAS_AUTH_MODE=local`/`ATLAS_DEV=1`/unfrozen).
- **Not changed** (it is not the production identity; modifying it churns the legacy suite without affecting real users). To fully retire it, make the desktop default to website unconditionally — a scoped follow-up.

## E. Desktop UI — `jarvis_desktop/static/atlas_accounts.js`
- Contains "Beta access pending" / "waiting for beta approval" dashboards keyed on `status === "pending"` (lines 32, 263–280, 333–375).
- **Dead path in production:** the website never returns `status:"pending"` and now always returns `approved:true`, so `_web_license_from_result` yields `valid:true` (beta_active) → these pending dashboards never trigger for website-mode (production) users. (They could show only in local/dev mode.)

## F. Waitlist — `public.waitlist` table + `/api/waitlist`
- A marketing signup list, **not an access gate** (`betaApproved` does not consult it). No change needed.

## Summary of what blocks access AFTER this change
- **Production (website + frozen desktop):** only `status === "suspended"`. No approval, no allowlist, no invite, no waitlist gating. ✅
- **Local/dev accounts_service:** still has `pending` (legacy, not production) — documented, not the real path.
