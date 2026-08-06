import type { Metadata } from "next";
import { PageShell, PremiumSection, ReleaseVersionBlock } from "../_components/site";

export const metadata: Metadata = {
  title: "Changelog - Atlas",
  description: "What shipped in Atlas v1.0: local-first indexing, impact analysis with cited files, MCP setup for Claude Code, Cursor, and Codex.",
};

const releases = [
  {
    version: "v1.0.4",
    date: "2026-07-16",
    label: "Workflow fix",
    items: [
      "Fixed Impact panel rendering after analysis (removed invalid Set.filter usage on dependents).",
      "History-scope repository invalidations no longer erase Ask, Impact, Debug, and Plan results after they render.",
      "Demo naming: visible Atlas Demo — Medium with canonical medium_repo, stable across restart.",
      "Rebuilt Windows installer from corrected source commit a4782f87.",
    ],
  },
  {
    version: "v1.0.3",
    date: "2026-07-15",
    label: "Public release",
    items: [
      "Desktop: launch presentation polish, restored configured-without-repo status copy, and installed-state persistence fixes.",
      "Website: download metadata now points at the v1.0.3 installer with its published SHA-256.",
    ],
  },
  {
    version: "v1.0.2",
    date: "2026-07-15",
    label: "UI/UX polish",
    items: [
      "Desktop workbench spacing, card padding, and typography refinements across Home, Memory, Files, Graph, Ask, Impact, Agents, Diagnostics, and Settings.",
      "Agents screen no longer shows a false Connected state; configuration cards reflect verified MCP setup accurately.",
      "Version labels, footer metadata, and build markers updated to v1.0.2 with embedded source commit f3d864e9.",
      "Rebuilt Windows installer from verified source; in-place update preserves repository memory without silent rescan.",
    ],
  },
  {
    version: "v1.0.1",
    date: "2026-07-15",
    label: "Verified installer",
    items: [
      "Rebuilt from the exact embedded desktop source commit and published as a fresh GitHub Release asset.",
      "Installed-app verification confirmed fallback-port launch isolation, restored repository memory, no silent rescan, and no requests to an occupied Aurora port.",
      "Website download metadata and checksum now point at the verified v1.0.1 installer.",
    ],
  },
  {
    version: "v1.0.0",
    date: "2026-07-10",
    label: "Launch build",
    items: [
      "Ask Atlas: repo-aware questions with cited files — subsequently disabled and still under development; not included in this beta.",
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
