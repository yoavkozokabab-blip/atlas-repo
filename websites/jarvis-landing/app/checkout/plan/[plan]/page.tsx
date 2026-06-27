import { redirect } from "next/navigation";
import { PageShell } from "../../../_components/site";
import { currentUser } from "../../../_lib/auth";
import { PLANS, isPlanId } from "../../../_lib/billing";

export const dynamic = "force-dynamic";

export default async function CheckoutPlanPage({ params }: { params: Promise<{ plan: string }> }) {
  const { plan } = await params;
  if (!isPlanId(plan) || plan === "free") redirect("/pricing");
  if (plan === "team") redirect("/contact");

  // Login gate: send anonymous users to sign in, then back here.
  const user = await currentUser();
  if (!user) redirect(`/login?next=/checkout/plan/${plan}`);

  const p = PLANS[plan];
  return (
    <PageShell eyebrow="Checkout" title={`${p.name} checkout is not enabled`} intro="Download Atlas and start with the free tier.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 560 }}>
          <div className="card" style={{ marginBottom: 22 }}>
            <h3 style={{ marginBottom: 14 }}>{p.name} — ${p.price} / {p.interval}</h3>
            <p>{p.blurb}</p>
            <dl className="kv" style={{ marginTop: 16 }}>
              <dt>Price</dt><dd>${p.price} per {p.interval}</dd>
              <dt>Availability</dt><dd>Paid checkout is not enabled in this build</dd>
              <dt>Start now</dt><dd>Create an account and download the Windows installer</dd>
            </dl>
          </div>
          <a className="btn btn-primary btn-lg" href="/download">Download Atlas</a>
          <div className="note-accent" style={{ marginTop: 22 }}>
            This page does not charge a card or start a paid subscription.
          </div>
        </div>
      </section>
    </PageShell>
  );
}
