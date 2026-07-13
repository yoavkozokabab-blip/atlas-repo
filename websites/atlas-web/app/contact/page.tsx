import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";
import { GITHUB_URL, HELLO_EMAIL, SECURITY_EMAIL, SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Contact — Atlas",
  description: "Get in touch with the Atlas team — support, billing, security, feedback and partnerships."
};

function mailto(email: string, subject: string) {
  return `mailto:${email}?subject=${encodeURIComponent(subject)}`;
}

const categories = [
  { t: "Support", d: "Installs, accounts, scanning or anything not working.", href: supportMailto("Atlas Support"), label: SUPPORT_EMAIL },
  { t: "Hello", d: "Product questions, partnerships and general notes.", href: mailto(HELLO_EMAIL, "Atlas"), label: HELLO_EMAIL },
  { t: "Security", d: "Responsible disclosure and security questions.", href: mailto(SECURITY_EMAIL, "Atlas Security Disclosure"), label: SECURITY_EMAIL },
  { t: "GitHub", d: "Issues, releases and source-visible project activity.", href: GITHUB_URL, label: "Open GitHub", external: true },
];

export default function ContactPage() {
  return (
    <PageShell
      eyebrow="Contact"
      title="Get in touch."
      intro="Support, product questions, security disclosures and GitHub links for Atlas."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container">
          <p className="lead" style={{ marginBottom: 28 }}>
            Expected response time: one to two business days. Security reports are prioritized.
          </p>

          <div className="grid-3">
            {categories.map((c) => (
              <div className="card" key={c.t}>
                <h3>{c.t}</h3>
                <p>{c.d}</p>
                <p style={{ marginTop: 12 }}>
                  <a
                    href={c.href}
                    target={c.external ? "_blank" : undefined}
                    rel={c.external ? "noreferrer" : undefined}
                    style={{ color: "var(--accent)" }}
                  >
                    {c.label}
                  </a>
                </p>
              </div>
            ))}
          </div>

          <div className="container" style={{ marginTop: 32, padding: 0 }}>
            <Link className="btn btn-primary" href="/download">Download Atlas</Link>
            <Link className="btn btn-ghost" href="/pricing" style={{ marginLeft: 10 }}>See pricing</Link>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
