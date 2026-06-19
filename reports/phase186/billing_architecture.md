# BILLING ARCHITECTURE (Phase 186B)

**Date:** 2026-06-20 · **Execution status:** design = **PASS**; live subscription evidence = **BLOCKED** (needs a Stripe account + keys + a deployed webhook endpoint, which this environment cannot provide). No "real subscription" will be claimed without a recorded Stripe dashboard event.

## 1. Audit: every billing implementation found

| Location | What it is | Verdict |
|---|---|---|
| `websites/jarvis-landing/app/_lib/billing.ts` | **STUB.** `startCheckout` deliberately falls through to a local trial; `liveChargesEnabled()` branch is inert (`:37-41`). `billingPortal`/`cancel`/`renew` mutate local state, no Stripe. | **This is the shipping path. It charges no one.** |
| `websites/jarvis-landing/app/api/{checkout,billing/portal,billing/cancel}/route.ts` | Thin wrappers over the stub. | Keep the routes; replace the stub body. |
| `~/jarvis_landing/api/{checkout.js,portal.js,stripe/webhook.js,license.js,_lib/stripe.js}` | **REAL Stripe** (old static site). Proper `stripe.webhooks.constructEvent` signature verification, trial-without-card checkout, status→entitlement mapping, `users` upsert. | **Reference implementation.** Email-keyed, no idempotency, wrong schema. Port the *logic*, then **delete this site**. |
| `accounts_service/billing_sync.py` | Desktop-side license/plan sync. | Becomes a read of canonical state (via 186A `/me`), not a billing authority. |

**Decision: ONE implementation** — port the proven `~/jarvis_landing/api/stripe/webhook.js` logic into the Next.js app, keyed to **authenticated users** (not email), writing the canonical Supabase `users` row. Delete the stub bodies and the old site.

## 2. License model — what is purchased

| Plan | Price | Entitlement | Stripe |
|---|---|---|---|
| **Free** | $0 | Local scanning, 1 repo, basic Change Plans | no subscription |
| **Atlas Pro** | **$29/mo, 7-day trial, no card up front** | Unlimited repos, impact analysis, investigation, risk detection, all MCP exports | one `price` (`STRIPE_PRICE_ID`), `mode: subscription`, `trial_period_days: 7`, `payment_method_collection: 'if_required'` |
| **Team** | contact sales | Pro + seats/SSO (post-launch) | n/a at launch → CTA to `/contact` |

Entitlement source of truth = `users.plan` + `users.plan_status` (already in `0001_init.sql`). The desktop reads it via 186A `/me`. **One entitlement check**, server-side.

## 3. Flow

```
/pricing → POST /api/checkout (authed)
  → stripe.checkout.sessions.create({
        mode:'subscription', line_items:[{price: STRIPE_PRICE_ID}],
        subscription_data:{trial_period_days:7},
        payment_method_collection:'if_required',
        customer: user.stripeCustomerId ?? undefined,
        customer_email: user.email,
        client_reference_id: user.id,          // ← key the webhook to the AUTHED user
        success_url: /billing/success?...  cancel_url: /billing/cancelled })
  → redirect to session.url
Stripe → POST /api/stripe/webhook (raw body, signature-verified)
  → checkout.session.completed | customer.subscription.updated/deleted | invoice.payment_failed
  → store.update(user.id, { plan, planStatus, stripeCustomerId, renewsAt, trialEndsAt })
Manage → POST /api/billing/portal → stripe.billingPortal.sessions.create({customer}) → redirect
```

## 4. Webhook hardening (the gaps in the reference code)

The old `webhook.js` verifies signatures correctly but **must add**:

1. **Signature verification** — keep `stripe.webhooks.constructEvent(rawBody, sig, STRIPE_WEBHOOK_SECRET)`. In Next.js App Router read the raw body with `await req.text()` (do **not** `req.json()` first). *(constructEvent also enforces Stripe's default 5-minute timestamp tolerance → baseline replay protection.)*
2. **Idempotency / replay** — add a `stripe_events(event_id text primary key, type text, received_at timestamptz)` table; at the top of the handler `insert` the `event.id` and if it conflicts, return `200` without reprocessing. This makes Stripe redelivery safe.
3. **Map by `client_reference_id`/`stripe_customer_id`, not email** — look up the user by id (from checkout) or by `stripe_customer_id` (for subscription events), falling back to email only as a last resort.
4. **Schema reconcile** — add `stripe_subscription_id text` to `users` (migration `0004`); map Stripe status → `plan_status`: `trialing→trialing`, `active→active`, `past_due→past_due` (still entitled), `canceled/unpaid/incomplete_expired→canceled`. Set `plan='pro'` when entitled, `'free'` when not.
5. **Always 200 on success, 400 only on bad signature, 500 on handler error** (so Stripe retries real failures, not signature rejects).

## 5. UX surfaces (already exist as pages — wire to real state)

`/account/billing` shows `plan` + `planStatus` + `renewsAt`/`trialEndsAt`; **Upgrade** → `/api/checkout`; **Manage/Cancel** → `/api/billing/portal` (Stripe-hosted portal handles cancel/downgrade/card update — less code to own). `/billing/success` confirms; `/billing/cancelled` returns to pricing.

## 6. Test plan (Stripe TEST mode)

Run with test keys + `stripe listen --forward-to localhost:3000/api/stripe/webhook`:
- Purchase: complete Checkout with `4242 4242 4242 4242` → user becomes `trialing`/`active`.
- Cancellation: cancel in portal → `customer.subscription.deleted` → `canceled` → desktop `/me` shows free.
- Upgrade/downgrade: portal plan change → `customer.subscription.updated` synced.
- Expired/declined card: `4000 0000 0000 0341` → `invoice.payment_failed` → state reflects `past_due`.
- Replay: re-send an event via `stripe events resend` → second one is a no-op (idempotency table).

## 7. PASS / FAIL / BLOCKED

| Task | Status |
|---|---|
| Audit all billing code; pick one impl | **PASS** (§1) |
| License model + entitlement logic | **PASS (design)** (§2) |
| Checkout / portal / webhook design | **PASS (design)** (§3–4) |
| Signature / replay / idempotency | **PASS (design)**; reference verifies signatures, idempotency table specified | 
| Implement real Stripe code | **NOT DONE** — deliberately not committing unverifiable money-path code to the monetization branch without test-mode validation. |
| Real subscription created / cancelled / webhook processed | **BLOCKED** — no Stripe account/keys/endpoint here. See `stripe_verification_report.md`. |
