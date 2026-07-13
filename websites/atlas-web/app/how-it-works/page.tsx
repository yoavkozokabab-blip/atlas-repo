import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";
import { facts } from "../lib/content/facts";

export const metadata: Metadata = {
  title: "How it works - Atlas",
  description:
    "The Atlas pipeline: connect a repository, scan files and symbols, build relationships, create persistent memory, connect coding agents, and retrieve cited context during work.",
};

const steps = [
  ["Connect a repository", "Open a local repo in the Atlas desktop app. Nothing is uploaded — indexing runs on your machine."],
  ["Scan files and symbols", `Atlas parses files, symbols and imports. The built-in sample repo (${facts.sampleFiles} files) indexes in ${facts.sampleIndexLabel}.`],
  ["Build relationships", "A dependency graph and evidence store capture how modules, callers and callees relate."],
  ["Create persistent memory", `The map is written to disk and validated against the live repo. Fresh agent sessions restore it in ${facts.restoreMsLabel}.`],
  ["Connect coding agents", `Claude Code, Cursor and Codex connect over MCP (${facts.mcpTools} tools). No re-explaining the repo each session.`],
  ["Retrieve cited context", `Ask where behavior lives or what a change affects; Atlas returns cited files in ${facts.askLatencyLabel} — deterministic lookups, no model in the loop.`],
  ["Update as the project changes", "Re-scans produce deltas; stale scans are refused rather than served, so the memory stays trustworthy."],
];

export default function HowItWorks() {
  return (
    <PageShell
      eyebrow="How it works"
      title="From raw repository to persistent memory."
      intro="Atlas turns a repository into a structured, cited memory that survives across agent sessions. Every step runs locally."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container" style={{ maxWidth: 860 }}>
          <ol className="steps" style={{ gap: 22 }}>
            {steps.map(([title, body]) => (
              <li key={title}>
                <h3 style={{ marginBottom: 6 }}>{title}</h3>
                <p>{body}</p>
              </li>
            ))}
          </ol>
          <p style={{ marginTop: 32 }}>
            <Link className="btn-mag" href="/download">Download Atlas <span className="arw" aria-hidden>→</span></Link>
          </p>
        </div>
      </section>
    </PageShell>
  );
}
