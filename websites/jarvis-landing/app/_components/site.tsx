import Link from "next/link";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export function SiteNav() {
  return (
    <header className="nav">
      <div className="container nav-inner">
        <Link className="brand" href="/" aria-label="Atlas home">
          <span className="brand-mark" aria-hidden />
          Atlas
        </Link>
        <nav className="nav-links" aria-label="Primary">
          <Link href="/features">Features</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/docs">Docs</Link>
          <Link href="/faq">FAQ</Link>
        </nav>
        <div className="nav-cta">
          <Link className="btn btn-ghost" href="/login">Sign in</Link>
          <Link className="btn btn-primary" href="/download">Download</Link>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <Link className="brand" href="/" aria-label="Atlas home">
              <span className="brand-mark" aria-hidden /> Atlas
            </Link>
            <p className="muted" style={{ marginTop: 14, fontSize: "0.88rem", maxWidth: "34ch" }}>
              Local-first repository intelligence for AI-assisted engineering.
            </p>
          </div>
          <div>
            <h4>Product</h4>
            <Link href="/features">Features</Link>
            <Link href="/pricing">Pricing</Link>
            <Link href="/download">Download</Link>
            <Link href="/docs">Docs</Link>
          </div>
          <div>
            <h4>Company</h4>
            <Link href="/contact">Contact</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </div>
          <div>
            <h4>Support</h4>
            {SUPPORT_EMAIL ? (
              <a href={supportMailto()}>{SUPPORT_EMAIL}</a>
            ) : (
              <Link href="/contact">Contact us</Link>
            )}
            <Link href="/faq">FAQ</Link>
          </div>
        </div>
        <div className="legal">© 2026 Atlas · Local-first repository intelligence.</div>
      </div>
    </footer>
  );
}

/** Standard page shell for content pages (nav + hero header + footer). */
export function PageShell({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="page-title">{title}</h1>
            {intro ? <p className="lead" style={{ marginTop: 18 }}>{intro}</p> : null}
          </div>
        </section>
        {children}
      </main>
      <SiteFooter />
    </>
  );
}
