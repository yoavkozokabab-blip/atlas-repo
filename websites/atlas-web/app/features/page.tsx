import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";

export const metadata: Metadata = {
  title: "Features — Atlas",
  description: "Dependency graph, impact analysis, investigation mode, risk detection and evidence-backed AI context export — all local-first."
};

const features = [
  { ic: "{}", t: "Dependency graph", d: "A precise, navigable map of how your modules really connect — hubs, cycles and blast radius — built locally from your source." },
  { ic: "Δ", t: "Impact analysis", d: "Change a file and see exactly what depends on it and which tests to run before you ship. Stop guessing at blast radius." },
  { ic: "?", t: "Investigation mode", d: "Trace a symptom to the likely files with grounded evidence — Atlas cites the code it reasoned from, it doesn't guess." },
  { ic: "!", t: "Risk detection", d: "Surface the architectural risk hotspots — high fan-in modules, cycles, fragile seams — that make changes dangerous." },
  { ic: "⌘", t: "AI context export", d: "One click to a compact, evidence-backed context packet for Claude, Codex or Cursor. No internal noise, no stale data." },
  { ic: "◐", t: "Local-first", d: "No upload, no cloud scan. Scanning and analysis run on your machine; only the context you copy ever leaves it." }
];

export default function FeaturesPage() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Features</p>
            <h1 className="page-title">Everything your AI is missing about your repo.</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              Atlas computes the structure an AI actually needs — locally,
              deterministically, and grounded in your real code.
            </p>
          </div>
        </section>

        <section className="section" style={{ borderTop: "none", paddingTop: 24 }}>
          <div className="container">
            <div className="grid-3">
              {features.map((f) => (
                <div className="card" key={f.t}>
                  <div className="ic mono" aria-hidden>{f.ic}</div>
                  <h3>{f.t}</h3>
                  <p>{f.d}</p>
                </div>
              ))}
            </div>
            <div className="cta" style={{ marginTop: 56 }}>
              <h2>See it on your own codebase.</h2>
              <p className="center" style={{ marginTop: 14, marginBottom: 28 }}>Free to start · local-first.</p>
              <Link className="btn btn-primary btn-lg" href="/download">Download Atlas</Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
