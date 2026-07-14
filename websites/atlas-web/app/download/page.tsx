import type { Metadata } from "next";
import Link from "next/link";
import { InstallationBlock, PageShell, PremiumSection, ReleaseVersionBlock, TechnicalDiagram } from "../_components/site";

export const metadata: Metadata = {
  title: "Atlas for Windows - Build verification",
  description: "Atlas for Windows downloads are temporarily paused during final installed-app verification.",
};

export default function DownloadPage() {
  return (
    <PageShell
      eyebrow="Download"
      title="Atlas for Windows."
      intro="The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready."
    >
      <PremiumSection>
        <div className="grid-2">
          <InstallationBlock />
          <ReleaseVersionBlock />
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
          Windows downloads will reopen after the current build completes final installed-app verification. macOS and Linux are not available yet.
        </p>
        <div className="page-actions">
          <Link className="btn-mag" href="/docs">Read docs <span className="arw" aria-hidden>→</span></Link>
          <Link className="btn-line" href="/security">Security model</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
