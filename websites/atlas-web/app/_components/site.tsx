import Link from "next/link";
import AtlasMark from "./AtlasMark";
import SiteNav from "./nav/SiteNav";
import {
  GITHUB_RELEASE_URL,
  GITHUB_URL,
  INSTALLER_SHA256,
  SUPPORT_EMAIL,
  supportMailto,
} from "../_config";
import { AGENTS, facts, limitations } from "../lib/content/facts";

export { default as SiteNav } from "./nav/SiteNav";

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-top">
          <div className="footer-brand">
            <Link className="brand site-brand" href="/" aria-label="Atlas home">
              <AtlasMark size={28} className="mark" /> Atlas
            </Link>
            <p>
              Local-first repository memory for Claude Code, Cursor and Codex.
              The index lives on your machine; agents get cited context when you ask.
            </p>
            <div className="footer-meta mono">
              <span>v{facts.version}</span>
              <span>{facts.platform}</span>
              <span>{facts.mcpTools} MCP tools</span>
            </div>
          </div>
          <div className="footer-cta">
            <Link className="btn-mag" href="/download" data-evt="download_click">
              Download Atlas <span className="arw" aria-hidden>→</span>
            </Link>
            <Link className="btn-line" href="/docs">Read docs</Link>
          </div>
        </div>
        <div className="footer-grid">
          <div>
            <h4>Product</h4>
            <Link href="/features">Product</Link>
            <Link href="/how-it-works">How it works</Link>
            <Link href="/integrations">Integrations</Link>
            <Link href="/pricing">Pricing</Link>
            <Link href="/download">Download</Link>
          </div>
          <div>
            <h4>Proof</h4>
            <Link href="/benchmarks">Benchmarks</Link>
            <Link href="/compare">Compare</Link>
            <Link href="/changelog">Changelog</Link>
            <Link href="/releases">Releases</Link>
            <Link href="/roadmap">Roadmap</Link>
            <Link href="/faq">FAQ</Link>
          </div>
          <div>
            <h4>Trust</h4>
            <Link href="/security">Security</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/refund">Refund</Link>
            <Link href="/cancellation">Cancellation</Link>
          </div>
          <div>
            <h4>Company</h4>
            <Link href="/about">About</Link>
            <Link href="/docs">Docs</Link>
            <Link href="/contact">Contact</Link>
            <a href={GITHUB_URL} target="_blank" rel="noreferrer">GitHub</a>
            <a href={GITHUB_RELEASE_URL} target="_blank" rel="noreferrer">Latest release</a>
            {SUPPORT_EMAIL ? (
              <a href={supportMailto()}>{SUPPORT_EMAIL}</a>
            ) : (
              <Link href="/contact">Contact us</Link>
            )}
          </div>
        </div>
        <div className="legal">
          © 2026 Atlas. Local-first repository intelligence. Windows only today;
          installer may show SmartScreen until signing is complete.
        </div>
      </div>
    </footer>
  );
}

/** Four-step install strip: Download -> Install -> Load sample -> Connect. */
export function InstallFlow() {
  return (
    <div className="install-flow" aria-label="Install steps">
      <span className="if-step">Download</span>
      <span className="if-arrow" aria-hidden>→</span>
      <span className="if-step">Install</span>
      <span className="if-arrow" aria-hidden>→</span>
      <span className="if-step">Load sample repository</span>
      <span className="if-arrow" aria-hidden>→</span>
      <span className="if-step">Connect Claude / Cursor / Codex</span>
      <span className="muted mono" style={{ fontSize: "0.8rem" }}>· No login required</span>
    </div>
  );
}

