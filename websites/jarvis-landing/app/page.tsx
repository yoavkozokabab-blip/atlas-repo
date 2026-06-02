import Image from "next/image";
import {
  ArrowRight,
  Bot,
  Brain,
  Cpu,
  Database,
  Gauge,
  Layers3,
  LockKeyhole,
  Mic2,
  Network,
  Play,
  Search,
  Send,
  Sparkles,
  Workflow,
  Wrench
} from "lucide-react";

const features = [
  {
    title: "Voice",
    copy: "Speak naturally and move from intent to action without digging through interfaces.",
    icon: Mic2,
    accent: "cyan"
  },
  {
    title: "Tool Use",
    copy: "Route commands through a controlled registry of local tools, apps, and workflows.",
    icon: Wrench,
    accent: "platinum"
  },
  {
    title: "Research",
    copy: "Scan context, inspect evidence, compare sources, and return concise operational answers.",
    icon: Search,
    accent: "blue"
  },
  {
    title: "Memory",
    copy: "Keep durable context for projects, preferences, sessions, and ongoing decisions.",
    icon: Database,
    accent: "green"
  },
  {
    title: "Automation",
    copy: "Schedule, monitor, recover, and continue important work with human approval intact.",
    icon: Workflow,
    accent: "gold"
  }
];

const demoEvents = [
  ["Wake", "Voice detected", "42 ms"],
  ["Understand", "show failing tests", "118 ms"],
  ["Route", "security + registry", "9 ms"],
  ["Act", "pytest diagnostics", "1.2 s"],
  ["Respond", "summary ready", "240 ms"]
];

const architecture = [
  {
    title: "Interface Layer",
    copy: "Voice, console, overlay, and dashboard surfaces feed one command path.",
    icon: Layers3
  },
  {
    title: "Policy Core",
    copy: "Router, security, registry, and approvals keep actions explicit and bounded.",
    icon: LockKeyhole
  },
  {
    title: "Runtime Mesh",
    copy: "Workers, watchdogs, traces, and queues keep the operating system responsive.",
    icon: Network
  },
  {
    title: "Intelligence Plane",
    copy: "Research, memory, automation, and tool selection compound across sessions.",
    icon: Brain
  }
];

