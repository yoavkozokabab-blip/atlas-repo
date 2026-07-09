import { PageShell } from "../_components/site";
import { SECURITY_EMAIL, supportMailto } from "../_config";

export const metadata = { title: "Security — Atlas" };

export default function SecurityPage() {
  return (
    <PageShell eyebrow="Security" title="Security at Atlas" intro="Atlas is built around local-first repository analysis and explicit user-controlled context sharing.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>Local-first architecture</h2>
          <p>Repository indexing runs on your machine. Atlas reads the selected local
            folder, builds a dependency graph and prepares repo-aware answers without
            uploading repository contents during indexing.</p>

          <h2>What stays on-device</h2>
          <ul>
            <li>Repository files read during scanning</li>
            <li>Dependency graph and local repository map</li>
            <li>Ask Atlas, Debug, Impact and change-planning context derived from the scan</li>
            <li>Context packets until you choose to copy or paste them into another tool</li>
          </ul>

          <h2>Authentication</h2>
          <p>Atlas account sessions use signed, httpOnly cookies. Passwords are stored
            as salted hashes, never plaintext. Admin access is role-based and separated
            from normal user account flows.</p>

          <h2>Billing</h2>
          <p>Paid subscription billing is handled by Paddle as Merchant of Record. Atlas
            never stores your payment details.</p>

          <h2>Responsible disclosure</h2>
          <p>If you believe you found a security issue, email{" "}
            <a href={`mailto:${SECURITY_EMAIL}?subject=Atlas%20Security%20Disclosure`}>
              {SECURITY_EMAIL}
            </a>{" "}
            with a description, reproduction steps and any relevant impact. Please do
            not publicly disclose the issue until we have had a reasonable opportunity
            to investigate and respond.</p>
          <p>We aim to acknowledge security reports within two business days.</p>

          <h2>Security contact</h2>
          <p>For non-sensitive security questions, you can also contact us through{" "}
            <a href={supportMailto("Atlas Security")}>support</a>.</p>
          <p className="note">Last updated: 2026-07-09.</p>
        </div>
      </section>
    </PageShell>
  );
}