export function PageHero({
  eyebrow,
  title,
  intro,
  meta = [],
  actions,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  meta?: string[];
  actions?: React.ReactNode;
}) {
  return (
    <section className="page-head premium-head">
      <div className="container premium-head-grid">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="page-title">{title}</h1>
          {intro ? <p className="lead" style={{ marginTop: 18 }}>{intro}</p> : null}
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
        <div className="page-map" aria-hidden>
          <span className="map-node n1" />
          <span className="map-node n2" />
          <span className="map-node n3" />
          <span className="map-line l1" />
          <span className="map-line l2" />
          <span className="map-line l3" />
        </div>
      </div>
      {meta.length ? (
        <div className="container">
          <div className="meta-row">
            {meta.map((item) => <span key={item}>{item}</span>)}
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** Standard page shell for content pages (nav + hero header + footer). */
export function PageShell({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <SiteNav />
      <main id="main-content">
        <PageHero eyebrow={eyebrow} title={title} intro={intro} />
        {children}
      </main>
      <SiteFooter />
    </>
  );
}

export function PremiumSection({
  eyebrow,
  title,
  intro,
  children,
  className = "",
}: {
  eyebrow?: string;
  title?: string;
  intro?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`section premium-section ${className}`}>
      <div className="container">
        {eyebrow || title || intro ? (
          <div className="section-head">
            {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
            {title ? <h2>{title}</h2> : null}
            {intro ? <p className="lead" style={{ marginTop: 14 }}>{intro}</p> : null}
          </div>
        ) : null}
        {children}
      </div>
    </section>
  );
}

export function AsymSection({
  eyebrow,
  title,
  intro,
  aside,
  children,
}: {
  eyebrow?: string;
  title: string;
  intro?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="asym">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {intro ? <p className="lead" style={{ marginTop: 14 }}>{intro}</p> : null}
        {aside ? <div className="asym-aside">{aside}</div> : null}
      </div>
      <div>{children}</div>
    </div>
  );
}

export function EvidenceBlock({
  question,
  rows,
}: {
  question: string;
  rows: Array<{ path: string; relation: string; reason: string }>;
}) {
  return (
    <div className="evidence evidence-premium">
      <div className="evidence-q">{question}</div>
      {rows.map((row) => (
        <div className="evidence-row" key={row.path}>
          <span className="path">{row.path}</span>
          <span className="rel">{row.relation}</span>
          <span className="reason">{row.reason}</span>
        </div>
      ))}
    </div>
  );
}

export function MetricBlock({ metrics }: { metrics: Array<[string, string]> }) {
  return (
    <div className="metrics metric-block">
      {metrics.map(([value, label]) => (
        <div className="metric" key={label}>
          <span className="metric-v mono">{value}</span>
          <span className="metric-l">{label}</span>
        </div>
      ))}
    </div>
  );
}

export function TechnicalDiagram({
  title = "Local Atlas path",
  items,
}: {
  title?: string;
  items: Array<[string, string]>;
}) {
  return (
    <div className="tech-diagram" aria-label={title}>
      <div className="tech-diagram-head mono">
        <span>{title}</span>
        <span>deterministic</span>
      </div>
      <div className="tech-path">
        {items.map(([label, detail], index) => (
          <div className="tech-step" key={label}>
            <span className="tech-index mono">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h3>{label}</h3>
              <p>{detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function InstallationBlock() {
  return (
    <div className="install-block">
      <div>
        <p className="eyebrow">Windows release</p>
        <h3>Atlas-Setup-{facts.version}.exe · v{facts.version}</h3>
        <p className="dl-meta">SHA256: <code>{INSTALLER_SHA256}</code></p>
        <p className="note" style={{ marginTop: 10 }}>
          No signup required. Windows SmartScreen may warn until the installer is signed.
        </p>
      </div>
      <div className="install-actions">
        <a className="btn-mag" href="/download/atlas" data-evt="download_click">
          Download Atlas <span className="arw" aria-hidden>→</span>
        </a>
        <a className="btn-line" href={GITHUB_RELEASE_URL} target="_blank" rel="noreferrer">
          Verify release
        </a>
      </div>
    </div>
  );
}

export function TrustBlock() {
  return (
    <div className="trust-block">
      {limitations.slice(0, 4).map((item) => (
        <div className="trust-row" key={item}>
          <span className="trust-marker" aria-hidden />
          <p>{item}</p>
        </div>
      ))}
    </div>
  );
}

export function IntegrationStatusBlock() {
  const integrations = [
    ...AGENTS.map((agent) => [agent, "Supported"] as const),
    ["MCP clients", "Experimental"] as const,
  ];
  return (
    <div className="integ-bar status-block">
      {integrations.map(([name, level]) => (
        <div className="integ-cell" key={name}>
          <span className="integ-name">{name}</span>
          <span className={`integ-badge ${level === "Supported" ? "ok" : "exp"}`}>{level}</span>
        </div>
      ))}
    </div>
  );
}

export function ReleaseVersionBlock() {
  return (
    <div className="release-block">
      <div>
        <span className="mono">current release</span>
        <strong>Atlas v{facts.version}</strong>
      </div>
      <div>
        <span className="mono">platform</span>
        <strong>{facts.platform}</strong>
      </div>
      <div>
        <span className="mono">distribution</span>
        <strong>Unsigned installer</strong>
      </div>
    </div>
  );
}
