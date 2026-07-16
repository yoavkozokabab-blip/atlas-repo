# Atlas billing activation checklist

**Current provider:** Disabled. No production checkout URL, portal session, or
provider mutation may be created.

Before enabling Paddle, all items require recorded evidence:

1. Approved production checkout domain and completed Paddle verification.
2. `BILLING_PROVIDER=paddle`, production host, production-format API key,
   production price ID, webhook secret, notification destination, and legal
   URLs configured only in server-side environment variables.
3. Entitlement/billing migration validated on a disposable database branch,
   reviewed, and applied with a recorded migration version.
4. Raw-body signature, timestamp, replay/idempotency, out-of-order, unknown
   user, cancellation, portal, and reconciliation tests pass in sandbox.
5. Webhook processing, not a checkout redirect, is authoritative for access.
6. `PADDLE_LIVE_CHECKOUT_ENABLED=true` and explicit release-level approval.
7. One controlled live lifecycle test: purchase, upgrade, scheduled cancel,
   immediate cancel, and reconciliation.

Any missing item is a fail-closed `BILLING_NOT_AVAILABLE` outcome and the UI
must remain Pro coming soon.
