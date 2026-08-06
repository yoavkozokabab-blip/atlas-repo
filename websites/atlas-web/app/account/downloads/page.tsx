import { currentUser } from "../../_lib/auth";
import { CURRENT_WINDOWS_RELEASE, releaseSizeLabel } from "../../_config";

export const dynamic = "force-dynamic";

export default async function DownloadsPage() {
  const user = await currentUser();
  if (!user) return null;
  return (
    <div>
      <div className="dl-card" style={{ marginBottom: 22 }}>
        <h3>Atlas for Windows</h3>
        <p className="dl-meta">
          {CURRENT_WINDOWS_RELEASE.filename} · v{CURRENT_WINDOWS_RELEASE.version} · Windows 10 / 11 ·{" "}
          {releaseSizeLabel()}
        </p>
        <a className="btn btn-primary btn-lg" href="/download/atlas" download style={{ marginTop: 14 }}>
          Download for Windows
        </a>
        <p className="dl-meta" style={{ marginTop: 10 }}>You have downloaded Atlas {user.downloads} time(s).</p>
        <div className="dl-warn">
          <b>Windows SmartScreen may show a warning on first run.</b> Confirm you
          downloaded Atlas from the official Atlas website or GitHub release, then click <b> More info → Run anyway</b>.
        </div>
      </div>
      <h3>Release notes</h3>
      <ul className="prose" style={{ paddingLeft: 20 }}>
        <li>v{CURRENT_WINDOWS_RELEASE.version} — local-first repository memory, Plan Change, Impact, Debug, and Claude/Cursor/Codex connection.</li>
      </ul>
    </div>
  );
}
