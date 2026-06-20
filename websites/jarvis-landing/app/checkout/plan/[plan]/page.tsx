import { redirect } from "next/navigation";
import { PageShell } from "../../../_components/site";
import { currentUser } from "../../../_lib/auth";
import { PLANS, isPlanId } from "../../../_lib/billing";
import { CheckoutButton } from "../../../_components/client";
import { PAID_PLANS_ENABLED } from "../../../_config";

export const dynamic = "force-dynamic";

export default async function CheckoutPlanPage({ params }: { params: Promise<{ plan: string }> }) {
  const { plan } = await params;
  // Free beta (Phase 186A): there is no checkout. Send anyone here back to pricing.
  if (!PAID_PLANS_ENABLED) redirect("/pricing");
  if (!isPlanId(plan) || plan === "free") redirect("/pricing");
  if (plan === "team") redirect("/contact");

  // Login gate: send anonymous users to sign in, then back here.
  const user = await currentUser();
  if (!user) redirect(`/login?next=/checkout/plan/${plan}`);

  const p = PLANS[plan];
  return (
    <PageShell eyebrow="Checkout" title={`Start ${p.name}`} intro="Review your plan before continuing.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 560 }}>
          <div className="card" style={{ marginBottom: 22 }}>
            <h3 style={{ marginBottom: 14 }}>{p.name} — ${p.price} / {p.interval}</h3>
            <p>{p.blurb}</p>
            <dl className="kv" style={{ marginTop: 16 }}>
              <dt>Price</dt><dd>${p.price} per {p.interval}</dd>
              <dt>Trial</dt><dd>{p.trialDays}-day free trial — no card required</dd>
              <dt>Billing</dt><dd>Monthly, starting after the trial</dd>
              <dt>Cancellation</dt><dd>Cancel anytime; access continues to period end</dd>
            </dl>
          </div>
          <CheckoutButton plan={plan} label={`Start ${p.trialDays}-day trial`} className="btn btn-primary btn-lg" />
          <div className="note-accent" style={{ marginTop: 22 }}>
            <b>Test mode:</b> this does not charge a card. It starts a simulated trial; live Stripe
            checkout activates when billing keys are configured.
          </div>
        </div>
      </section>
    </PageShell>
  );
}
