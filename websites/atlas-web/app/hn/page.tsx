import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";
import { GITHUB_URL, SUPPORT_EMAIL } from "../_config";

export const metadata: Metadata = {
  title: "Atlas for Hacker News",
  description: "Try persistent repo memory in 30 seconds. Atlas indexes repositories locally and gives AI coding agents cited files.",
};

const faq = [
  ["Is this a hosted code indexing service?", "No. Atlas indexes your repository locally on your machine."],
  ["What does it send to Claude Code or Cursor?", "Only the context you choose to send through the connected agent workflow."],
  ["Can I inspect exact files?", "Yes. Atlas answers are designed around cited files and local paths."],
  ["What is rough today?", "Windows is the supported installer. macOS and Linux are not available yet, and Pro checkout may be disabled until Paddle credentials are configured."],
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
              <h1>Try persistent repo memory in 30 seconds</h1>
              <p>
                Built for developers who are tired of re-explaining the same codebase to AI coding agents.
              </p>
              <p>
                Atlas indexes your repository locally, then gives Claude Code, Cursor, and Codex cited context for questions, debugging, and change planning.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary btn-lg" href="/download">Download Atlas</Link>
              </div>
              <p className="hero-note">No signup required · Local-first · Your code stays on your machine</p>
            </div>
            <div className="product-panel">
              <div className="product-top"><span>Sample flow</span><span className="status-dot">Local</span></div>
              <div className="product-body">
                <div className="product-question">Ask: what breaks if auth changes?</div>
                <div className="product-answer">Atlas maps likely callers, tests, and config files, then returns cited paths you can hand to an agent.</div>
                <div className="citations"><span>services/auth.py</span><span>api/routes.py</span><span>tests/test_auth.py</span></div>
              </div>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-2">
            <div>
              <p className="eyebrow">Founder note</p>
              <h2>Why this exists</h2>
              <p>I wanted AI coding agents to stop losing repo context between sessions. Atlas is a local memory layer: scan the repo, keep the map, cite the files, and let the agent work from something concrete.</p>
            </div>
            <div>
              <p className="eyebrow">What it does not do</p>
              <h2>Boundaries</h2>
              <p>Atlas does not claim to replace your coding agent, certify code security, or support non-Windows installers today. It is a local companion for repo context.</p>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-3">
            <div className="card"><h3>What it does</h3><p>Indexes your repository locally, builds a repo map, and answers with cited files.</p></div>
            <div className="card"><h3>Privacy</h3><p>Your source stays on your machine. You choose what context to send to external agents.</p></div>
            <div className="card"><h3>Install</h3><p>Download the Windows installer, open a repo, connect your agent, and ask a question.</p></div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container grid-2">
            <div className="card">
              <h3>Limitations</h3>
              <ul>
                <li>Windows installer only today.</li>
                <li>No claim of signed installer unless the release artifact is signed.</li>
                <li>Pro checkout depends on Paddle configuration.</li>
                <li>Atlas can still be wrong; cited files make verification faster.</li>
              </ul>
            </div>
            <div className="card">
              <h3>Changelog</h3>
              <ul>
                <li>Launch copy simplified around download, connect, and use.</li>
                <li>MCP setup writes local agent config instead of asking users to copy by default.</li>
                <li>Public download no longer requires login.</li>
              </ul>
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
            <p style={{ marginTop: 24 }}>
              <a className="btn btn-ghost" href={GITHUB_URL} target="_blank" rel="noreferrer">GitHub release</a>{" "}
              <a className="btn btn-ghost" href={`mailto:${SUPPORT_EMAIL}`}>Contact</a>
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
