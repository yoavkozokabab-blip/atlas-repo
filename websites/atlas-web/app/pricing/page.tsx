import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";

export const metadata: Metadata = {
  title: "Pricing — Atlas",
  description: "Simple pricing for serious codebases. Download Atlas free and start with local-first repository intelligence."
};

export default function PricingPage() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Pricing</p>
            <h1 className="page-title">Simple pricing for serious codebases.</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              Start free, on your machine. Atlas gives you local-first repository
              memory and AI-ready context for Claude, Cursor and Codex.
            </p>
          </div>
        </section>

        <section className="section" style={{ borderTop: "none", paddingTop: 24 }}>
          <div className="container">
            <div className="tier feat" style={{ maxWidth: 440, margin: "0 auto" }}>
              <h3>Free</h3>
              <div className="price">$0</div>
              <ul>
                <li>Local scanning &amp; architecture map</li>
                <li>Change Plans, impact and investigation</li>
                <li>Claude / Codex / Cursor context export</li>
                <li>Your code stays on your machine</li>
              </ul>
              <Link className="btn btn-primary btn-lg" href="/download">Download free</Link>
            </div>
            <div className="note-accent" style={{ marginTop: 28, maxWidth: 560, marginLeft: "auto", marginRight: "auto" }}>
              <b>Note:</b> Atlas is free during the release candidate. Paid plans
              aren&apos;t available yet — no checkout, no payment collection.
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
