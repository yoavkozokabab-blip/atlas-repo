import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";

export const metadata: Metadata = {
  title: "Atlas vs built-in agent context - Atlas",
  description: "Factual comparison of Atlas with the project context built into Claude and Cursor: persistence, local indexing, cited files, MCP, impact analysis.",
};

// "yes" / "partial" / "no" with an honest note where the answer needs nuance.
const rows: Array<[string, string, string, string]> = [
  ["Persistent repo memory across sessions", "Session/project scoped", "Session/workspace scoped", "Yes — the local index persists until you rescan"],
  ["Repository indexing runs locally", "Context handled by the tool", "Codebase indexing (see Cursor's docs for where it runs)", "Yes — indexing never leaves your machine"],
  ["Answers with cited files", "Sometimes, from what is in context", "Sometimes, from retrieved context", "Always — every answer lists the files it is grounded in"],
  ["Dependency graph of the repository", "No", "No", "Yes — resolved import graph with hubs and cycles"],
  ["Impact analysis (what breaks if X changes)", "Ad-hoc, model-driven", "Ad-hoc, model-driven", "Yes — deterministic, from the resolved graph"],
  ["MCP server other tools can call", "Claude consumes MCP", "Cursor consumes MCP", "Yes — Atlas is the MCP server (18 tools)"],
  ["Works across Claude Code, Cursor, and Codex", "Claude only", "Cursor only", "Yes — one index, three agents"],
];

export default function ComparePage() {
  return (
    <PageShell
      eyebrow="Compare"
      title="Atlas next to your agent's built-in context."
      intro="Claude Code and Cursor are excellent coding agents. Atlas is not a replacement for either — it is a persistent local memory layer they can both read from. Here is the factual difference."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 980 }}>
          <div style={{ overflowX: "auto" }}>
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
            Built-in behavior of other tools changes over time — check their docs for current details.
            This table describes how Atlas complements them, not why you should stop using them.
          </p>
          <p style={{ marginTop: 20 }}>
            <Link className="btn btn-primary" href="/download">Download Atlas</Link>{" "}
            <Link className="btn btn-ghost" href="/benchmarks" style={{ marginLeft: 8 }}>See benchmarks</Link>
          </p>
        </div>
      </section>
    </PageShell>
  );
}
