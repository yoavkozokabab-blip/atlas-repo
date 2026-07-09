import Link from "next/link";
import { SiteNav, SiteFooter } from "./_components/site";

const flows = [
  ["1", "Download Atlas", "Install the Windows app and open your repo locally."],
  ["2", "Connect your agent", "Use the built-in setup for Claude Code, Cursor, or Codex."],
  ["3", "Ask with context", "Atlas answers with cited files you can hand to your AI coding agent."],
] as const;

const agents = [
  ["Claude Code", "Connect Atlas through MCP and ask repo-aware questions from your coding workflow."],
  ["Cursor", "Give Cursor cited local context instead of re-explaining the same files each session."],
  ["Codex", "Use Atlas context when planning changes, debugging behavior, or mapping an unfamiliar repo."],
] as const;

const features = [
  ["Ask Atlas", "Ask where behavior lives, why a module matters, or which files are involved. Answers cite real files from the local index."],
  ["Impact", "See likely affected files and dependency paths before you change a subsystem."],
  ["Debug", "Start from an error or symptom and get a repo-grounded investigation path."],
] as const;

export default function Home() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="hero launch-hero">
          <div className="container hero-grid">
            <div>
              <p className="eyebrow">Local-first memory for AI coding agents</p>
              <h1>Persistent repo memory for Claude Code and Cursor</h1>
              <p>
                Atlas indexes your repository locally, then helps AI coding agents answer
                questions, debug issues, and plan changes with cited files.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary btn-lg" href="/download">Download Atlas</Link>
              </div>
              <p className="hero-note">No signup required · Local-first · Your code stays on your machine</p>
            </div>
            <ProductPanel />
          </div>
        </section>

        <section className="section compact-section" id="flow">
          <div className="container">
            <div className="section-head">
              <p className="eyebrow">30-second flow</p>
              <h2>Install, connect, ask.</h2>
            </div>
            <div className="grid-3">
              {flows.map(([n, title, body]) => (
                <div className="card step-card" key={title}>
                  <span className="step-num">{n}</span>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container">
            <div className="section-head">
              <p className="eyebrow">Works with</p>
              <h2>Claude Code, Cursor, and Codex.</h2>
            </div>
            <div className="grid-3">
              {agents.map(([title, body]) => (
                <div className="card" key={title}>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container">
            <div className="grid-3">
              {features.map(([title, body]) => (
                <div className="card" key={title}>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container">
            <div className="band">
              <div>
                <p className="eyebrow">Local-first</p>
                <h2>Your repo is indexed on your machine.</h2>
                <p style={{ marginTop: 14 }}>
                  Atlas scans local files, builds a repository map, and returns cited
                  answers from that local index. It does not upload your repository to
                  a hosted analysis service.
                </p>
              </div>
              <div className="flow" aria-label="Atlas local workflow">
                <div className="row"><span className="tag local">Local</span> Repository index</div>
                <div className="row"><span className="tag local">Local</span> Dependency and impact map</div>
                <div className="row"><span className="tag local">Local</span> Cited answers</div>
                <div className="row"><span className="tag net">You choose</span> Send context to an agent</div>
              </div>
            </div>
          </div>
        </section>

        <section className="section compact-section">
          <div className="container" style={{ maxWidth: 780 }}>
            <p className="eyebrow center">FAQ</p>
            <h2 className="center" style={{ marginBottom: 28 }}>Short answers before you try it.</h2>
            <div className="faq">
              <details open>
                <summary>Do I need an account to download Atlas?</summary>
                <p>No. Download the Windows installer and start locally.</p>
              </details>
              <details>
                <summary>Does Atlas replace my AI coding agent?</summary>
                <p>No. Atlas gives Claude Code, Cursor, and Codex repo memory they can use.</p>
              </details>
              <details>
                <summary>Does Atlas upload my source code?</summary>
                <p>No. Repository indexing runs locally. You decide what context to send elsewhere.</p>
              </details>
            </div>
            <p className="center" style={{ marginTop: 24 }}>
              <Link className="btn btn-ghost" href="/faq">Read the full FAQ</Link>
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

function ProductPanel() {
  return (
    <div className="product-panel" aria-label="Atlas product preview">
      <div className="product-top">
        <span>Atlas</span>
        <span className="status-dot">Local index ready</span>
      </div>
      <div className="product-body">
        <div className="product-question">Where is login state handled?</div>
        <div className="product-answer">
          Login state is managed in <b>app/_lib/auth.ts</b>. The session route
          reads the signed cookie, and desktop login uses the same account state.
        </div>
        <div className="citations">
          <span>app/_lib/auth.ts</span>
          <span>app/api/auth/session/route.ts</span>
          <span>atlas_desktop/static/atlas_accounts.js</span>
        </div>
      </div>
    </div>
  );
}
