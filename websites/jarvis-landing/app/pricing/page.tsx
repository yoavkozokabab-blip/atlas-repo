import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";
import { PAID_PLANS_ENABLED } from "../_config";

export const metadata: Metadata = {
  title: "Pricing — Atlas",
  description: PAID_PLANS_ENABLED
    ? "Simple pricing for serious codebases. Free to start, Pro at $29/mo with a 7-day trial, Team for engineering orgs."
    : "Atlas is in free invite beta — everything is free while we're in beta. Paid plans come later."
};

export default function PricingPage() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Pricing</p>
            <h1 className="page-title">{PAID_PLANS_ENABLED ? "Simple pricing for serious codebases." : "Free while we're in beta."}</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              {PAID_PLANS_ENABLED
                ? "Start free, on your machine. Upgrade when you want unlimited repos, impact analysis and investigation. The 7-day Pro trial starts inside Atlas — no credit card."
                : "Atlas is in a free invite beta. Everything below is free right now — there's nothing to buy and no card required. Paid plans are planned for after the beta."}
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
                <div className="price">{PAID_PLANS_ENABLED ? <>$29<small> / month</small></> : <>Free<small> in beta</small></>}</div>
                <ul>
                  <li>Unlimited repositories</li>
                  <li>Impact analysis &amp; investigation mode</li>
                  <li>AI context compression</li>
                  <li>Architecture risk detection</li>
                  <li>Priority support</li>
                </ul>
                {PAID_PLANS_ENABLED ? (
                  <>
                    <Link className="btn btn-primary" href="/checkout/plan/pro">Start 7-day trial</Link>
                    <p className="dl-meta" style={{ marginTop: 10 }}>Trial starts in-app · no card</p>
                  </>
                ) : (
                  <>
                    <Link className="btn btn-primary" href="/download">Join the beta</Link>
                    <p className="dl-meta" style={{ marginTop: 10 }}>Free during beta · Pro pricing planned later</p>
                  </>
                )}
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
              {PAID_PLANS_ENABLED
                ? "Local-first · cancel anytime from the billing portal · prices in USD"
                : "Local-first · free invite beta · no card, no charge"}
            </p>
            <div className="note-accent" style={{ marginTop: 28, maxWidth: 760 }}>
              {PAID_PLANS_ENABLED ? (
                <><b>Note:</b> the 7-day Pro trial starts inside the app — no card required.</>
              ) : (
                <><b>Free invite beta.</b> There is nothing to purchase yet — no checkout, no card, no charge. Download Atlas, sign in, and start using it. We&apos;ll announce paid plans before they go live.</>
              )}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
