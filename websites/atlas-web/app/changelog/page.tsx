import type { Metadata } from "next";
import { PageShell, PremiumSection, ReleaseVersionBlock } from "../_components/site";

export const metadata: Metadata = {
  title: "Changelog - Atlas",
  description: "What shipped in Atlas v1.0: local-first indexing, dependency graph and impact analysis, MCP setup for Claude Code, Cursor, and Codex.",
};

const releases = [
  {
    version: "v1.0.5",
    date: "2026-07-18",
    label: "Security + performance release",
    items: [
      "Indexing: real-world 3 GB repository cold scan ~8 s (was ~57 s); unchanged rescan ~3.6 s; one-file rescan ~8 s.",
      "Repository-context isolation: every Impact, Debug, and Plan result is bound to the repository and scan that produced it; switching repositories can never surface another repository's results.",
      "Security: the local accounts service now uses per-installation DPAPI-protected signing keys instead of a shared secret; upgrading invalidates legacy sessions. Users of v1.0.0–v1.0.4 should update.",
      "Ask: in-app repository Q&A is turned off in this release. It could still answer confidently about concepts that are not in the repository, and we would rather ship nothing there than ship a wrong answer. Graph, Impact, Debug, and Plan are unaffected, and agents still retrieve cited context over MCP.",
      "Impact: one-sentence result summary and 'Copy impact context for agent' carrying repository identity and scan revision.",
      "Analytics: Settings toggle to disable pseudonymous usage analytics; disabling blocks and clears everything, including queued events.",
      "Agents: Connected reflects a live MCP handshake and drops within seconds of the client closing.",
      "Rebuilt Windows installer from source commit ffa7152a (Atlas-Setup-1.0.5.exe), fixing restart persistence so a restored repository is never reported as needing a full rescan.",
      "Hotfix: first-run accounts are temporarily unavailable; Atlas launches in local mode with no account required. Graph, Impact, scanning, persistence, and MCP remain available. Installer identity updated to desktop commit 459884c6.",
    ],
  },
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
