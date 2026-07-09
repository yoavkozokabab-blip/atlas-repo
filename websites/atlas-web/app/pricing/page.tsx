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
              Start free, then upgrade to Pro when you want unlimited repositories,
              sync and priority indexing. Atlas stays local-first: repository
              indexing happens on your machine.
            </p>
          </div>
        </section>

        <section className="section" style={{ borderTop: "none", paddingTop: 24 }}>
          <div className="container">
            <div className="tiers">
              <div className="tier">
                <h3>Free</h3>
                <div className="price">$0</div>
                <p className="note">Unlimited time.</p>
                <ul>
                  <li>Repository scanning</li>
                  <li>Local dependency graph</li>
                  <li>MCP integration</li>
                  <li>Claude Code</li>
                  <li>Cursor</li>
                  <li>Codex</li>
                  <li>Ask Atlas</li>
                  <li>Debug</li>
                  <li>Impact analysis</li>
                  <li>Plan Change workflows</li>
                  <li>Dependency map</li>
                </ul>
                <Link className="btn btn-primary btn-lg" href="/download">Start free</Link>
              </div>

              <div className="tier feat">
                <p className="badge ok" style={{ marginBottom: 10 }}>Most Popular</p>
                <h3>Pro</h3>
                <div className="price">$19<small>/month</small></div>
                <p className="note">7-day free trial.</p>
                <ul>
                  <li>Everything in Free</li>
                  <li>Unlimited repositories</li>
                  <li>Unlimited indexing</li>
                  <li>Cloud account sync</li>
                  <li>Snapshot history</li>
                  <li>Advanced search</li>
                  <li>Priority indexing</li>
                  <li>Priority workflow improvements</li>
                  <li>Priority support</li>
                </ul>
                <Link className="btn btn-primary btn-lg" href="/checkout/plan/pro">Start 7-day free trial</Link>
                <div className="note-accent" style={{ marginTop: 18 }}>
                  <p style={{ margin: 0 }}><b>Secure payments powered by Paddle.</b></p>
                  <p style={{ margin: "6px 0 0" }}>Atlas never stores your payment details.</p>
                </div>
              </div>

              <div className="tier">
                <p className="badge muted" style={{ marginBottom: 10 }}>Coming Soon</p>
                <h3>Team</h3>
                <div className="price">Coming soon</div>
                <p className="note">For teams that want shared Atlas workflows.</p>
                <ul>
                  <li>Contact us</li>
                  <li>No Team subscription billing today</li>
                  <li>Designed for shared team workflows</li>
                </ul>
                <Link className="btn btn-ghost btn-lg" href="/contact">Contact us</Link>
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
