import type { Metadata } from "next";
import Link from "next/link";
import { InstallationBlock, PageShell, PremiumSection, ReleaseVersionBlock } from "../_components/site";

export const metadata: Metadata = {
  title: "Releases - Atlas",
  description: "Atlas release information and current Windows build verification status.",
};

export default function ReleasesPage() {
  return (
    <PageShell
      eyebrow="Releases"
      title="Atlas release status."
      intro="Windows downloads are temporarily paused while the latest desktop build completes final installed-app verification."
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
        intro="Use the changelog for what changed. Verified installer details will return here when downloads reopen."
      >
        <div className="page-actions">
          <Link className="btn-line" href="/changelog">Read changelog</Link>
        </div>
      </PremiumSection>
    </PageShell>
  );
}
