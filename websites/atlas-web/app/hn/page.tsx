import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter, InstallFlow } from "../_components/site";
import { GITHUB_RELEASE_URL, GITHUB_URL, INSTALLER_SHA256, SUPPORT_EMAIL } from "../_config";

export const metadata: Metadata = {
  title: "Atlas for Hacker News",
  description:
    "Persistent repository context across fresh coding-agent sessions. Local-first indexing for Claude Code, Cursor, and Codex. Windows v1.0.",
};

const faq = [
  ["Why not just CLAUDE.md / AGENTS.md?", "Hand-written context files drift the moment the code changes, and they hold prose, not structure. Atlas maintains a resolved import graph, subsystem map, and per-file evidence that is validated against the repository signature — if the repo changed, Atlas says so instead of serving stale context."],
  ["Why not Cursor's built-in indexing?", "Cursor's index serves Cursor. Atlas is one local index that Claude Code, Cursor, and Codex all read over MCP, it persists across sessions with explicit staleness detection, and it adds deterministic impact analysis on the dependency graph — not just retrieval."],
  ["Why not Serena or another MCP code server?", "Closest neighbor, and if Serena works for you, keep it. Atlas differs in emphasis: persisted validated scans that restore instantly in fresh sessions, deterministic what-breaks impact analysis from the resolved import graph, and a desktop app that writes the MCP config for all three agents in one click."],
  ["What does Atlas send to the agent?", "Only the context the agent requests via MCP tools: file paths, symbols, graph facts, and short evidence strings. The agent then sends what it chooses to its own model provider under that provider's terms. Full data flow is on the security page."],
  ["What is rough today?", "Windows-only installer (unsigned, so SmartScreen warns). Deep import analysis is Python and JavaScript/TypeScript; Go, Rust, Java, C#, Ruby are scanned at file level. Pro checkout is not enabled yet."],
] as const;

