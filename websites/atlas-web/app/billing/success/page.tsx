import Link from "next/link";
import { PageShell } from "../../_components/site";

export const dynamic = "force-dynamic";

export default async function BillingSuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ plan?: string }>;
}) {
  const sp = await searchParams;
  const plan = typeof sp.plan === "string" ? sp.plan : "Pro";
  return (
    <PageShell eyebrow="Billing" title="Checkout complete.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 560 }}>
          <div className="card">
            <h3 style={{ marginBottom: 10 }}>Your {plan} checkout completed</h3>
            <p>
              Paddle is processing the subscription update. Your account billing page
              will reflect the latest status after the webhook is received.
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 18 }}>
              <Link className="btn btn-primary" href="/download">Download Atlas</Link>
              <Link className="btn btn-ghost" href="/account/billing">Manage billing</Link>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
