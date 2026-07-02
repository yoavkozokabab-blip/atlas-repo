import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Contact — Atlas",
  description: "Get in touch with the Atlas team — support, billing, security, feedback and partnerships."
};

const categories = [
  { t: "Support", d: "Installs, accounts, scanning or anything not working.", subject: "Atlas Support" },
  { t: "Billing", d: "Subscriptions, invoices, trials, refunds and cancellations.", subject: "Atlas Billing" },
  { t: "Security", d: "Report a vulnerability or ask about our security practices.", subject: "Atlas Security Disclosure" },
  { t: "Feedback", d: "Feature requests, bug reports and product ideas.", subject: "Atlas Feedback" },
  { t: "Partnerships", d: "Integrations, teams, and working together.", subject: "Atlas Partnerships" }
];

export default function ContactPage() {
  return (
    <PageShell
      eyebrow="Contact"
      title="Get in touch."
      intro="Pick the topic that fits — every message reaches us directly. We read all of them."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container">
          {SUPPORT_EMAIL ? (
            <p className="lead" style={{ marginBottom: 28 }}>
              Reach us at{" "}
              <a href={supportMailto()} style={{ color: "var(--accent)" }}>{SUPPORT_EMAIL}</a>{" "}
              — or use a topic below to pre-fill the subject.
            </p>
          ) : (
            <div className="note-accent" style={{ marginBottom: 28, maxWidth: 720 }}>
              Use the topic cards below — each opens your email client with a pre-filled subject.
            </div>
          )}

          <div className="grid-3">
            {categories.map((c) => (
              <div className="card" key={c.t}>
                <h3>{c.t}</h3>
                <p>{c.d}</p>
                <p style={{ marginTop: 12 }}>
                  <a href={supportMailto(c.subject)} style={{ color: "var(--accent)" }}>
                    Email {c.t.toLowerCase()}
                  </a>
                </p>
              </div>
            ))}
            <div className="card">
              <h3>macOS / Linux</h3>
              <p>Want Atlas on your platform? Tell us — it helps us prioritize.</p>
              <p style={{ marginTop: 12 }}>
                <a href={supportMailto("Atlas on macOS/Linux")} style={{ color: "var(--accent)" }}>
                  Request a build
                </a>
              </p>
            </div>
          </div>

          <div className="container" style={{ marginTop: 32, padding: 0 }}>
            <Link className="btn btn-primary" href="/download">Download Atlas</Link>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
