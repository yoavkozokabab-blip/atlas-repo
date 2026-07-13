import Link from "next/link";
import { facts } from "../../lib/content/facts";
import { GITHUB_URL, DOWNLOAD_URL, INSTALLER_SHA256 } from "../../_config";

const capabilities = [
  ["01", "Ask Atlas", "Where behavior lives, why a module matters, which files are involved — answered with real citations from the local index."],
  ["02", "Impact", "The files a change is likely to affect and the dependency paths between them, before you touch a subsystem."],
  ["03", "Debug", "Start from an error or symptom; Atlas parses the traceback to repo files and symbol spans and returns an investigation path."],
] as const;

const integrations = [
  ["Claude Code", "Supported"],
  ["Cursor", "Supported"],
  ["Codex", "Supported"],
  ["MCP clients", "Experimental"],
] as const;

const metrics = [
  [facts.sampleIndexLabel, `index · ${facts.sampleFiles}-file sample repo`],
  [facts.askLatencyLabel, "Ask Atlas latency"],
  [facts.restoreMsLabel, "restore across sessions"],
  ["0.95–0.98", "file recall · 50 scenarios"],
  [String(facts.mcpTools), "MCP tools"],
] as const;

const faqs = [
  ["Do I need an account to download Atlas?", "No. Download the Windows installer and start locally — there's a guest mode with no signup."],
  ["Does Atlas replace my AI coding agent?", "No. Atlas gives Claude Code, Cursor, and Codex a persistent, cited memory of your repository that they can use."],
  ["Does Atlas upload my source code?", "No. Repository indexing runs on your machine. You decide what context to send to an agent."],
  ["How is this different from repeated file search?", "Atlas builds a dependency graph + evidence store once and restores it in milliseconds across sessions, returning ranked, cited files — not a fresh grep each time."],
] as const;

export default function HomeSections() {
  return (
    <div className="content-below">
      {/* Capabilities — editorial list, not a card grid */}
      <section className="section cap">
        <div className="container cap-grid">
          <div className="cap-intro">
            <p className="eyebrow">Capabilities</p>
            <h2>Ask in the language of your codebase.</h2>
            <p className="lead" style={{ marginTop: 16 }}>
              Three kinds of question, each grounded in cited files. No model in the
              retrieval loop — deterministic lookups against the local index.
            </p>
          </div>
          <ol className="cap-list">
            {capabilities.map(([n, title, body]) => (
              <li key={title}>
                <span className="cap-n mono">{n}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Integrations */}
      <section className="section integ">
        <div className="container">
          <div className="head-row">
            <div>
              <p className="eyebrow">Integrations</p>
              <h2>Built for the agents you already use.</h2>
            </div>
            <Link className="btn-line" href="/integrations">All integrations <span aria-hidden>→</span></Link>
          </div>
          <div className="integ-bar">
            {integrations.map(([name, level]) => (
              <div className="integ-cell" key={name}>
                <span className="integ-name">{name}</span>
                <span className={`integ-badge ${level === "Supported" ? "ok" : "exp"}`}>{level}</span>
              </div>
            ))}
          </div>
          <div className="integ-config">
            <div className="integ-config-head mono">
              <span>mcp config</span>
              <span className="muted">Model Context Protocol · stdio</span>
            </div>
            <pre className="mono">{`{
  "mcpServers": {
    "atlas": { "command": "Atlas.exe", "args": ["--mcp"] }
  }
}`}</pre>
          </div>
          <p className="note" style={{ marginTop: 14 }}>
            The same local index serves every agent — your source never leaves the machine.
            Exact per-client setup is in the <Link href="/docs">docs</Link>.
          </p>
        </div>
      </section>

      {/* Proof — big mono metrics, not centered pills */}
      <section className="section proof-band">
        <div className="container">
          <div className="head-row">
            <div>
              <p className="eyebrow">Proof</p>
              <h2>Measured, not marketed.</h2>
            </div>
            <Link className="btn-line" href="/benchmarks">Methodology &amp; limits <span aria-hidden>→</span></Link>
          </div>
          <div className="metrics">
            {metrics.map(([v, l]) => (
              <div className="metric" key={l}>
                <span className="metric-v mono">{v}</span>
                <span className="metric-l">{l}</span>
              </div>
            ))}
          </div>
          <p className="note" style={{ marginTop: 22 }}>
            Self-measured on one Windows machine against a reference repository, not a random
            OSS sample. Every number has a reproducible harness in the repo.
          </p>
        </div>
      </section>

      {/* Local-first */}
      <section className="section">
        <div className="container">
          <div className="band">
            <div>
              <p className="eyebrow">Local-first</p>
              <h2>Your repo is indexed on your machine.</h2>
              <p style={{ marginTop: 14 }}>
                Atlas scans local files, builds a repository map, and returns cited answers from
                that local index. It does not upload your repository to a hosted analysis service.
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

      {/* FAQ — two-column editorial */}
      <section className="section faq-sec">
        <div className="container faq-grid">
          <div className="faq-intro">
            <p className="eyebrow">FAQ</p>
            <h2>Before you try it.</h2>
            <p style={{ marginTop: 14 }}>
              More questions? <Link href="/faq">Read the full FAQ</Link> or{" "}
              <Link href="/contact">contact us</Link>.
            </p>
          </div>
          <div className="faq faq-list">
            {faqs.map(([q, a], i) => (
              <details key={q} open={i === 0}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Download strip */}
      <section className="section dl-strip-sec">
        <div className="container">
          <div className="dl-strip">
            <div>
              <h2>Download Atlas.</h2>
              <p className="mono dl-strip-meta">
                {facts.platform} · v{facts.version} · SHA-256 {INSTALLER_SHA256.slice(0, 12).toLowerCase()}… · no signup
              </p>
            </div>
            <div className="dl-strip-cta">
              <Link className="btn-mag" href={DOWNLOAD_URL} data-evt="download_click">
                Download Atlas <span className="arw" aria-hidden>→</span>
              </Link>
              <a className="btn-line" href={GITHUB_URL} target="_blank" rel="noreferrer">View on GitHub</a>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
