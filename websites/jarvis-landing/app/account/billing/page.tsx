import Link from "next/link";
import { currentUser } from "../../_lib/auth";
import { PLANS } from "../../_lib/billing";
import { ManageBillingButton, BillingActionButton, CheckoutButton } from "../../_components/client";

export const dynamic = "force-dynamic";

export default async function BillingPage() {
  const user = await currentUser();
  if (!user) return null;
  const plan = PLANS[user.plan];
  const isPaid = user.plan !== "free";
  const isCanceled = user.planStatus === "canceled" || user.planStatus === "expired";

  return (
    <div>
      <div className="card" style={{ marginBottom: 22 }}>
        <h3 style={{ marginBottom: 14 }}>Billing</h3>
        <dl className="kv">
          <dt>Current plan</dt><dd>{plan.name}</dd>
          <dt>Price</dt><dd>{plan.price === 0 ? "$0" : plan.price === null ? "Custom" : `$${plan.price} / ${plan.interval}`}</dd>
          <dt>Status</dt><dd>{user.planStatus}</dd>
          {user.trialEndsAt ? (<><dt>Trial ends</dt><dd>{new Date(user.trialEndsAt).toLocaleDateString()}</dd></>) : null}
          {user.renewsAt ? (<><dt>Renews</dt><dd>{new Date(user.renewsAt).toLocaleDateString()}</dd></>) : null}
        </dl>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        {!isPaid && <CheckoutButton plan="pro" label="Start Pro trial" />}
        {isPaid && !isCanceled && <ManageBillingButton />}
        {isPaid && !isCanceled && <BillingActionButton action="cancel" label="Cancel subscription" />}
        {isCanceled && <BillingActionButton action="renew" label="Renew subscription" className="btn btn-primary" />}
      </div>

      <div className="note-accent" style={{ maxWidth: 640 }}>
        <b>Test mode:</b> no real charges occur. Checkout simulates a trial locally;
        live Stripe billing activates when keys are configured.
      </div>

      <p className="note" style={{ marginTop: 18 }}>
        To cancel, use the button above or the billing portal. See our{" "}
        <Link href="/refund" style={{ color: "var(--accent)" }}>Refund</Link> and{" "}
        <Link href="/cancellation" style={{ color: "var(--accent)" }}>Cancellation</Link> policies.
      </p>
    </div>
  );
}
