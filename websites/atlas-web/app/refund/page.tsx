import { PageShell } from "../_components/site";

export const metadata = { title: "Refund Policy — Atlas" };

export default function RefundPage() {
  return (
    <PageShell eyebrow="Legal" title="Refund Policy" intro="A practical, customer-friendly policy for Atlas billing issues.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <p>Atlas offers a Free plan and a 7-day Pro trial so you can evaluate the
            product before a paid subscription continues.</p>
          <p>If you believe you were charged incorrectly, or you experienced a billing
            issue or service issue, Atlas will review refund requests submitted within
            14 days of the charge.</p>
          <p>Refunds are reviewed case by case. This policy does not promise automatic
            refunds, and your local consumer rights may provide additional remedies.</p>
          <p>Paddle acts as Merchant of Record for Atlas paid subscriptions. Paddle may
            process approved refunds and related billing adjustments.</p>
          <p>To request a review, contact support with the email on your Atlas account,
            the charge date and a short description of the issue.</p>
          <p className="note">Last updated: 2026-07-09. See also Cancellation and Terms.</p>
        </div>
      </section>
    </PageShell>
  );
}
