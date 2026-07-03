import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";
import { SUPPORT_EMAIL, supportMailto } from "../_config";

export const metadata: Metadata = {
  title: "Docs — Atlas",
  description: "Getting started with Atlas: install, scan a repository, generate a Change Plan, and export AI-ready context."
};

export default function DocsPage() {
  return (
    <PageShell
      eyebrow="Docs"
      title="Getting started"
      intro="Atlas runs locally and gives your AI tools real context about your codebase. Here's the five-minute path."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose">
          <h2>1. Install</h2>
          <p>Download <Link href="/download">Atlas for Windows</Link> and run the installer. It&apos;s
            self-contained — no Python required. On first launch Atlas starts a local server and
            opens in your browser.</p>

          <h2>2. Load a repository</h2>
          <p>Point Atlas at a project folder, or click <b>Load Sample Repository</b> to try the
            bundled demo. Atlas scans locally and builds the dependency graph, subsystem map and
            risk model — your code never leaves your machine.</p>

          <h2>3. Generate a Change Plan</h2>
          <p>Describe a change (e.g. <code>add authentication</code>). Atlas returns the files to
            inspect first, what may break, and the verification steps — grounded in your real code,
            with a confidence rating.</p>

          <h2>4. Export context for your AI</h2>
          <p>Click <b>Copy for Claude / Cursor / Codex</b>. Atlas produces a compact, evidence-backed
            context packet. Paste it into your tool so it starts with your repo&apos;s structure instead of
            re-reading files.</p>

          <h2>Workflows</h2>
          <ul>
            <li><b>Change Plan</b> — plan a change with the exact files and order.</li>
            <li><b>Impact</b> — see what depends on a file and which tests to run (Pro).</li>
            <li><b>Investigation</b> — trace a symptom to likely files with evidence (Pro).</li>
          </ul>

          <p className="note" style={{ marginTop: 24 }}>
            Need help? <a href={supportMailto("Atlas Support")} style={{ color: "var(--accent)" }}>{SUPPORT_EMAIL || "contact support"}</a>
          </p>
        </div>
      </section>
    </PageShell>
  );
}
