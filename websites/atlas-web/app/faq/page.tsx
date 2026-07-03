import type { Metadata } from "next";
import { PageShell } from "../_components/site";

export const metadata: Metadata = {
  title: "FAQ — Atlas",
  description: "Frequently asked questions about Atlas: privacy, how it works with Claude/Codex/Cursor, platforms, pricing and trials."
};

const faqs = [
  ["What is Atlas?", "Local-first repository intelligence: it maps your codebase and exports AI-ready context for Claude, Codex and Cursor."],
  ["Does my code leave my machine?", "No. Scanning and analysis run locally; only the compact context you choose to copy goes wherever you paste it."],
  ["Does Atlas replace Claude, Cursor or Codex?", "No — it makes them better by giving them your repository's real structure instead of letting them guess."],
  ["Will it invent files or give stale context?", "No. Atlas is evidence-backed and refuses stale or unverifiable context rather than hallucinating."],
  ["What platforms are supported?", "Windows today. macOS and Linux are on the roadmap — let us know on the contact page."],
  ["Is it free?", "Yes — a free tier for one repository. Pro ($29/mo) adds unlimited repos, impact analysis, investigation, compression and risk detection; the 7-day trial starts in-app, no card."],
  ["How do I cancel?", "Anytime from the billing portal; access continues to the end of the period."],
  ["Is the installer safe?", "Download Atlas from atlas-repo-chi.vercel.app. Windows SmartScreen may warn on first run for new or unsigned apps; confirm the source before continuing."]
] as const;

export default function FaqPage() {
  return (
    <PageShell eyebrow="FAQ" title="Questions, answered." intro="Everything you need to know before you download.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container faq" style={{ maxWidth: 800 }}>
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
