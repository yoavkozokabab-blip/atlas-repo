# Phase 197 Current State Audit

Generated: 2026-06-13

Scope:
- `C:\jarvis_landing`
- `C:\J.A.R.V.I.S\local_jarvis`

No code changes were made before this audit artifact.

## Executive Summary

Atlas is not live-commercial ready today.

The private-beta intake path has prior evidence of working on the Vercel production URL, but the current checkout does not contain a live Stripe checkout endpoint, Stripe webhook endpoint, paid-license Supabase schema, paid-user admin operations, or desktop paid-license lifecycle enforcement for all required states.

The most serious current-state blocker is repository hygiene in `local_jarvis`: `.env` is tracked by git. I did not read or print the file contents. A tracked secret file prevents a safe live monetization verdict until it is removed from version control and any exposed secrets are rotated.

## Repository State

### `C:\jarvis_landing`

Branch:
- `main`
- Ahead of `origin/main` by 9 commits.

Remote:
- `origin https://github.com/yoavkozokabab-blip/atlas-website.git`

Working tree:
- Dirty: 19 files reported by `git status --porcelain`.
- Modified tracked files include `index.html`, `css/style.css`, `js/app.js`, `js/canvas.js`, and `js/demo.js`.
- Untracked files include new docs/reports/scripts/screenshots such as `docs/CONVERSION_AUDIT.md`, `docs/JOSHUA_FEEDBACK_REPORT.md`, `reports/admin_setup.md`, `reports/deployment_readiness.md`, and screenshot/script assets.

Environment/secrets tracking:
- `.env` exists locally and is ignored by `.gitignore`.
- `.env.local` is ignored by `.gitignore`.
- `.env.example` is tracked.
- `.vercel/project.json` exists and is ignored by `.gitignore`.
- `git ls-files .env .env.local .vercel/project.json` did not report tracked secrets.

Vercel project metadata:
- `.vercel/project.json` identifies project name `jarvis_landing`.
- Prior project metadata points to Vercel project id `prj_4jzmksKQe50sxaNEQcw8yM2wL2VG`.

### `C:\J.A.R.V.I.S\local_jarvis`

Branch:
- `monetization-v1`

Remote:
- `origin https://github.com/yoavkozokabab-blip/atlas-repo.git`

Working tree:
- Very dirty: 2,987 tracked changes reported with `git status --porcelain -uno`.
- Large numbers of deleted vendored/package files are present under `.phase152_packaging_lib` and `accounts_service/.lib`.
- Runtime data, `dist/Atlas`, desktop static files, accounts routes, reports, and tests also have local changes.
- `C:\J.A.R.V.I.S\local_jarvis\.git\index.lock` exists, so git commit operations are currently blocked until the lock is safely resolved.

Environment/secrets tracking:
- `.env` is tracked by git.
- `.env.example` is tracked by git.
- `git check-ignore .env .env.local .env.example` returned no ignore match.
- I did not open or print `.env`.
- This is a live-readiness blocker and may require secret rotation depending on file history and contents.

## Current Production Deployment

Known production URL from prior Phase 195E/196 reports:
- `https://jarvislanding-brown.vercel.app`

Prior reports state:
- `GET /api/health` previously returned HTTP 200 with `ok:true`, `runtime:PRODUCTION`, and Supabase status `ok`.
- Supabase project ref was masked as `lkbp***kgjy`.
- `SITE_URL` was previously observed as misconfigured to `http://localhost:3000` in production, breaking verification redirects.
- `RESEND_API_KEY` was previously missing, so email delivery was disabled or degraded.

Current live HTTP verification:
- Attempted read-only HTTPS probes to `/api/health`, `/api/admin/signups`, and `/api/checkout`.
- Sandbox network/TLS failed with `The underlying connection was closed`.
- Escalated read-only curl approval timed out twice.
- Therefore the current deployment was not live-verified in this phase.

## Current Supabase State

Landing repo schema:
- `supabase/migrations/001_waitlist.sql`
- `supabase/migrations/002_service_role_grants.sql`

Observed schema scope:
- `waitlist_signups`
- `waitlist_rate_limits`

