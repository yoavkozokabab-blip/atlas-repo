import { PageShell } from "../_components/site";

export const metadata = { title: "Refund Policy — Atlas" };

export default function RefundPage() {
  return (
    <PageShell eyebrow="Legal" title="Refund Policy" intro="Draft — full policy lands in the legal pass.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <p>Atlas offers a free tier and a free Pro trial so you can evaluate before paying.
            Subscription fees are generally non-refundable except where required by law; contact
            us within a reasonable window for billing issues and we&apos;ll make it right.</p>
          <p className="note">This is a product/legal draft and will be reviewed by a qualified
            lawyer before public launch. See also Cancellation and Terms.</p>
        </div>
      </section>
    </PageShell>
  );
}
