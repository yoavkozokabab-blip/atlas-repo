import Link from "next/link";
import { SiteNav, SiteFooter } from "./_components/site";

export default function Home() {
  return (
    <>
      {/* NAV */}
      <SiteNav />

      <main>
        {/* HERO */}
        <section className="hero">
          <div className="container hero-grid">
            <div>
              <p className="eyebrow">Local-first repository memory</p>
              <h1>
                Give Cursor and Claude a <span className="grad">memory of your codebase.</span>
              </h1>
              <p>
                Scan once, on your machine. Atlas maps your architecture, dependency
                graph, risk and impact - then gives Cursor, Claude and Codex
                local-first repo memory instead of letting them guess.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary btn-lg" href="/download">Download for Windows</Link>
                <a className="btn btn-ghost btn-lg" href="#see-it-work">See it work</a>
              </div>
              <p className="hero-note">
                Free to start · your code never leaves your machine · Windows installer
              </p>
            </div>
            <div className="hero-visual">
              <GraphCard />
            </div>
          </div>
        </section>

        {/* PROOF */}
        <div className="container">
          <div className="proof" aria-label="Works with">
            <span>Works with</span>
            <span>Claude</span><span>Codex</span><span>Cursor</span>
          </div>
        </div>

        {/* PILLARS */}
        <section className="section">
          <div className="container">
            <div className="grid-3">
              <Pillar t="Understands" d="Builds a real map of your repo - subsystems, a dependency graph, hubs and architectural risk - not a flat file dump." />
              <Pillar t="Grounds" d="Evidence-backed plans that name the exact files. Atlas refuses stale or unverifiable context rather than hallucinating." />
              <Pillar t="Stays private" d="Local-first by design. Scanning and analysis run on your machine; only the context you choose to copy ever leaves it." />
            </div>
          </div>
        </section>

        {/* SEE IT WORK */}
        <section className="section" id="see-it-work">
          <div className="container">
            <div className="grid-2">
              <div>
                <p className="eyebrow">See it work</p>
                <h2>The context your agent actually needs.</h2>
                <p className="lead" style={{ marginTop: 18 }}>
                  Point Atlas at a repo, describe a change, and it returns the files
                  to touch, what may break, and the verification steps. Ask Atlas,
                  Impact, Debug and Plan Change keep your AI tool grounded in the
                  repository you actually scanned.
                </p>
              </div>
              <div className="terminal" role="img" aria-label="Example Atlas answer with cited files">
                <div className="head">
                  <span className="dot" /><span className="dot" /><span className="dot" />
                </div>
                <pre>{`Ask Atlas: Where is authentication implemented?

Answer:
Authentication is wired through services/auth.py and api/routes.py.
The middleware guards API handlers before request dispatch.

Cited files:
  services/auth.py
  api/routes.py
  tests/test_auth.py

`}<span className="c"># confidence: medium-high · evidence-backed</span></pre>
              </div>
            </div>
          </div>
        </section>

        {/* TRUST / LOCAL-FIRST */}
        <section className="section">
          <div className="container">
            <div className="band">
              <div>
                <p className="eyebrow">Private by design</p>
                <h2>Your code never leaves your machine.</h2>
                <p style={{ marginTop: 16 }}>
                  Atlas runs locally. Repository scanning, the dependency graph and
                  analysis all happen on your device. The only thing that travels is
                  the answer or prompt you explicitly send to your AI tool.
                </p>
              </div>
              <div className="flow" aria-label="Data flow">
                <div className="row"><span className="tag local">Local</span> Repository scan + dependency graph</div>
                <div className="row"><span className="tag local">Local</span> Architecture, risk &amp; impact analysis</div>
                <div className="row"><span className="tag local">Local</span> Ask Atlas, Impact, Debug and Plan Change</div>
                <div className="row"><span className="tag net">You choose</span> Send the result to Claude / Codex / Cursor</div>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ TEASER */}
        <section className="section">
          <div className="container" style={{ maxWidth: 760 }}>
            <p className="eyebrow center">FAQ</p>
            <h2 className="center" style={{ marginBottom: 32 }}>Questions, answered.</h2>
            <div className="faq">
              <details open>
                <summary>Does my code leave my machine?</summary>
                <p>No. Scanning and analysis run locally; only the output you choose to send goes wherever you paste it.</p>
              </details>
              <details>
                <summary>Does Atlas replace Claude, Codex or Cursor?</summary>
                <p>No - it makes them better by giving them your repository&apos;s real structure instead of letting them guess.</p>
              </details>
              <details>
                <summary>Will it invent files or give stale context?</summary>
                <p>No. Atlas is evidence-backed and refuses stale or unverifiable context rather than hallucinating.</p>
              </details>
              <details>
                <summary>What platforms are supported?</summary>
                <p>Atlas is available today as a Windows installer.</p>
              </details>
            </div>
          </div>
        </section>

        {/* GET STARTED */}
        <section className="section" id="get-started">
          <div className="container" style={{ maxWidth: 760 }}>
            <div className="band">
              <div>
                <p className="eyebrow">Start using Atlas</p>
                <h2>Create an account, download Atlas, and connect your AI tool.</h2>
                <p style={{ marginTop: 14 }}>
                  Atlas works with Claude, Cursor and Codex. Create an account, install
                  the Windows app, scan a repository, then copy local-first context into
                  the AI coding agent you already use.
                </p>
              </div>
              <div style={{ alignSelf: "center", width: "100%" }}>
                <Link className="btn btn-primary btn-lg" href="/download">Download Atlas</Link>
                <Link className="btn btn-ghost btn-lg" href="/login" style={{ marginLeft: 10 }}>Sign in</Link>
              </div>
            </div>
          </div>
        </section>

      </main>

      {/* FOOTER */}
      <SiteFooter />
    </>
  );
}

function Pillar({ t, d }: { t: string; d: string }) {
  return (
    <div className="card">
      <h3>{t}</h3>
      <p>{d}</p>
    </div>
  );
}

function GraphCard() {
  const nodes = [
    { x: 70, y: 60, r: 9, hub: true },
    { x: 180, y: 40, r: 5, hub: false },
    { x: 250, y: 110, r: 7, hub: true },
    { x: 130, y: 130, r: 5, hub: false },
    { x: 60, y: 170, r: 5, hub: false },
    { x: 200, y: 190, r: 6, hub: false },
    { x: 300, y: 60, r: 5, hub: false },
    { x: 320, y: 170, r: 5, hub: false }
  ];
  const edges = [
    [0, 1], [0, 3], [0, 4], [1, 2], [2, 5], [2, 6], [3, 5], [2, 7], [6, 7]
  ];
  return (
    <div className="graph-card">
      <div className="bar"><span className="dot" /><span className="dot" /><span className="dot" /></div>
      <svg viewBox="0 0 360 230" width="100%" height="auto" role="img" aria-label="Dependency graph visualization">
        {edges.map(([a, b], i) => (
          <line
            key={i}
            className={i % 3 === 0 ? "edge bridge" : "edge"}
            x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
            strokeWidth={i % 3 === 0 ? 1.6 : 0.9}
          />
        ))}
        {nodes.map((n, i) => (
          <circle
            key={i}
            className={n.hub ? "pulse" : undefined}
            cx={n.x} cy={n.y} r={n.r}
            fill={n.hub ? "var(--accent)" : "var(--accent-2)"}
            opacity={n.hub ? 1 : 0.7}
          />
        ))}
      </svg>
    </div>
  );
}