export default function Home() {
  return (
    <main>
      <header className="site-header" aria-label="Main navigation">
        <a className="brand" href="#top" aria-label="JARVIS home">
          <span className="brand-mark" aria-hidden="true" />
          JARVIS
        </a>
        <nav className="nav-links">
          <a href="#features">Features</a>
          <a href="#demo">Demo</a>
          <a href="#architecture">Architecture</a>
        </nav>
        <a className="nav-cta" href="#waitlist">
          Join <ArrowRight size={16} strokeWidth={1.8} />
        </a>
      </header>

      <section className="hero" id="top">
        <Image
          src="/jarvis-hero.png"
          alt="Dark futuristic AI operating system interface"
          fill
          priority
          sizes="100vw"
          className="hero-image"
        />
        <div className="hero-shade" aria-hidden="true" />
        <div className="scan-grid" aria-hidden="true" />

        <div className="hero-content">
          <div className="eyebrow">
            <Sparkles size={15} strokeWidth={1.7} />
            Private alpha now forming
          </div>
          <h1>JARVIS</h1>
          <p className="hero-subtitle">Personal AI Operating System</p>
          <p className="hero-copy">
            A voice-native command layer for tools, research, memory, and automation.
            Designed for people who want an AI that operates with context, restraint,
            and speed.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="#waitlist">
              Join waitlist <ArrowRight size={18} strokeWidth={1.8} />
            </a>
            <a className="button button-secondary" href="#demo">
              <Play size={17} fill="currentColor" strokeWidth={1.8} />
              Watch demo
            </a>
          </div>
          <dl className="hero-metrics" aria-label="JARVIS performance highlights">
            <div>
              <dt>Sub-second</dt>
              <dd>voice loop target</dd>
            </div>
            <div>
              <dt>Local-first</dt>
              <dd>tool routing</dd>
            </div>
            <div>
              <dt>Human-led</dt>
              <dd>automation</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="section section-intro" aria-label="Operating system thesis">
        <div className="section-shell intro-grid">
          <p className="kicker">Not another chat window</p>
          <h2>An AI layer that understands the work surface.</h2>
          <p>
            JARVIS connects conversation to operating context: the active window,
            project memory, available tools, runtime health, and the command registry
            that decides what can actually run.
          </p>
        </div>
      </section>

      <section className="section" id="features">
        <div className="section-shell">
          <div className="section-heading">
            <p className="kicker">Core capabilities</p>
            <h2>Everything important, routed through one trusted command path.</h2>
          </div>

          <div className="feature-grid">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article className={`feature-card accent-${feature.accent}`} key={feature.title}>
                  <div className="feature-icon" aria-hidden="true">
                    <Icon size={22} strokeWidth={1.7} />
                  </div>
                  <h3>{feature.title}</h3>
                  <p>{feature.copy}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="section demo-section" id="demo">
        <div className="section-shell demo-grid">
          <div className="demo-copy">
            <p className="kicker">Live command demo</p>
            <h2>Say it once. JARVIS handles the route.</h2>
            <p>
              The demo surface shows the full lifecycle from voice detection to
              final response. Partial understanding can update the HUD, while final
              execution still passes through the router, security checks, and registry.
            </p>
            <div className="signal-row" aria-label="Runtime qualities">
              <span><Gauge size={16} /> Low latency</span>
              <span><LockKeyhole size={16} /> Approval aware</span>
              <span><Cpu size={16} /> Local runtime</span>
            </div>
          </div>

          <div className="demo-console" aria-label="JARVIS demo console">
            <div className="console-bar">
              <span />
              <span />
              <span />
              <strong>voice session</strong>
            </div>
            <div className="console-body">
              <p className="prompt">User</p>
              <p className="command">"JARVIS, review the latest patch and show failing tests."</p>
              <div className="event-list">
                {demoEvents.map(([phase, detail, time]) => (
                  <div className="event-row" key={phase}>
                    <span className="phase">{phase}</span>
                    <span>{detail}</span>
                    <time>{time}</time>
                  </div>
                ))}
              </div>
              <div className="response">
                <Bot size={18} strokeWidth={1.7} />
                <p>Two regressions found. Screenshot pruning is fixed. Runtime checks pass.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section architecture-section" id="architecture">
        <div className="section-shell">
          <div className="section-heading">
            <p className="kicker">Architecture</p>
            <h2>Built like an operating layer, not a novelty assistant.</h2>
          </div>

          <div className="architecture-map">
            {architecture.map((layer, index) => {
              const Icon = layer.icon;
              return (
                <article className="architecture-node" key={layer.title}>
                  <span className="node-index">0{index + 1}</span>
                  <Icon size={22} strokeWidth={1.7} aria-hidden="true" />
                  <h3>{layer.title}</h3>
                  <p>{layer.copy}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="section waitlist-section" id="waitlist">
        <div className="section-shell waitlist-panel">
          <div>
            <p className="kicker">Join waitlist</p>
            <h2>Build your personal command layer.</h2>
            <p>
              Early access is for builders, operators, and researchers who want
              an AI that can understand context and execute through guardrails.
            </p>
          </div>
          <form className="waitlist-form" action="/api/waitlist" method="post">
            <label htmlFor="email">Email</label>
            <div className="form-row">
              <input id="email" name="email" type="email" placeholder="you@company.com" required />
              <button className="button button-primary" type="submit">
                <Send size={17} strokeWidth={1.8} />
                Request access
              </button>
            </div>
            <label htmlFor="role">What will you run with JARVIS?</label>
            <input
              id="role"
              name="role"
              type="text"
              placeholder="Research, dev tools, trading ops, personal automation..."
            />
          </form>
        </div>
      </section>

      <footer className="site-footer">
        <span>JARVIS</span>
        <span>Personal AI Operating System</span>
      </footer>
    </main>
  );
}
