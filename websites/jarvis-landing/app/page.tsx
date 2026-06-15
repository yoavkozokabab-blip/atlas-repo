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
              <p className="eyebrow">Repository intelligence · local-first</p>
              <h1>
                Stop making AI <span className="grad">re-read your repository.</span>
              </h1>
              <p>
                Atlas maps your codebase once, on your machine, into architecture, a
                dependency graph, risk and impact — then hands Claude, Codex and
                Cursor evidence-backed context instead of letting them guess.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary btn-lg" href="/download">Download for Windows</Link>
                <a className="btn btn-ghost btn-lg" href="#see-it-work">See it work</a>
              </div>
              <p className="hero-note">Free to start · your code never leaves your machine</p>
            </div>
            <div className="hero-visual">
              <GraphCard />
            </div>
          </div>
        </section>

        {/* PROOF */}
        <div className="container">
          <div className="proof" aria-label="Works with">
            <span>WORKS WITH</span>
            <span>Claude</span><span>Codex</span><span>Cursor</span><span>Copilot</span>
          </div>
        </div>

        {/* PILLARS */}
        <section className="section">
          <div className="container">
            <div className="grid-3">
              <Pillar t="Understands" d="Builds a real map of your repo — subsystems, a dependency graph, hubs and architectural risk — not a flat file dump." />
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
                  to touch, what may break, and the verification steps — then exports
                  a clean, compact packet for your AI tool. No internal noise, no
                  guessing.
                </p>
              </div>
              <div className="terminal" role="img" aria-label="Example Atlas context export for Claude">
                <div className="head">
                  <span className="dot" /><span className="dot" /><span className="dot" />
                </div>
                <pre>{`# ATLAS REPOSITORY CONTEXT — your-service
scope=full  modules=73  edges=159  cycles=0

## CHANGE PLAN — "add authentication"
files to inspect first:
  services/auth.py        # entry point
  api/routes.py           # wire the middleware
likely to break:
  api/handlers.py         # depends on auth
verify:
  tests/test_auth.py

`}<span className="c"># confidence: medium-high · evidence-backed</span></pre>
              </div>
            </div>
          </div>
        </section>

        {/* FEATURES */}
        <section className="section">
          <div className="container">
            <p className="eyebrow center">Built for serious codebases</p>
            <h2 className="center" style={{ marginBottom: 40 }}>Everything your AI is missing about your repo.</h2>
            <div className="grid-3">
              <Feature ic="{}" t="Dependency graph" d="A precise, navigable map of how your modules really connect — hubs, cycles and blast radius." />
              <Feature ic="Δ" t="Impact analysis" d="Change a file, see exactly what depends on it and which tests to run before you ship." />
              <Feature ic="?" t="Investigation mode" d="Trace a symptom to the likely files with grounded evidence, not vibes." />
              <Feature ic="!" t="Risk detection" d="Surface the architectural risk hotspots that make changes dangerous." />
              <Feature ic="⌘" t="AI context export" d="One click to a compact, evidence-backed packet for Claude, Codex or Cursor." />
              <Feature ic="◐" t="Local-first" d="No upload, no cloud scan. Your source stays on your machine, always." />
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
                  the compact context you explicitly copy into your AI tool.
                </p>
              </div>
              <div className="flow" aria-label="Data flow">
                <div className="row"><span className="tag local">LOCAL</span> Repository scan + dependency graph</div>
                <div className="row"><span className="tag local">LOCAL</span> Architecture, risk &amp; impact analysis</div>
                <div className="row"><span className="tag local">LOCAL</span> Context packet generated on your machine</div>
                <div className="row"><span className="tag net">YOU CHOOSE</span> Paste the packet into Claude / Codex / Cursor</div>
              </div>
            </div>
          </div>
        </section>

        {/* PRICING TEASER */}
        <section className="section">
          <div className="container">
            <p className="eyebrow center">Pricing</p>
            <h2 className="center" style={{ marginBottom: 40 }}>Simple pricing for serious codebases.</h2>
            <div className="tiers">
              <div className="tier">
                <h3>Free</h3>
                <div className="price">$0</div>
                <ul>
                  <li>Local scanning &amp; architecture map</li>
                  <li>One repository</li>
                  <li>Basic Change Plans</li>
                </ul>
                <Link className="btn btn-ghost" href="/download">Download</Link>
              </div>
              <div className="tier feat">
                <h3>Pro</h3>
                <div className="price">$29<small> / month</small></div>
                <ul>
                  <li>Unlimited repositories</li>
                  <li>Impact analysis &amp; investigation</li>
                  <li>AI context compression</li>
                  <li>Architecture risk detection</li>
                  <li>Priority support</li>
                </ul>
                <Link className="btn btn-primary" href="/checkout/plan/pro">Start 7-day trial</Link>
              </div>
              <div className="tier">
                <h3>Team</h3>
                <div className="price">Talk to us</div>
                <ul>
                  <li>Shared context &amp; seats</li>
                  <li>SSO</li>
                  <li>For engineering teams</li>
                </ul>
                <Link className="btn btn-ghost" href="/contact">Contact</Link>
              </div>
            </div>
            <p className="center muted" style={{ marginTop: 22, fontSize: "0.85rem" }}>
              Local-first · 7-day trial, no card · cancel anytime
            </p>
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
                <p>No. Scanning and analysis run locally; only the compact context you choose to copy goes wherever you paste it.</p>
              </details>
              <details>
                <summary>Does Atlas replace Claude, Codex or Cursor?</summary>
                <p>No — it makes them better by giving them your repository&apos;s real structure instead of letting them guess.</p>
              </details>
              <details>
                <summary>Will it invent files or give stale context?</summary>
                <p>No. Atlas is evidence-backed and refuses stale or unverifiable context rather than hallucinating.</p>
              </details>
              <details>
                <summary>What platforms are supported?</summary>
                <p>Windows today. macOS and Linux are on the waitlist.</p>
              </details>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="section">
          <div className="container">
            <div className="cta">
              <h2>Make your AI fluent in your codebase.</h2>
              <p className="center" style={{ marginTop: 14, marginBottom: 28 }}>
                Local. Deterministic. Free to start.
              </p>
              <Link className="btn btn-primary btn-lg" href="/download">Download Atlas</Link>
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

function Feature({ ic, t, d }: { ic: string; t: string; d: string }) {
  return (
    <div className="card">
      <div className="ic mono" aria-hidden>{ic}</div>
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
