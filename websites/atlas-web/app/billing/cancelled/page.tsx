import Link from "next/link";
import { PageShell } from "../../_components/site";
import InstallerWaitState from "../../_components/InstallerWaitState";

export const dynamic = "force-dynamic";

export default function BillingCancelledPage() {
  return (
    <PageShell eyebrow="Billing" title="Checkout cancelled">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 560 }}>
          <div className="card">
            <p>No problem — nothing was charged. You can start your trial whenever you&apos;re ready.</p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 18 }}>
              <Link className="btn btn-primary" href="/pricing">Back to pricing</Link>
              <InstallerWaitState />
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
