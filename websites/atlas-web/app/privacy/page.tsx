import type { Metadata } from "next";
import { PageShell } from "../_components/site";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Privacy & Security — Atlas",
  description: "Atlas is local-first. Your source code never leaves your machine. Here's exactly what runs locally and what doesn't."
};

export default function PrivacyPage() {
  return (
    <PageShell
      eyebrow="Privacy"
      title="Privacy Policy"
      intro="Atlas is local-first. Repository indexing happens on your machine. Atlas does not upload repository contents during indexing. Atlas never trains AI models using customer repositories."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>What runs locally</h2>
          <ul>
            <li>Repository scanning and file reading</li>
            <li>The dependency graph, subsystem map and architecture analysis</li>
            <li>Risk detection, impact analysis and Plan Change workflows</li>
            <li>Generation of the AI context packet</li>
          </ul>
          <p>Your source code is read and analyzed entirely on your device. Atlas does not upload
            your repository to an Atlas-hosted service.</p>

          <h2>What can leave your device</h2>
          <ul>
            <li><b>The context you copy or your agent requests.</b> When you click “Copy for
              Claude/Codex/Cursor”, the compact packet goes wherever <em>you</em> paste it. If you
              connect an external coding agent over MCP, that agent may send the context you request
              to the model provider <em>it</em> is configured to use — the same as when you use that
              agent without Atlas.</li>
            <li><b>Account &amp; licensing</b> (if you sign in): email and license status are exchanged
              with the Atlas accounts service to validate your plan. Your code is never included.</li>
            <li><b>Pseudonymous product analytics</b> to improve Atlas (can be disabled in Settings).
              Events carry a random per-installation identifier — and your account id if you are
              signed in — but never repository contents, repository names or paths, file names,
              source code, prompts, answers, secrets, or MCP payloads.</li>
            <li><b>Billing metadata.</b> Paid subscriptions are handled by Paddle as Merchant of
              Record. Atlas does not store your payment details.</li>
          </ul>

          <h2>Trust by construction</h2>
          <p>Atlas refuses to hand your AI stale or unverifiable context. If a repository changed
            since the last scan, exports are blocked until you refresh — so your agent never works
            from a misleading map.</p>

          <h2>Data &amp; contact</h2>
          <p>For privacy questions, data requests, or security disclosures, contact us via the
            <a href={supportMailto("Atlas Privacy")}> {SUPPORT_EMAIL ? SUPPORT_EMAIL : "contact page"}</a>.</p>

          <p className="note">Last updated: 2026-07-09.</p>
        </div>
      </section>
    </PageShell>
  );
}
