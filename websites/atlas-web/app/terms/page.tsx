import type { Metadata } from "next";
import { PageShell } from "../_components/site";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Terms — Atlas",
  description: "Terms of use for Atlas."
};

export default function TermsPage() {
  return (
    <PageShell eyebrow="Legal" title="Terms of Use" intro="The basics of using Atlas on your machine and in your repositories.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>Using Atlas</h2>
          <p>Atlas is a local-first desktop application for repository intelligence. You may use it
            to analyze codebases you own or are authorized to work on.</p>
          <h2>Plans &amp; billing</h2>
          <p>Atlas offers Free, Pro ($19/month) and Team (Coming soon) plans. The Free
            plan is available at no cost. Pro includes a 7-day free trial. Team billing
            is not implemented; contact us if you want to discuss future team access.</p>
          <p>Paid Pro subscriptions are processed by Paddle as Merchant of Record.
            Atlas does not store your payment details. You can cancel anytime from
            the billing portal; access continues to the end of the paid period.</p>
          <h2>Acceptable use</h2>
          <ul>
            <li>Don&apos;t use Atlas to violate the law or third-party rights.</li>
            <li>Don&apos;t attempt to circumvent licensing or resell access.</li>
          </ul>
          <h2>Disclaimer</h2>
          <p>Atlas provides analysis and recommendations to assist engineering work. You remain
            responsible for reviewing changes before shipping them.</p>
          <h2>Contact</h2>
          <p>Questions: <a href={supportMailto("Atlas Terms")}>{SUPPORT_EMAIL || "contact us"}</a>.</p>
          <p className="note">Last updated: 2026-07-09.</p>
        </div>
      </section>
    </PageShell>
  );
}
