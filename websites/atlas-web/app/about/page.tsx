import type { Metadata } from "next";
import Link from "next/link";
import InstallerWaitState from "../_components/InstallerWaitState";
import { PageShell, PremiumSection, TrustBlock } from "../_components/site";

export const metadata: Metadata = {
  title: "About - Atlas",
  description: "About Atlas: a local-first repository memory layer for AI-assisted engineering.",
};

export default function AboutPage() {
  return (
    <PageShell
      eyebrow="About"
      title="Atlas is built for engineers who are tired of re-explaining the repo."
      intro="The product goal is narrow: give AI coding agents a persistent, cited, local understanding of the codebase without uploading repository contents during indexing."
    >
      <PremiumSection
        eyebrow="Principles"
        title="Small surface, serious claims."
        intro="Atlas is not trying to become the coding agent. It is the memory layer those agents can query when they need grounded context."
      >
        <ul className="premium-list">
          <li><span className="num">01</span><div><h3>Local first</h3><p>Repository scanning and indexing happen on your machine.</p></div></li>
          <li><span className="num">02</span><div><h3>Cited by default</h3><p>Answers point back to files and evidence, so engineers can verify before acting.</p></div></li>
          <li><span className="num">03</span><div><h3>Agent neutral</h3><p>The same local index can serve Claude Code, Cursor and Codex over MCP.</p></div></li>
        </ul>
      </PremiumSection>

      <PremiumSection eyebrow="Limits" title="The constraints are public too.">
        <TrustBlock />
        <div className="page-actions">
          <InstallerWaitState />
          <Link className="btn-line" href="/contact">Contact</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
