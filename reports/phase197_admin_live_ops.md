# Phase 197 Admin Live Operations

Generated: 2026-06-13

## Result

Status: PARTIAL

Accounts admin can manage beta and license lifecycle states. Landing admin remains waitlist-only. Payment operations are not live-ready.

## Current Capabilities

Waitlist:
- View signups: implemented in landing admin.
- Search/filter/export: implemented in landing admin surface.
- Mark invited/notes: not verified as a complete live workflow in this phase.

Users:
- Desktop accounts admin lists users and profile/license/device data.
- Admin can approve beta.
- Admin can suspend, reinstate, ban/unban with existing role controls.
- Admin can force logout.
- Admin can revoke devices.
- Admin can update plan, max devices, expiry, and now license status.

Payments:
- Stripe customer id: not available.
- Subscription status: not available from Stripe.
- Trial end: not wired to Stripe.
- Next renewal: not available.
- Past due flag: account license status now supports `past_due`, but Stripe does not populate it.
- Cancel flag: account license status now supports `canceled`/`cancelled`, but Stripe does not populate it.

Security:
- Existing account admin tests verify non-admin denial and secret-field hiding.
- No passwords, password hashes, refresh hashes, service role keys, or Stripe secret keys are exposed by the changed admin response schemas.

## Verification

Commands run:
- `py -3 -m pytest accounts_service\tests\test_phase197_license_lifecycle.py -q -p no:cacheprovider` - PASS
- `py -3 -m pytest jarvis_desktop\tests\test_phase188_auth_ux.py jarvis_desktop\tests\test_phase193_admin_console.py -q -p no:cacheprovider` - PASS

## Remaining Blockers

- No payment dashboard.
- No Stripe customer/subscription fields in admin.
- No live payment issue queue.
- No live paid checkout/webhook to drive admin payment states.

