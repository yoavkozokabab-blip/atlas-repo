import type { Metadata } from "next";
import { PageShell } from "../_components/site";
import { SUPPORT_EMAIL } from "../_config";

export const metadata: Metadata = {
  title: "FAQ - Atlas",
  description: "Frequently asked questions about Atlas: privacy, local indexing, Claude Code, Cursor, Codex, Windows downloads, pricing, Paddle billing, and security.",
};

const faqs = [
  ["What is Atlas?", "Atlas is local-first repository memory for AI coding agents. It indexes your repo on your machine and returns cited files for questions, debugging, impact analysis, and change planning."],
  ["When will Windows downloads reopen?", "The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready."],
  ["Does my code leave my machine?", "Repository indexing runs locally. Atlas does not upload your source code to a hosted indexing service."],
  ["What can leave my machine?", "Only the context you explicitly copy or send to another tool. If you paste Atlas output into Claude Code, Cursor, Codex, or another service, that service receives what you sent."],
  ["Does Atlas replace Claude Code, Cursor, or Codex?", "No. Atlas gives those agents repository memory and cited local context."],
  ["How is this different from the context Claude Code or Cursor already has?", "Those tools rebuild context per session from what fits in the window. Atlas keeps a persistent local index of the whole repository — dependency graph, subsystem map, impact paths — and serves cited files from it across sessions."],
  ["Why not just maintain a CLAUDE.md or AGENTS.md?", "Hand-written context files drift as soon as the code changes, and they store prose rather than structure. Atlas maintains a resolved import graph and per-file evidence, validates it against a content signature of the repository, and refuses to serve it stale."],
  ["Why not Cursor's built-in codebase indexing?", "Cursor's index serves Cursor only. Atlas is one local index shared by Claude Code, Cursor, and Codex over MCP, it survives fresh sessions with explicit staleness detection, and it adds deterministic impact analysis on the dependency graph."],
  ["Why not Serena or another MCP code server?", "If another MCP server works for you, keep using it. Atlas focuses on persisted validated scans that restore in milliseconds in fresh sessions, deterministic what-breaks analysis, and one-click MCP setup for all three agents from a desktop app."],
  ["Which model answers my questions?", "None. Atlas does not call any LLM — Ask Atlas, Impact, Debug, and Plan Change are deterministic lookups against the local index. Your coding agent brings its own model and decides what context to send to it."],
  ["Is Atlas open source?", "The source is publicly visible on GitHub, but it ships under a proprietary license — it is source-visible, not open source."],
  ["Why $19/month for Pro?", "The core app is free with no account. $19 is planned for capacity features (unlimited repos, sync, snapshots) built on paid infrastructure — priced to sustain a solo-built product without ads or data monetization. Pro checkout is not enabled until Paddle billing is fully verified."],
  ["Why Windows only?", "Because shipping one platform well beat shipping three badly. The core is portable Python; macOS and Linux are on the roadmap after the Windows build proves itself."],
  ["Why are Windows downloads paused?", "The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready."],
  ["Can Atlas be wrong about impact?", "Yes. Impact analysis covers statically resolved imports; dynamic dispatch, reflection, string-based imports, and runtime wiring are invisible to it. Every result cites the evidence used so you can verify before acting."],
  ["Does Atlas preserve my existing MCP configuration?", "Yes. Connect writes only the atlas entry, keeps every other MCP server untouched, creates a timestamped backup of your config file first, and validates the resulting JSON/TOML before replacing it."],
  ["Why does Atlas need repository read access?", "Indexing means reading source files to build the dependency graph and symbol evidence — locally. Atlas never needs write access to your code and never uploads it during indexing."],
  ["Does Atlas work offline?", "Repository scanning, the local index, and cited answers work offline. Your AI coding agent still needs its own network access to its model provider."],
  ["Where is repository data stored?", "In a local data directory in your user profile (.atlas_desktop). Nothing is stored on Atlas servers during indexing."],
  ["Can I delete the local data?", "Yes. Delete the .atlas_desktop folder in your user profile, or uninstall Atlas. Removing it deletes scans, settings, and local session data."],
  ["Does Atlas modify my code?", "No. Atlas reads and analyzes your repository. The only files it writes are agent config files (for example Claude, Cursor, or Codex MCP config) when you explicitly click Connect."],
  ["Does Atlas require admin permissions?", "No. The Windows installer runs with the lowest privilege level and installs per-user."],
  ["What languages and repos are supported?", "Atlas scans common source files (Python, JavaScript/TypeScript, Go, Rust, Java, C#, Ruby, and more). The deepest dependency and import analysis today is for Python and JavaScript/TypeScript."],
  ["How large can repos be, and how fast is indexing?", "Atlas is built for real-world repositories and indexes locally, so speed depends on your machine and repo size. Typical projects index in seconds to a few minutes; very large monorepos take longer."],
  ["What happens after I edit files?", "Atlas detects that the repository changed since the last scan and blocks stale exports until you refresh, so agents never work from an outdated map."],
  ["How does Atlas connect to coding agents?", "Atlas uses local MCP configuration for Claude Code, Cursor, and Codex where supported by the tool. The app writes the relevant local config and shows exact file paths."],
  ["Can I still copy manually?", "Yes. Manual JSON copy is available in the advanced manual setup path."],
  ["What platforms are supported today?", "Atlas is available today as a Windows installer. macOS and Linux are not available yet."],
  ["Is the installer signed?", "Do not assume the installer is signed. Windows SmartScreen may show a warning for new or unsigned apps; confirm you are using the official release link before continuing."],
  ["What is included in Free?", "Free includes the core local app, local scan, Ask Atlas, MCP, Impact, Debug, Plan Change, and Map."],
  ["What is included in Pro?", "Pro is planned at $19/month with a 7-day trial: unlimited repositories and indexing, cloud sync, snapshot history, advanced search, priority indexing, New Pro capabilities as they ship, and priority support."],
  ["Is paid billing live?", "Only when Paddle credentials are configured on the deployment. If checkout is not configured, the Pro button is disabled or shows a not-configured message."],
  ["Who processes payments?", "Paddle is the Merchant of Record for paid subscriptions when Pro checkout is enabled. Atlas does not store payment card details."],
  ["Is Team available?", "Team is coming soon. There is no Team subscription billing today."],
  ["Can I cancel Pro?", "Yes, anytime from the billing portal. Access continues to the end of the paid period."],
  ["What about refunds?", "Refund requests for billing or service issues are reviewed if submitted within 14 days of the charge. See the Refund Policy for details."],
  ["Can I delete my account?", "Yes. Signed-in users can delete their account from account settings."],
  ["How do I report a security issue?", `Email ${SUPPORT_EMAIL}. Do not paste secrets or full private source code into email.`],
] as const;

export default function FaqPage() {
  return (
    <PageShell eyebrow="FAQ" title="Questions, answered." intro="Practical details before you install Atlas.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container faq" style={{ maxWidth: 860 }}>
          {faqs.map(([q, a], i) => (
            <details key={q} open={i === 0}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>
    </PageShell>
  );
}
