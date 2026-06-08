# Phase 193 — Access State UX Redesign

## Problem

After a **successful** login, users could be dumped on a blocking, full-screen
"Access inactive" / "Beta access pending" wall (the pre-login `acc-panel-state`
panel). It looked like an authentication failure even though sign-in had
succeeded, blocked the entire product, and gave the impression Atlas was broken.

### Root cause

`get_account_state()` computed a single `authenticated` flag:

```python
authenticated = bool(token and user and license_status.get("valid") is True)
```

A **pending** beta user logs in successfully (the accounts service issues a
token), but `/user/license` returns `valid: false`. So `authenticated` was
`false`, and `_syncLayoutFromState()` routed the user to the pre-login blocking
panel — a dead end. Worse, `expired`/rejected users were refused at login with a
`403`, never reaching any in-app explanation.

## Solution

A signed-in user is now **never** stranded on a pre-login wall. Every account
state resolves to a useful in-app dashboard rendered *inside the app shell*, so
Atlas branding and navigation stay visible.

| Account state | Where they land |
|---|---|
| active | Product home (+ dashboard header) |
| beta | Product home (+ dashboard header) |
| pending | In-app **"Application received"** dashboard |
| inactive / expired | In-app **"Account not active"** dashboard |
| rejected | In-app **"Application not approved"** dashboard |
| suspended / banned | Hard login block (punitive — unchanged) |
| admin / superadmin | Product home + **Admin Console** in the user menu |

### Before → After

**Before:** login success → `authenticated == false` for pending →
`showAccountScreen('blocked')` → full-screen pre-login panel reading
"Beta access pending" / "Access inactive", no branding context, product
inaccessible, only "Back to sign in" / "Sign out".

**After:** login success → app shell revealed (topbar + nav) →
`view-status` dashboard tailored to the account state, with a clear title,
progress steps, ETA/reason, **Refresh account status**, **Contact support**,
and **Sign out**. Active/beta users get a real Home dashboard (welcome, status,
plan, repository, recent analyses, quick actions). Inactive/expired/rejected
users can log in (token issued) instead of hitting a `403`.

## Changes

### Backend — accounts service (`accounts_service/`)
- `models.py`: added `inactive` and `rejected` to `USER_STATUSES`.
- `routers/auth.py`: `BLOCKED_STATUSES` reduced to `("suspended", "banned")`.
  Non-punitive inactive states (`pending`/`inactive`/`expired`/`rejected`) now
  receive a token at login so the desktop app can route them to a dashboard.
- `routers/users.py`: `/user/license` returns `valid: false` with a precise
  `status` (`pending`/`inactive`/`expired`/`rejected`) and message for each
  non-active state, even if a stale license row is still "active".
- `routers/admin.py`: rejecting an application now sets `status = "rejected"`
  (was `"expired"`) so the UI can show a tailored "not approved" page.
- `schemas.py`: `AdminUserUpdate.status` literal extended with
  `inactive`/`rejected`.

### Desktop client
- `jarvis_desktop/accounts_client.py`: `get_account_state()` now also returns
  `signed_in = bool(token and user)` — a session signal distinct from full
  `authenticated` access.
- `jarvis_desktop/static/atlas_accounts.js`:
  - `_accountStatus()` taxonomy (active/beta/pending/inactive/rejected/blocked).
  - `_renderStatusDashboard()` + `STATUS_DASH` spec for the three dashboards.
  - `_renderHomeDashboard()` (welcome, status/plan pills, repository, recent
    analyses, quick actions).
  - `_syncLayoutFromState()` / `doLogin()` route signed-in-but-inactive users
    into the in-app `view-status` dashboard instead of the blocking panel.
  - `requireAccess()` keeps signed-in users on their status dashboard rather
    than bouncing them to a pre-login wall.
  - `_updateAccountChip()` / `_populateProfile()` / `openAccountScreen()` treat
    `signed_in` (not just `authenticated`) as "in app", so the user menu
    (Account / Admin Console / Sign out) is always available.
  - New public API: `refreshStatus()` (re-check server without logout/login),
    `reapply()`, `accountStatus()`, `isSignedIn()`.
- `jarvis_desktop/static/index.html`: new `#view-status` dashboard (inside the
  app shell) + `#homeDashboard` header with quick actions.
- `jarvis_desktop/static/styles.css`: styles for the home dashboard, status
  pills, quick actions, and the status dashboards (same Atlas visual language).

## Verification

### Live UI (all six account states screenshotted)
Driven through the real `index.html` by stubbing `/api/accounts/state`:

- **pending** → `view-status`, body `app-authenticated` (not the auth wall),
  title "Application received", steps + ETA + Refresh/Support/Sign out.
- **inactive** → "Account not active" with reason, Refresh/Support/Sign out.
- **rejected** → "Application not approved", review-complete step,
  Reapply (coming soon) shown, Refresh hidden.
- **active** → Home dashboard: "Welcome back, dev", Active + Pro pills,
  repository "acme-api · 842 files", recent analyses, all four quick actions.
- **beta** → Home dashboard with Beta access + Beta pills.
- **admin** → Home dashboard + user menu showing **Admin Console**
  (`isAdmin == true`); normal user has it hidden (`adminMenuHidden == true`).

Navigation + Atlas branding remain visible on every status dashboard.

### Tests
- New: `jarvis_desktop/tests/test_phase193_access_state_ux.py` — static frontend
  contract (status view, home dashboard, quick actions, dashboard titles,
  routing, styles) + accounts-service behavior (pending/inactive/rejected log in
  with `valid: false` license; suspended/banned still `403`; active is valid).
- Updated: `accounts_service/tests/test_phase191_registration_reliability.py`
  (reject now yields `rejected`).
- Regression run: `accounts_service/tests`, `test_phase186*`, `test_phase188`,
  `test_phase191`, `test_phase192`, `test_phase193_admin_console` all green.

## Commit

`<filled in on commit>`
