import { redirect } from "next/navigation";
import { PageShell } from "../../../_components/site";
import { currentUser } from "../../../_lib/auth";
import { CheckoutButton } from "../../../_components/client";
import { PLANS, isPlanId, proCheckoutReady } from "../../../_lib/billing";
import { supportMailto } from "../../../_config";

export const dynamic = "force-dynamic";

export default async function CheckoutPlanPage({ params }: { params: Promise<{ plan: string }> }) {
  const { plan } = await params;
  if (!isPlanId(plan) || plan === "free") redirect("/pricing");
  if (plan === "team") redirect("/contact");

  const user = await currentUser();
  if (!user) redirect(`/login?next=/checkout/plan/${plan}`);

  const p = PLANS[plan];
  const ready = proCheckoutReady();
  return (
    <PageShell eyebrow="Checkout" title={`${p.name} checkout`} intro="Paddle handles paid subscriptions as Merchant of Record.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 600 }}>
          <div className="card" style={{ marginBottom: 22 }}>
            <h3 style={{ marginBottom: 14 }}>{p.name} - ${p.price} / {p.interval}</h3>
            <p>{p.blurb}</p>
            <dl className="kv" style={{ marginTop: 16 }}>
              <dt>Price</dt><dd>$19 per month</dd>
              <dt>Trial</dt><dd>7 days</dd>
              <dt>Payment processor</dt><dd>Paddle Merchant of Record</dd>
              <dt>Status</dt><dd>{ready ? "Checkout configured" : "Checkout not configured"}</dd>
            </dl>
          </div>
          {ready ? (
            <CheckoutButton plan="pro" label="Start 7-day trial" />
          ) : (
            <div className="note-accent">
              Pro checkout is not configured on this deployment. Set Paddle environment variables before accepting paid subscriptions, or <a href={supportMailto("Atlas Pro")}>contact Atlas</a>.
            </div>
          )}
        </div>
      </section>
    </PageShell>
  );
}
