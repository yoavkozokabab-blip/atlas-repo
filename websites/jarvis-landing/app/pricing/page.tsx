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
            <div className="tiers">
              <div className="tier">
                <h3>Free</h3>
                <div className="price">$0</div>
                <ul>
                  <li>Local scanning &amp; architecture map</li>
                  <li>One repository</li>
                  <li>Basic Change Plans</li>
                  <li>Claude / Codex / Cursor export</li>
                </ul>
                <Link className="btn btn-ghost" href="/download">Download free</Link>
              </div>
              <div className="tier feat">
                <h3>Pro</h3>
                <div className="price">Coming soon</div>
                <ul>
                  <li>Unlimited repositories</li>
                  <li>Impact analysis &amp; investigation mode</li>
                  <li>AI context compression</li>
                  <li>Architecture risk detection</li>
                  <li>Priority support</li>
                </ul>
                <Link className="btn btn-primary" href="/download">Download Atlas</Link>
                <p className="dl-meta" style={{ marginTop: 10 }}>Paid checkout is not enabled yet</p>
              </div>
              <div className="tier">
                <h3>Team</h3>
                <div className="price">Talk to us</div>
                <ul>
                  <li>Everything in Pro</li>
                  <li>Shared context &amp; seats</li>
                  <li>SSO</li>
                  <li>For engineering teams</li>
                </ul>
                <Link className="btn btn-ghost" href="/contact">Contact sales</Link>
              </div>
            </div>
            <p className="center muted" style={{ marginTop: 24, fontSize: "0.88rem" }}>
              Local-first · Windows installer · your code stays on your machine
            </p>
            <div className="note-accent" style={{ marginTop: 28, maxWidth: 760 }}>
              <b>Note:</b> paid checkout is not enabled in this build. Download Atlas
              and start with the free tier.
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
