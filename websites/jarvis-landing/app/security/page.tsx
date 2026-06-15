import { PageShell } from "../_components/site";

export const metadata = { title: "Security — Atlas" };

export default function SecurityPage() {
  return (
    <PageShell eyebrow="Security" title="Security at Atlas" intro="Draft — full security page lands in the legal/security pass.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>Local-first by design</h2>
          <p>Your source code is scanned and analyzed on your machine. Atlas does not upload your
            repository. Only the compact context you choose to copy leaves your device.</p>
          <h2>Accounts</h2>
          <p>Passwords are stored only as salted hashes (never plaintext). Sessions use signed,
            httpOnly cookies. Admin access is role-based.</p>
          <h2>Reporting a vulnerability</h2>
          <p>Email us via the Contact page&apos;s Security category. We aim to acknowledge quickly.</p>
          <p className="note">This is a product/security draft and will be reviewed before public
            launch.</p>
        </div>
      </section>
    </PageShell>
  );
}