Missing for live monetization:
- paid users table in landing/Supabase
- subscriptions table
- Stripe customer id storage
- Stripe subscription id storage
- Stripe event idempotency table
- payment status lifecycle fields
- license activation records tied to Stripe

The desktop accounts service has local SQLAlchemy tables for users, licenses, devices, sessions, usage, feedback, beta profiles, notifications, and audit logs, but that is separate from the landing repo's Supabase waitlist database.

## Current Stripe Mode

Landing repo:
- No Stripe dependency in `package.json`.
- No `/api/checkout` route.
- No `/api/stripe/webhook` route.
- No billing portal route.
- No Stripe env validation for `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`, or `STRIPE_PRODUCT_ID`.
- `api/_lib/env.js` currently validates Supabase, admin, site URL, and email-related variables only.

Desktop repo:
- `jarvis_desktop/billing/service.py` and `jarvis_desktop/static/billing.js` describe billing as disabled/local preview.
- `jarvis_desktop/billing/plans.py` shows `Pro` as `Coming soon` and `Private beta - join waitlist`.
- No live Stripe checkout/webhook/subscription integration was found in accounts service or desktop billing code.

Current Stripe mode verdict:
- Not configured.
- Live Stripe mode is not verifiable from the current codebase.

## Current Pricing UI

Landing page:
- CTAs are waitlist/private beta oriented.
- Copy includes "Free during beta - pricing shared before anything changes".
- FAQ says beta access is free and post-beta pricing is still being finalized.
- There is no live paid checkout CTA.

Desktop billing UI:
- Free/Pro/Team/Enterprise plan cards exist.
- Pro and Team are marked "Coming soon" or private beta.
- Billing UI explicitly states no checkout and no payment collection in this beta build.

## Current Admin Dashboard

Landing admin:
- `admin.html` plus `api/admin/signups.js` and `api/admin/export.js`.
- Supports waitlist review/export only.
- Auth uses `ADMIN_API_SECRET` bearer auth.
- Does not support paid users, Stripe customer ids, subscriptions, payment status, trial end, next renewal, cancel flags, or manual paid-plan operations.

Desktop accounts admin:
- Supports account/user/device/license/beta operations in `accounts_service/routers/admin.py` and desktop proxy routes.
- Has audit logging and role checks from earlier accounts phases.
- Does not expose Stripe customer/subscription/payment lifecycle data.

## Current Desktop Licensing Integration

Accounts service:
- User statuses: `pending`, `active`, `beta`, `suspended`, `banned`, `expired`, `inactive`, `rejected`.
- License plans: `beta`, `free`, `pro`, `enterprise`.
- License statuses: `active`, `expired`, `suspended`, `cancelled`.

Required Phase 197 states not fully represented:
- `trial`
- `past_due`
- `canceled` spelling

Desktop client:
- `jarvis_desktop/accounts_client.py` caches license state and has offline grace handling.
- Local-state tampering detection exists for signed local state.
- Blocking states include suspended, banned, expired, device revoked, and offline grace expired.

Current gap:
- There is no live Stripe-to-license synchronization path, so the desktop cannot automatically recognize a paid live Stripe subscription.

## Part 1 Blockers

P0:
- `local_jarvis/.env` is tracked by git. Do not proceed to live monetization without removing it from version control and rotating any secrets that may have been committed.
- No live Stripe checkout route exists.
- No live Stripe webhook route exists.
- No Stripe event idempotency or subscription/license persistence exists in the landing/Supabase stack.
- Desktop paid-license activation is not connected to Stripe.

P1:
- Landing production URL could not be live-verified in this sandbox due network/approval timeout.
- Prior reports show production `SITE_URL` was misconfigured to localhost.
- Prior reports show production email sending was not configured.
- Landing admin dashboard is waitlist-only.
- Desktop license model lacks explicit `trial`, `past_due`, and `canceled` states requested for Phase 197.
- `local_jarvis` has a large dirty worktree and an active `.git/index.lock`, preventing clean isolated commits.

## Current-State Verdict

Live commercial readiness:
- NO-GO

Private beta readiness:
- Conditional only. Prior reports indicate waitlist/admin/manual beta intake can work, but current deployment was not reverified in this phase and email verification remains a known limitation until production env is corrected.

