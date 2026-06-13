# Phase 197 User Funnel

Generated: 2026-06-13

## Result

Status: PRIVATE BETA PARTIAL, PAID FUNNEL BLOCKED

## Flow A - Private Beta Invite

Target:
- Waitlist signup
- Admin review
- Invite sent
- User installs Atlas
- User registers
- Beta approved manually

Current state:
- Landing waitlist API and waitlist admin exist.
- Prior Phase 195E/196 reports indicate the Vercel waitlist URL has stored signups in Supabase.
- Desktop registration and beta approval flows exist in accounts service.
- Desktop admin can approve pending applications and grant beta.

Known limitations:
- Current live deployment could not be reverified from this sandbox.
- Prior production reports show `SITE_URL` was misconfigured to localhost.
- Prior production reports show email delivery was not configured.
- Manual invite/approval remains the fallback.

Verdict:
- Suitable only for supervised private beta after production waitlist health is rechecked by the operator.

## Flow B - Paid User

Target:
- Landing page
- Pricing
- Stripe checkout
- Payment/subscription
- License active
- User installs Atlas
- Desktop recognizes active license

Current state:
- Pricing UI does not expose a paid checkout.
- No checkout endpoint exists.
- No live product/price was verified.
- No webhook endpoint exists.
- No Supabase paid-user subscription schema exists.
- Desktop license lifecycle now understands paid inactive states, but there is no Stripe-to-license activation path.

Verdict:
- Blocked.

## Manual Activation Fallback

Manual paid/pro activation is possible in the accounts admin path after this phase:
- Admin can set `plan=pro`.
- Admin can set `license_status=active`, `trial`, `past_due`, `canceled`, `cancelled`, `expired`, or `suspended`.
- Admin changes are audit logged.

This is an operator fallback only. It is not a verified paid Stripe funnel.

## Remaining Blockers

- Implement checkout.
- Implement webhook.
- Verify live Stripe product/price.
- Apply paid schema/state sync.
- Reverify production waitlist and email environment.

