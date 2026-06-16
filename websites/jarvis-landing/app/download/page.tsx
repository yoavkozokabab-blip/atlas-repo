import type { Metadata } from "next";
import Link from "next/link";
import { SiteNav, SiteFooter } from "../_components/site";
import { WaitlistForm } from "../_components/waitlist";
import { currentUser } from "../_lib/auth";
import { ENV } from "../_lib/config";

export const metadata: Metadata = {
  title: "Download Atlas — Windows",
  description: "Download Atlas for Windows. Local-first repository intelligence — free to start, your code never leaves your machine."
};

export const dynamic = "force-dynamic";

export default async function DownloadPage() {
  const user = await currentUser();
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">Download</p>
            <h1 className="page-title">Download Atlas</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              Local-first repository memory for Windows. Free to start — create a free
              account to download.
            </p>
          </div>
        </section>

        <section className="section" style={{ borderTop: "none", paddingTop: 24 }}>
          <div className="container grid-2">
            <div className="dl-card">
              <h3>Atlas for Windows</h3>
              <p className="dl-meta">Atlas_Setup.exe · v{ENV.appVersion} · Windows 10 / 11 · ~42 MB</p>

              {user ? (
                <>
                  <a className="btn btn-primary btn-lg" href="/download/atlas" download style={{ marginTop: 16 }}>
                    Download for Windows
                  </a>
                  <p className="dl-meta" style={{ marginTop: 12 }}>
                    Signed in as {user.email} · your code never leaves your machine
                  </p>
                </>
              ) : (
                <>
                  <Link className="btn btn-primary btn-lg" href="/login?next=/download" style={{ marginTop: 16 }}>
                    Create a free account to download
                  </Link>
                  <p className="dl-meta" style={{ marginTop: 12 }}>
                    Free · takes 30 seconds · <Link href="/login?next=/download" style={{ color: "var(--accent)" }}>already have an account?</Link>
                  </p>
                </>
              )}

              <div className="dl-warn">
                <b>Heads up — this is an unsigned beta build.</b> Windows SmartScreen may
                show a warning on first run. Click <b>More info → Run anyway</b>. A
                code-signed release (no warning) is coming for the public launch.
              </div>

              <div style={{ marginTop: 22, paddingTop: 20, borderTop: "1px solid var(--line)" }}>
                <h3 style={{ fontSize: "1rem" }}>Want beta updates?</h3>
                <p className="note" style={{ marginTop: 8, marginBottom: 12 }}>
                  Join the Atlas beta list for updates, fixes, MCP improvements, and
                  platform releases.
                </p>
                <WaitlistForm source="download-beta-updates" compact />
              </div>
            </div>

            <div>
              <h3>Get value in under 5 minutes</h3>
              <ol className="steps" style={{ marginTop: 16 }}>
                <li>Run the installer and launch Atlas.</li>
                <li>Load the bundled sample repository, or point Atlas at your own.</li>
                <li>Describe a change and generate your first Change Plan.</li>
                <li>Click <b>Copy for Claude / Cursor / Codex</b> and paste it into your AI tool.</li>
              </ol>
              <div style={{ marginTop: 24 }}>
                <h3 style={{ fontSize: "1rem" }}>On macOS or Linux?</h3>
                <p className="note" style={{ marginTop: 8, marginBottom: 12 }}>
                  Binaries are on the roadmap — join the waitlist and we&apos;ll email you
                  when your platform is ready.
                </p>
                <WaitlistForm source="download-macos-linux" compact />
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
