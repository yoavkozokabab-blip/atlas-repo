import type { Metadata } from "next";
import Link from "next/link";
import {
  AsymSection,
  EvidenceBlock,
  IntegrationStatusBlock,
  MetricBlock,
  PageShell,
  PremiumSection,
  TechnicalDiagram,
  TrustBlock,
} from "../_components/site";
import { facts } from "../lib/content/facts";

export const metadata: Metadata = {
  title: "Product - Atlas",
  description:
    "Dependency graph, impact analysis, investigation mode, risk detection and evidence-backed AI context export - all local-first.",
};

const capabilities = [
  ["Dependency graph", "A local map of modules, imports, hubs, cycles and dependency paths."],
  ["Impact", "Deterministic what-breaks analysis from the resolved graph before you edit."],
  ["Debug", "Start from a symptom or traceback and get a grounded investigation path."],
  ["Plan Change", "Generate a change plan around the files and symbols Atlas found."],
  ["MCP export", "Serve the same local index to Claude Code, Cursor and Codex."],
] as const;

export default function FeaturesPage() {
  return (
    <PageShell
      eyebrow="Product"
      title="The missing memory layer for AI engineering."
      intro="Atlas builds the repository structure your coding agent cannot keep in context: dependencies, citations, impact paths and validated local memory."
    >
      <PremiumSection>
        <AsymSection
          eyebrow="Capabilities"
          title="Ask about behavior, not filenames."
          intro="Atlas is not a chatbot over your repo. It is a deterministic local index your agents can query when they need grounded context."
          aside={<MetricBlock metrics={[
            [String(facts.mcpTools), "MCP tools"],
            [facts.restoreMsLabel, "fresh-session restore"],
            [facts.askLatencyLabel, "cited-context retrieval"],
          ]} />}
        >
          <ul className="premium-list">
            {capabilities.map(([title, body], i) => (
              <li key={title}>
                <span className="num">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </AsymSection>
      </PremiumSection>

      <PremiumSection
        eyebrow="Evidence"
        title="Every answer has a trail back to the code."
        intro="Atlas gives the agent file-level evidence rather than asking it to infer structure from a shrinking prompt window."
      >
        <div className="grid-2">
          <EvidenceBlock
            question="Where is authentication implemented?"
            rows={[
              { path: "app/_lib/auth.ts", relation: "core", reason: "session signing, cookies and account lookup" },
              { path: "app/api/auth/login/route.ts", relation: "entry", reason: "public login request handling" },
              { path: "app/account/page.tsx", relation: "surface", reason: "signed-in account state and links" },
            ]}
          />
          <TechnicalDiagram
            title="repo memory"
            items={[
              ["Scan", "Read local source files and resolve symbols/imports."],
              ["Map", "Build graph relationships and evidence rows."],
              ["Serve", "Expose cited context to agents through MCP."],
            ]}
          />
        </div>
      </PremiumSection>

      <PremiumSection
        eyebrow="Integrations"
        title="One local index, multiple agents."
        intro="Atlas complements your coding agent; it does not replace it."
      >
        <IntegrationStatusBlock />
      </PremiumSection>

      <PremiumSection
        eyebrow="Limits"
        title="The honest parts are part of the product."
      >
        <TrustBlock />
        <div className="page-actions">
          <Link className="btn-mag" href="/download">Download Atlas <span className="arw" aria-hidden>→</span></Link>
          <Link className="btn-line" href="/benchmarks">Read benchmarks</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
