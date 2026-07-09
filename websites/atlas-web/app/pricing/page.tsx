import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";
import { proCheckoutReady } from "../_lib/billing";

export const metadata: Metadata = {
  title: "Pricing - Atlas",
  description: "Atlas pricing: Free local app today, Pro planned at $19/month with Paddle checkout when billing is configured.",
};

export default function PricingPage() {
  const proReady = proCheckoutReady();
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Pricing</p>
            <h1 className="page-title">Simple pricing for repo memory.</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              Start with the local Windows app. Pro billing is powered by Paddle as Merchant of Record when checkout is configured.
            </p>
          </div>
        </section>

        <section className="section" style={{ borderTop: "none", paddingTop: 24 }}>
          <div className="container">
            <div className="tiers">
              <div className="tier">
                <h3>Free</h3>
                <div className="price">$0</div>
                <p className="note">Core local app.</p>
                <ul>
                  <li>Local repository scan</li>
                  <li>Ask Atlas</li>
                  <li>MCP integration</li>
                  <li>Impact</li>
                  <li>Debug</li>
                  <li>Plan Change</li>
                  <li>Map</li>
                </ul>
                <Link className="btn btn-primary btn-lg" href="/download">Download Atlas</Link>
              </div>

              <div className="tier feat">
                <p className="badge ok" style={{ marginBottom: 10 }}>Pro</p>
                <h3>Pro</h3>
                <div className="price">$19<small>/month</small></div>
                <p className="note">7-day trial when checkout is enabled.</p>
                <ul>
                  <li>Everything in Free</li>
                  <li>Unlimited repositories and indexing</li>
                  <li>Cloud sync</li>
                  <li>Snapshot history</li>
                  <li>Advanced search</li>
                  <li>Priority indexing</li>
                  <li>New Pro capabilities as they ship</li>
                  <li>Priority support</li>
                </ul>
                {proReady ? (
                  <Link className="btn btn-primary btn-lg" href="/checkout/plan/pro">Start 7-day trial</Link>
                ) : (
                  <button className="btn btn-primary btn-lg" disabled>Coming soon</button>
                )}
                <div className="note-accent" style={{ marginTop: 18 }}>
                  <p style={{ margin: 0 }}><b>Paddle is the Merchant of Record.</b></p>
                  <p style={{ margin: "6px 0 0" }}>Atlas does not store payment card details. Pro checkout stays disabled until Paddle credentials are configured.</p>
                </div>
              </div>

              <div className="tier">
                <p className="badge muted" style={{ marginBottom: 10 }}>Coming soon</p>
                <h3>Team</h3>
                <div className="price">Contact</div>
                <p className="note">No Team subscription billing today.</p>
                <ul>
                  <li>Shared workflows</li>
                  <li>Team setup discussion</li>
                  <li>Security and deployment questions</li>
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
