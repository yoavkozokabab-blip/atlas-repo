import type { Metadata } from "next";
import { PageShell } from "../_components/site";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Terms — Atlas",
  description: "Terms of use for Atlas."
};

export default function TermsPage() {
  return (
    <PageShell eyebrow="Legal" title="Terms of Use" intro="The basics of using Atlas. A full agreement will be published ahead of public launch.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>Using Atlas</h2>
          <p>Atlas is a local-first desktop application for repository intelligence. You may use it
            to analyze codebases you own or are authorized to work on.</p>
          <h2>Plans &amp; billing</h2>
          <p>The Free plan is available at no cost. Pro is billed monthly; the trial is provided
            without a card and converts to paid only if you choose to subscribe. You can cancel
            anytime from the billing portal; access continues to the end of the paid period.</p>
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
          <p className="note">Last updated: 2026-06-13. This is a preliminary summary, not the final agreement.</p>
        </div>
      </section>
    </PageShell>
  );
}
