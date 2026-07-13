import type { Metadata } from "next";
import Link from "next/link";
import { InstallationBlock, PageShell, PremiumSection, ReleaseVersionBlock, TechnicalDiagram } from "../_components/site";
import { ENV } from "../_lib/config";
import { GITHUB_RELEASE_URL, INSTALLER_SHA256 } from "../_config";

export const metadata: Metadata = {
  title: "Download Atlas - Windows",
  description: "Download Atlas for Windows. No signup required. Local-first repository memory for Claude Code, Cursor, and Codex.",
};

export default function DownloadPage() {
  return (
    <PageShell
      eyebrow="Download"
      title="Install Atlas on Windows."
      intro="A local-first desktop app for repository memory. No signup is required to download or start."
    >
      <PremiumSection>
        <div className="grid-2">
          <InstallationBlock />
          <ReleaseVersionBlock />
        </div>
      </PremiumSection>

      <PremiumSection
        eyebrow="Verify"
        title="Confirm the release before running it."
        intro="Atlas is currently distributed as an unsigned Windows installer, so SmartScreen may warn on first run."
      >
        <div className="dl-card">
          <h3>Atlas for Windows</h3>
          <p className="dl-meta">Atlas_Setup.exe · v{ENV.appVersion} · 30 MB · Windows 10 / 11</p>
          <p className="dl-meta" style={{ marginTop: 12, wordBreak: "break-all" }}>
            SHA256: <code>{INSTALLER_SHA256}</code>
          </p>
          <div className="dl-warn">
            <b>Windows SmartScreen may show a warning on first run.</b> Confirm you downloaded Atlas from the official release link before continuing.
          </div>
          <p style={{ marginTop: 18 }}>
            <a className="btn-line" href={GITHUB_RELEASE_URL} target="_blank" rel="noreferrer">
              Verify against the GitHub release
            </a>
          </p>
        </div>
      </PremiumSection>

      <PremiumSection
        eyebrow="First run"
        title="Start in under five minutes."
      >
        <TechnicalDiagram
          title="install flow"
          items={[
            ["Run installer", "Install per-user on Windows 10 or 11."],
            ["Open a repository", "Scan the bundled sample repo or choose your own local project."],
            ["Connect an agent", "Use the app to configure Claude Code, Cursor or Codex."],
            ["Ask with citations", "Use the cited files in your agent instead of re-explaining the repo."],
          ]}
        />
        <p className="note" style={{ marginTop: 20 }}>
          Windows is available now. macOS and Linux are not available yet.
        </p>
        <div className="page-actions">
          <Link className="btn-mag" href="/docs">Read docs <span className="arw" aria-hidden>→</span></Link>
          <Link className="btn-line" href="/security">Security model</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
