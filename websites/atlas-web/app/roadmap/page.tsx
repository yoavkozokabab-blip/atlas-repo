import type { Metadata } from "next";
import { PageShell, PremiumSection } from "../_components/site";
import { UpdatesSignupForm } from "../_components/updates-signup";

export const metadata: Metadata = {
  title: "Roadmap - Atlas",
  description: "What Atlas ships today, what is being built next, and what is under consideration. Honest and technical - no promised dates.",
};

const sections = [
  {
    key: "Now",
    intro: "Shipped and supported in v1.0.",
    items: [
      "Windows installer (per-user, no admin required).",
      "Local-first repository indexing: dependency graph, subsystem map, entry points.",
      "Ask Atlas with cited files, plus Impact, Debug, and Plan Change workflows.",
      "MCP integration for Claude Desktop, Cursor, and Codex with one-click config writes.",
      "30-second sample-repository demo.",
    ],
  },
  {
    key: "Next",
    intro: "Actively being worked on. No committed dates.",
    items: [
      "Code signing for the installer, so Windows SmartScreen stops warning on first run.",
      "Pro checkout via Paddle (the plan and pricing exist today; live checkout requires completed Paddle configuration).",
      "Deeper dependency analysis beyond Python and JavaScript/TypeScript.",
      "Faster indexing on very large monorepos.",
    ],
  },
  {
    key: "Later",
    intro: "Under consideration. Not committed - treat as direction, not promise.",
    items: [
      "macOS and Linux builds.",
      "Team plan (shared workflows). No Team billing exists today.",
      "Cloud sync and snapshot history for Pro.",
      "Automatically maintained agent memory files kept in sync with the index.",
    ],
  },
];

export default function RoadmapPage() {
  return (
    <PageShell
      eyebrow="Roadmap"
      title="Where Atlas is going."
      intro="Three honest buckets. Items move between them based on real progress, not marketing."
    >
      <PremiumSection>
        <div className="grid-3">
          {sections.map((s, index) => (
            <div className="tier" key={s.key}>
              <p className="eyebrow">{s.key}</p>
              <h3>{s.intro}</h3>
              <ul style={{ marginTop: 18 }}>
                {s.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <p className="mono muted" style={{ marginTop: 18 }}>bucket {String(index + 1).padStart(2, "0")}</p>
            </div>
          ))}
        </div>
      </PremiumSection>
      <PremiumSection
        eyebrow="Product updates"
        title="Follow Atlas as it ships."
        intro="Get occasional release and platform updates. No marketing lists and no repository data."
      >
        <UpdatesSignupForm source="roadmap" />
      </PremiumSection>
    </PageShell>
  );
}
