import type { Metadata } from "next";
import Link from "next/link";
import { InstallationBlock, PageShell, PremiumSection, ReleaseVersionBlock } from "../_components/site";
import { GITHUB_RELEASE_URL } from "../_config";

export const metadata: Metadata = {
  title: "Releases - Atlas",
  description: "Atlas release information, current version, Windows installer verification, and GitHub release link.",
};

export default function ReleasesPage() {
  return (
    <PageShell
      eyebrow="Releases"
      title="Current Atlas release."
      intro="The public website points users to the same installer path and GitHub release verification used on the Download page."
    >
      <PremiumSection>
        <div className="grid-2">
          <ReleaseVersionBlock />
          <InstallationBlock />
        </div>
      </PremiumSection>

      <PremiumSection
        eyebrow="History"
        title="Release notes live in the changelog."
        intro="Use this page for the current release artifact and verification path; use the changelog for what changed."
      >
        <div className="page-actions">
          <a className="btn-mag" href={GITHUB_RELEASE_URL} target="_blank" rel="noreferrer">
            Open GitHub release <span className="arw" aria-hidden>→</span>
          </a>
          <Link className="btn-line" href="/changelog">Read changelog</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
