# STRIPE VERIFICATION REPORT (Phase 186B)

**Date:** 2026-06-20

## Brutal-honesty statement
The phase asks for evidence of a **real subscription created, a real subscription cancelled, and a real webhook processed.** I **cannot** produce that evidence in this environment. Doing so requires:
- a Stripe account + secret/publishable keys + a `STRIPE_PRICE_ID`,
- a `STRIPE_WEBHOOK_SECRET` and a publicly reachable (or `stripe listen`-tunnelled) endpoint,
- the billing code from `billing_architecture.md` actually implemented.

None of those exist yet. **I will not fabricate Stripe dashboard screenshots or claim a subscription that did not happen.**

## What IS verified (by reading code / running locally)

| Item | Status | Evidence |
|---|---|---|
| Shipping checkout charges nothing | **CONFIRMED** | `_lib/billing.ts:30-57` — stub grants a local trial; `liveChargesEnabled()` branch is inert. |
| No webhook handler in the deployed site | **CONFIRMED** | repo search: a handler exists only in `~/jarvis_landing/api/stripe/webhook.js` + `node_modules`. |
| A correct reference webhook exists | **CONFIRMED** | old site uses `stripe.webhooks.constructEvent(raw, sig, secret)` with `bodyParser:false` — signatures *are* verified there. |
| Env scaffolding for live mode is present | **CONFIRMED** | `_lib/config.ts` exposes `hasStripe`, `paymentsMode` (stub/test/live), `liveChargesEnabled()`. |
| The build is deployable | **CONFIRMED** | `npm run build` passes (this session). |

## What is NOT verified (BLOCKED)

| Item | Status | Why |
|---|---|---|
| Real checkout session created | **BLOCKED** | needs Stripe keys + `STRIPE_PRICE_ID`. |
| Subscription becomes active/trialing | **BLOCKED** | needs a completed test checkout. |
| Webhook signature validation against live events | **BLOCKED** | needs `STRIPE_WEBHOOK_SECRET` + endpoint. |
| Replay protection / idempotency | **BLOCKED + NOT IMPLEMENTED** | idempotency table (`stripe_events`) is specified, not built. |
| Cancellation / upgrade / downgrade / failed-card flows | **BLOCKED** | needs Stripe test-mode runs (cards `4242…`, `4000…0341`). |

## Exact steps for the owner to reach PASS

1. Create the Stripe product + a $29/mo recurring price; copy `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`. (Repo already has `jarvis_landing/scripts/create-stripe-product.mjs` as a starting point.)
2. Implement the code in `billing_architecture.md` §3–4 (checkout route, webhook route, migrations `0004`+`stripe_events`).
3. `stripe listen --forward-to localhost:3000/api/stripe/webhook` → copy the signing secret to `STRIPE_WEBHOOK_SECRET`; set `PAYMENTS_MODE=test`.
4. Run the §6 test matrix; capture the Stripe dashboard + DB rows as evidence.
5. Only then set live keys + `PAYMENTS_MODE=live`.

**Verdict: Billing is NOT launch-ready. It is a hard blocker for any paid launch.** A free launch can proceed by hiding all paid CTAs (see roadmap M3.0).
