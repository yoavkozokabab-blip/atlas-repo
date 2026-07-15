import type { Metadata } from "next";
import { PageShell, PremiumSection, ReleaseVersionBlock } from "../_components/site";

export const metadata: Metadata = {
  title: "Changelog - Atlas",
  description: "What shipped in Atlas v1.0: local-first indexing, Ask Atlas with cited files, MCP setup for Claude Code, Cursor, and Codex.",
};

const releases = [
  {
    version: "v1.0.3",
    date: "2026-07-15",
    label: "HN polish",
    items: [
      "Fixed global runtime banner showing false timeouts while the local backend was healthy.",
      "Unified repository state across sidebar, diagnostics, and main screens.",
      "Diagnostics now reports truthful component health instead of stale optional-endpoint failures.",
      "Agents screen distinguishes configured clients from verified clients (Cursor verified; Claude/Codex configured).",
      "Copy, layout, and footer cleanup for clearer first-run presentation.",
    ],
  },
  {
    version: "v1.0.0",
    date: "2026-07-10",
    label: "Launch build",
    items: [
      "Ask Atlas: repo-aware questions answered with cited files from the local index, including where-is-X-implemented routing.",
      "HN-ready first-run flow: load the sample repository, ask a prefilled question, and see cited files in about 30 seconds.",
      "One-click MCP setup for Claude Desktop, Cursor, and Codex - each with independent status, connect, test, and manual fallback.",
      "Local-first repository indexing: dependency graph, subsystem map, and impact analysis built entirely on your machine.",
      "Impact, Debug, and Plan Change workflows grounded in the scanned repository.",
      "Paddle billing prepared for the Pro plan ($19/month, 7-day trial). Checkout stays disabled until Paddle credentials are configured.",
      "Public website: download without signup, privacy/terms/refund/security pages, and an honest FAQ.",
    ],
  },
];

export default function ChangelogPage() {
  return (
    <PageShell
      eyebrow="Changelog"
      title="What's new in Atlas."
      intro="Release notes for the Atlas desktop app and website."
    >
      <PremiumSection>
        <ReleaseVersionBlock />
      </PremiumSection>
      <PremiumSection>
        <div className="container prose" style={{ maxWidth: 780, padding: 0 }}>
          {releases.map((r) => (
            <div key={r.version}>
              <h2>{r.version} <span className="badge ok" style={{ marginLeft: 10, verticalAlign: "middle" }}>{r.label}</span></h2>
              <p className="note">{r.date}</p>
              <ul>
                {r.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </PremiumSection>
    </PageShell>
  );
}
