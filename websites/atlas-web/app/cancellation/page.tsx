import { PageShell } from "../_components/site";

export const metadata = { title: "Cancellation Policy — Atlas" };

export default function CancellationPage() {
  return (
    <PageShell eyebrow="Legal" title="Cancellation Policy" intro="Draft — full policy lands in the legal pass.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <p>You can cancel your subscription at any time from your billing page or the billing
            portal. Cancellation stops future renewals; your plan stays active until the end of the
            current paid period, after which it reverts to Free.</p>
          <p className="note">This is a product/legal draft and will be reviewed by a qualified
            lawyer before public launch. See also Refund and Terms.</p>
        </div>
      </section>
    </PageShell>
  );
}
