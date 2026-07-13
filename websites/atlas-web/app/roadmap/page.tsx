import type { Metadata } from "next";
import { PageShell } from "../_components/site";

export const metadata: Metadata = {
  title: "Roadmap - Atlas",
  description: "What Atlas ships today, what is being built next, and what is under consideration. Honest and technical — no promised dates.",
};

const sections = [
  {
    key: "Now",
    badge: "ok",
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
    badge: "muted",
    intro: "Actively being worked on. No committed dates.",
    items: [
      "Code signing for the installer, so Windows SmartScreen stops warning on first run.",
      "Pro checkout via Paddle (the plan and pricing exist today; live checkout requires completed Paddle configuration).",
      "Deeper dependency analysis beyond Python and JavaScript/TypeScript (Go, Rust, and Java are scanned today but with shallower import resolution).",
      "Faster indexing on very large monorepos.",
    ],
  },
  {
    key: "Later",
    badge: "muted",
    intro: "Under consideration. Not committed — treat as direction, not promise.",
    items: [
      "macOS and Linux builds.",
      "Team plan (shared workflows). No Team billing exists today.",
      "Cloud sync and snapshot history for Pro.",
      "Automatically maintained agent memory files (for example CLAUDE.md / AGENTS.md kept in sync with the index).",
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
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container grid-3">
          {sections.map((s) => (
            <div className="card" key={s.key}>
              <p className={`badge ${s.badge}`} style={{ marginBottom: 10 }}>{s.key}</p>
              <p className="muted" style={{ fontSize: "0.9rem" }}>{s.intro}</p>
              <ul style={{ marginTop: 12, paddingLeft: 18 }}>
                {s.items.map((item) => (
                  <li key={item} style={{ marginBottom: 8 }}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </PageShell>
  );
}
