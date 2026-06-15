import Link from "next/link";
import { PageShell } from "../../_components/site";

export const dynamic = "force-dynamic";

export default async function BillingSuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ plan?: string; mode?: string }>;
}) {
  const sp = await searchParams;
  const plan = typeof sp.plan === "string" ? sp.plan : "Pro";
  const isStub = sp.mode === "stub";
  return (
    <PageShell eyebrow="Billing" title="You're all set.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 560 }}>
          <div className="card">
            <h3 style={{ marginBottom: 10 }}>Your {plan} trial has started</h3>
            <p>Download Atlas and your plan features are unlocked. Manage or cancel anytime from
              your billing page.</p>
            {isStub && (
              <p className="note" style={{ marginTop: 12 }}>
                (Test mode — no charge was made. Live billing activates when Stripe is connected.)
              </p>
            )}
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 18 }}>
              <Link className="btn btn-primary" href="/account/downloads">Download Atlas</Link>
              <Link className="btn btn-ghost" href="/account/billing">Manage billing</Link>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
