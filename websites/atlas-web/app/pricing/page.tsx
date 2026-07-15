import type { Metadata } from "next";
import Link from "next/link";
import { PageShell, PremiumSection, TrustBlock } from "../_components/site";
import { proCheckoutReady } from "../_lib/billing";

export const metadata: Metadata = {
  title: "Pricing - Atlas",
  description: "Atlas pricing: Free local app today, Pro planned at $19/month with Paddle checkout when billing is configured.",
};

const free = ["Local repository scan", "Ask Atlas", "MCP integration", "Impact", "Debug", "Plan Change", "Map"];
const pro = [
  "Everything in Free",
  "Unlimited repositories and indexing",
  "Cloud sync",
  "Snapshot history",
  "Advanced search",
  "Priority indexing",
  "New Pro capabilities as they ship",
  "Priority support",
];
const team = ["Shared workflows", "Team setup discussion", "Security and deployment questions"];

export default function PricingPage() {
  const proReady = proCheckoutReady();
  return (
    <PageShell
      eyebrow="Pricing"
      title="Simple pricing for repo memory."
      intro="Start with the local Windows app. Pro billing is powered by Paddle as Merchant of Record when checkout is configured."
    >
      <PremiumSection>
        <div className="tiers premium-tiers">
          <div className="tier">
            <p className="eyebrow">Free</p>
            <h3>Core local app</h3>
            <div className="price">$0</div>
            <p className="note">Available today.</p>
            <ul>{free.map((item) => <li key={item}>{item}</li>)}</ul>
            <Link className="btn-mag" href="/download">Download Atlas <span className="arw" aria-hidden>→</span></Link>
          </div>

          <div className="tier feat">
            <p className="eyebrow">Pro</p>
            <h3>Capacity features</h3>
            <div className="price">$19<small>/month</small></div>
            <p className="note">7-day trial when checkout is enabled.</p>
            <ul>{pro.map((item) => <li key={item}>{item}</li>)}</ul>
            {proReady ? (
              <Link className="btn-mag" href="/checkout/plan/pro" data-evt="pro_cta_click">Start 7-day trial <span className="arw" aria-hidden>→</span></Link>
            ) : (
              <button className="btn btn-primary btn-lg" disabled data-evt="pro_cta_click">Coming soon</button>
            )}
            <div className="note-accent" style={{ marginTop: 18 }}>
              <p style={{ margin: 0 }}><b>Paddle is the Merchant of Record.</b></p>
              <p style={{ margin: "6px 0 0" }}>Atlas does not store payment card details. Pro checkout stays disabled until Paddle credentials are configured.</p>
            </div>
          </div>

          <div className="tier">
            <p className="eyebrow">Team</p>
            <h3>Discussion only</h3>
            <div className="price">Contact</div>
            <p className="note">No Team subscription billing today.</p>
            <ul>{team.map((item) => <li key={item}>{item}</li>)}</ul>
            <Link className="btn-line" href="/contact">Contact us</Link>
          </div>
        </div>
      </PremiumSection>

      <PremiumSection
        eyebrow="Trust"
        title="No pricing magic hidden behind the page."
        intro="The public page reflects current billing behavior: Free is available, Pro checkout depends on configured Paddle credentials, and Team billing does not exist today."
      >
        <TrustBlock />
      </PremiumSection>
    </PageShell>
  );
}
