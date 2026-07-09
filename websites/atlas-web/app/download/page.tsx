import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";
import { ENV } from "../_lib/config";

export const metadata: Metadata = {
  title: "Download Atlas - Windows",
  description: "Download Atlas for Windows. No signup required. Local-first repository memory for Claude Code, Cursor, and Codex.",
};

export default function DownloadPage() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Download</p>
            <h1 className="page-title">Download Atlas</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              Windows installer for local-first repository memory. No signup required.
            </p>
          </div>
        </section>

        <section className="section" style={{ borderTop: "none", paddingTop: 24 }}>
          <div className="container grid-2">
            <div className="dl-card">
              <h3>Atlas for Windows</h3>
              <p className="dl-meta">Atlas_Setup.exe · v{ENV.appVersion} · Windows 10 / 11</p>
              <a className="btn btn-primary btn-lg" href="/download/atlas" style={{ marginTop: 16 }}>
                Download Atlas
              </a>
              <p className="dl-meta" style={{ marginTop: 12 }}>
                No signup required · Local-first · Your code stays on your machine
              </p>
              <div className="dl-warn">
                <b>Windows SmartScreen may show a warning on first run.</b> Confirm
                you downloaded Atlas from the official release link before continuing.
              </div>
            </div>

            <div>
              <h3>Start in under 5 minutes</h3>
              <ol className="steps" style={{ marginTop: 16 }}>
                <li>Run the installer and launch Atlas.</li>
                <li>Open a repository on your machine.</li>
                <li>Connect Claude Code, Cursor, or Codex from the Atlas app.</li>
                <li>Ask Atlas a repo-aware question and use the cited files in your agent.</li>
              </ol>
              <p className="dl-meta" style={{ marginTop: 20 }}>
                Windows is available now. macOS and Linux are not available yet.
              </p>
              <p style={{ marginTop: 18 }}>
                <Link className="btn btn-ghost" href="/docs">Read docs</Link>
              </p>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