export default function HackerNewsPage() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="hero hn-hero">
          <div className="container hero-grid">
            <div>
              <p className="eyebrow">Atlas for Hacker News</p>
              <h1>Persistent repository context across fresh coding-agent sessions</h1>
              <p>
                Atlas indexes your repository locally into a dependency graph, subsystem map, and
                evidence store — then serves it to Claude Code, Cursor, and Codex over MCP. Built for developers who are tired of re-explaining the same codebase to AI coding agents. Kill the agent, open a new session tomorrow: the context is still there, validated against the current state of your repo.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary btn-lg" href="/download" data-evt="download_click">Download Atlas</Link>
              </div>
              <p className="hero-note">No signup required · Continue without an account · Local-first indexing · Your code stays on your machine · Windows v1.0</p>
              <div style={{ marginTop: 22 }}>
                <InstallFlow />
              </div>
            </div>
            <div className="product-panel">
              <div className="product-top"><span>Fresh MCP session</span><span className="status-dot">Restored, not rescanned</span></div>
              <div className="product-body">
                <div className="product-question">atlas_health → persistence</div>
                <div className="product-answer">
                  status: <b>restored</b> · validation: <b>valid</b> · graph_rebuilt: <b>false</b> ·
                  restore: <b>8–11 ms</b>
                </div>
                <div className="citations"><span>~/.atlas_desktop/scans/&lt;repo_id&gt;/</span><span>graph.json</span><span>memory_packet.json</span></div>
              </div>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-2">
            <div className="card">
              <h3>What it does</h3>
              <ul>
                <li>Scans a local repository into a resolved import graph, subsystem map, risk model, and symbol evidence.</li>
                <li>Answers repo questions with cited files (Ask Atlas), and runs Impact, Debug, and Plan Change on the graph.</li>
                <li>Persists the scan, index, and repository memory to disk, and restores them in fresh MCP sessions after validating a content signature.</li>
                <li>One-click MCP setup for Claude Desktop, Cursor, and Codex — with timestamped config backups that preserve your other MCP servers.</li>
              </ul>
            </div>
            <div className="card">
              <h3>What it does not do</h3>
              <ul>
                <li>It is not a coding agent and does not call any LLM. Answers are deterministic lookups against the local index.</li>
                <li>It does not modify your source code. The only files it writes outside its data directory are agent MCP configs, when you click Connect.</li>
                <li>It does not upload repository contents to Atlas servers during indexing — there is no hosted indexing service.</li>
                <li>It does not certify correctness. Impact analysis covers resolved imports; dynamic dispatch and reflection are out of scope.</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-2">
            <div>
              <p className="eyebrow">Persistence, measured</p>
              <h2>Fresh sessions restore instead of rescanning.</h2>
              <p style={{ marginTop: 12 }}>
                Scans persist under <code>~/.atlas_desktop/scans/&lt;repo_id&gt;/</code> (graph,
                index, risks, evidence, signed memory packet). A fresh MCP process validates a
                sorted, content-hashed manifest signature against the live repository; if nothing
                changed, it restores. If anything changed, it refuses the stale scan, tells you
                why, and asks for a rescan.
              </p>
              <p className="note" style={{ marginTop: 12 }}>
                Measured on the controlled 27-file benchmark repository that ships in the Atlas
                source, on one Windows dev machine, using the installed v1.0.1 build: cold scan
                2.22 s; restore into a fresh installed MCP process 8–11 ms with no graph rebuild,
                verified separately for the Claude, Cursor, and Codex launch paths. That is the
                full scope of this claim — no agent-accuracy or token numbers are claimed.
              </p>
            </div>
            <div>
              <p className="eyebrow">Data flow, exactly</p>
              <h2>What leaves your machine.</h2>
              <ol className="steps" style={{ marginTop: 12 }}>
                <li><b>Indexing:</b> local process reads local files. Nothing leaves.</li>
                <li><b>Storage:</b> local disk only (<code>~/.atlas_desktop</code>). Delete that folder and it is gone.</li>
                <li><b>MCP retrieval:</b> stdio between local processes. Nothing leaves.</li>
                <li><b>Agent → model provider:</b> the agent you connected may send retrieved context to its provider under that provider&apos;s terms. That is your agent&apos;s existing data path, not a new Atlas one.</li>
                <li><b>Analytics:</b> aggregate event names only; never code, prompts, or file paths.</li>
              </ol>
              <p style={{ marginTop: 12 }}>
                <Link className="btn btn-ghost" href="/security#data-flow">Full data-flow diagram</Link>
              </p>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-3">
            <div className="card"><h3>30-second flow</h3><p>Install → open Atlas → continue without an account → load the sample repository (or scan your own) → ask &quot;Where is authentication implemented?&quot; → get cited files → connect your agent.</p></div>
            <div className="card"><h3>Languages</h3><p>Deep import/dependency analysis: Python and JavaScript/TypeScript. Scanned at file level: Go, Rust, Java, C#, Ruby, and other common source files. Large monorepos index slower — an active work item.</p></div>
            <div className="card"><h3>SmartScreen</h3><p>The installer is not code-signed yet, so Windows SmartScreen warns on first run (&quot;More info → Run anyway&quot;). Verify the download: SHA256 is published below and on the GitHub release.</p></div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-2">
            <div>
              <p className="eyebrow">Founder note</p>
              <h2>Why this exists</h2>
              <p>I kept re-explaining the same codebase to coding agents — every new session started
                from zero, and CLAUDE.md files drifted the moment the code moved. Atlas is the
                memory layer I wanted: scan once, keep a validated map on disk, let every agent
                read it, and refuse to serve it when it goes stale. Built solo; feedback —
                especially critical — is the point of posting here.</p>
            </div>
            <div className="card">
              <h3>Verify the build</h3>
              <p className="note" style={{ wordBreak: "break-all" }}>
                Atlas_Setup.exe SHA256:<br /><code>{INSTALLER_SHA256}</code>
              </p>
              <p style={{ marginTop: 14 }}>
                <a className="btn btn-ghost" href={GITHUB_RELEASE_URL} target="_blank" rel="noreferrer">GitHub release</a>{" "}
                <Link className="btn btn-ghost" href="/changelog">Changelog</Link>{" "}
                <a className="btn btn-ghost" href={`mailto:${SUPPORT_EMAIL}`}>Contact</a>
              </p>
              <p className="note" style={{ marginTop: 10 }}>
                Source-visible project activity: <a href={GITHUB_URL} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>{GITHUB_URL.replace("https://", "")}</a>
              </p>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container faq" style={{ maxWidth: 820 }}>
            <p className="eyebrow center">FAQ</p>
            <h2 className="center" style={{ marginBottom: 28 }}>HN questions</h2>
            {faq.map(([q, a], i) => (
              <details key={q} open={i === 0}><summary>{q}</summary><p>{a}</p></details>
            ))}
            <p style={{ marginTop: 18 }}>
              <Link className="btn btn-ghost" href="/faq">Full FAQ</Link>
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
