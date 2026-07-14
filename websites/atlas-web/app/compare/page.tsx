import type { Metadata } from "next";
import Link from "next/link";
import InstallerWaitState from "../_components/InstallerWaitState";
import { PageShell, PremiumSection, TrustBlock } from "../_components/site";

export const metadata: Metadata = {
  title: "Atlas vs built-in agent context - Atlas",
  description: "Factual comparison of Atlas with the project context built into Claude and Cursor: persistence, local indexing, cited files, MCP, impact analysis.",
};

const rows: Array<[string, string, string, string]> = [
  ["Persistent repo memory across sessions", "Session/project scoped", "Session/workspace scoped", "Yes - the local index persists until you rescan"],
  ["Repository indexing runs locally", "Context handled by the tool", "Codebase indexing; check Cursor docs for current details", "Yes - indexing never leaves your machine"],
  ["Answers with cited files", "Sometimes, from what is in context", "Sometimes, from retrieved context", "Every answer lists grounded files"],
  ["Dependency graph of the repository", "No", "No", "Resolved import graph with hubs and cycles"],
  ["Impact analysis", "Ad-hoc, model-driven", "Ad-hoc, model-driven", "Deterministic, from the resolved graph"],
  ["MCP server other tools can call", "Claude consumes MCP", "Cursor consumes MCP", "Atlas is the MCP server"],
  ["Works across Claude Code, Cursor, and Codex", "Claude only", "Cursor only", "One index, three agents"],
];

export default function ComparePage() {
  return (
    <PageShell
      eyebrow="Compare"
      title="Atlas next to your agent's built-in context."
      intro="Claude Code and Cursor are excellent coding agents. Atlas is a persistent local memory layer they can both read from."
    >
      <PremiumSection>
        <div style={{ overflowX: "auto" }} tabIndex={0} aria-label="Atlas comparison table">
          <table className="compare-table">
            <thead>
              <tr>
                <th>Capability</th>
                <th>Claude project context</th>
                <th>Cursor built-in context</th>
                <th>Atlas</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([cap, claude, cursor, atlas]) => (
                <tr key={cap}>
                  <td>{cap}</td>
                  <td>{claude}</td>
                  <td>{cursor}</td>
                  <td><b>{atlas}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note" style={{ marginTop: 18 }}>
          Built-in behavior of other tools changes over time; check their docs for current details. This table describes how Atlas complements them.
        </p>
        <div className="page-actions">
          <InstallerWaitState />
          <Link className="btn-line" href="/benchmarks">See benchmarks</Link>
        </div>
      </PremiumSection>

      <PremiumSection eyebrow="Limits" title="No fake certainty.">
        <TrustBlock />
      </PremiumSection>
    </PageShell>
  );
}
