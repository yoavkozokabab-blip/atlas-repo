import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "../_components/site";

export const metadata: Metadata = {
  title: "Benchmarks - Atlas",
  description: "Transparent, reproducible Atlas measurements: sample-repo indexing time, Ask Atlas latency, and retrieval quality on a 50-scenario suite.",
};

export default function BenchmarksPage() {
  return (
    <PageShell
      eyebrow="Benchmarks"
      title="Measured, not marketed."
      intro="Every number below was produced by a harness that ships in the repository, on a single developer machine. Read the limitations before quoting anything."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container prose" style={{ maxWidth: 820 }}>
          <h2>Sample repository (the built-in demo)</h2>
          <ul>
            <li><b>Size:</b> 18 files / 17 production modules.</li>
            <li><b>Indexing time:</b> ~4 seconds, measured end-to-end (load + scan + graph build).</li>
            <li><b>Ask Atlas latency:</b> 1–30 ms per question after indexing. Answers are deterministic lookups against the local index — there is no model call in the loop.</li>
          </ul>

          <h2>Retrieval quality (50-scenario suite)</h2>
          <p>
            The repository ships a benchmark suite of 50 ground-truth scenarios (feature
            additions, bug investigations, impact analyses) against a reference repository
            with known structure. Latest full run:
          </p>
          <ul>
            <li><b>File recall:</b> 0.95 (feature addition), 0.98 (bug investigation), 0.97 (impact analysis) — the files you actually need are almost always in the answer.</li>
            <li><b>File precision:</b> 0.80 (feature), 0.30 (bug investigation), 0.88 (impact) — bug investigations deliberately cast a wider net of hypotheses.</li>
            <li><b>All 50 scenarios execute without errors.</b></li>
          </ul>
          <p className="note">
            Reproduce it: <code>py -3 benchmarks/generate_suite.py</code> then <code>py -3 benchmarks/runner.py</code> in the Atlas repository.
          </p>

          <h2>Memory use</h2>
          <p>
            We have not published a rigorous memory benchmark yet. Anecdotally the desktop
            app is a single local Python process; a proper measurement across repo sizes
            will be published here when it exists. We will not fabricate a number in the meantime.
          </p>

          <h2>Limitations — read this part</h2>
          <ul>
            <li>All numbers are self-measured on one Windows development machine; your hardware will differ.</li>
            <li>The 50-scenario suite runs against a reference repository we built, not a random sample of open-source projects.</li>
            <li>The sample demo repo is small by design. Indexing large monorepos is slower and is an active work item (see the <Link href="/roadmap">roadmap</Link>).</li>
            <li>Retrieval quality is not the same as end-to-end task success with a coding agent — that study has not been run yet.</li>
          </ul>
        </div>
      </section>
    </PageShell>
  );
}
