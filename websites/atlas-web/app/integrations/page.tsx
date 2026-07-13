import type { Metadata } from "next";
import Link from "next/link";
import {
  AsymSection,
  EvidenceBlock,
  IntegrationStatusBlock,
  PageShell,
  PremiumSection,
  TechnicalDiagram,
} from "../_components/site";
import { facts } from "../lib/content/facts";

export const metadata: Metadata = {
  title: "Integrations - Atlas",
  description:
    "Atlas connects to Claude Code, Cursor and Codex over MCP. Support levels, install steps, example workflows and current limitations.",
};

const integrations = [
  ["Claude Code", "Supported", "Connect Atlas as an MCP server and ask repo-aware questions from your Claude Code workflow."],
  ["Cursor", "Supported", "Give Cursor cited local context instead of re-explaining the same files each session."],
  ["Codex", "Supported", "Use Atlas context when planning changes, debugging behavior, or mapping an unfamiliar repo."],
  ["MCP-compatible clients", "Experimental", `Atlas exposes ${facts.mcpTools} MCP tools. Validate against your client before relying on it.`],
] as const;

export default function Integrations() {
  return (
    <PageShell
      eyebrow="Integrations"
      title="Built for the agents you already use."
      intro="Atlas serves cited repository context to coding agents over MCP. Support levels and limitations stay explicit."
    >
      <PremiumSection>
        <IntegrationStatusBlock />
      </PremiumSection>

      <PremiumSection>
        <AsymSection
          eyebrow="Support"
          title="One index, three primary agents."
          intro="The desktop app owns the local index and config writes. Agents consume it through their MCP support."
        >
          <ul className="premium-list">
            {integrations.map(([name, support, body], index) => (
              <li key={name}>
                <span className="num">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{name} <span className={`integ-badge ${support === "Supported" ? "ok" : "exp"}`}>{support}</span></h3>
                  <p>{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </AsymSection>
      </PremiumSection>

      <PremiumSection
        eyebrow="Config"
        title="The shape is boring on purpose."
        intro="Atlas launches as a local stdio MCP server. The desktop app writes the exact client config and keeps backups."
      >
        <div className="grid-2">
          <TechnicalDiagram
            title="mcp handoff"
            items={[
              ["Connect", "Choose Claude, Cursor or Codex in the Atlas desktop app."],
              ["Write config", "Atlas adds only its own MCP entry and preserves existing servers."],
              ["Restart agent", "The agent loads the config and can query the local index."],
            ]}
          />
          <EvidenceBlock
            question="What does an agent receive?"
            rows={[
              { path: "scan index", relation: "local", reason: "repository graph and evidence store stay on disk" },
              { path: "MCP response", relation: "selected", reason: "only cited context returned by the query" },
              { path: "model provider", relation: "agent path", reason: "your agent may send selected context under its own terms" },
            ]}
          />
        </div>
        <div className="page-actions">
          <Link className="btn-mag" href="/docs#mcp">Read MCP setup <span className="arw" aria-hidden>→</span></Link>
          <Link className="btn-line" href="/security#data-flow">Review data flow</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
