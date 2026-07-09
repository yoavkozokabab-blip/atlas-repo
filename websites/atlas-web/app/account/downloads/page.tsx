import { existsSync, statSync } from "node:fs";
import path from "node:path";
import { currentUser } from "../../_lib/auth";
import { ENV } from "../../_lib/config";

export const dynamic = "force-dynamic";

function installerSizeMB(): string {
  const candidates = [
    process.env.ATLAS_INSTALLER_PATH || "",
    path.join(process.cwd(), "..", "..", "packaging", "installer", "output", "Atlas_Setup.exe"),
  ].filter(Boolean);
  for (const p of candidates) {
    try {
      if (existsSync(p)) return (statSync(p).size / (1024 * 1024)).toFixed(0) + " MB";
    } catch {}
  }
  return "~42 MB";
}

export default async function DownloadsPage() {
  const user = await currentUser();
  if (!user) return null;
  return (
    <div>
      <div className="dl-card" style={{ marginBottom: 22 }}>
        <h3>Atlas for Windows</h3>
        <p className="dl-meta">Atlas_Setup.exe · v{ENV.appVersion} · Windows 10 / 11 · {installerSizeMB()}</p>
        <a className="btn btn-primary btn-lg" href="/download/atlas" download style={{ marginTop: 14 }}>
          Download for Windows
        </a>
        <p className="dl-meta" style={{ marginTop: 10 }}>You have downloaded Atlas {user.downloads} time(s).</p>
        <div className="dl-warn">
          <b>Windows SmartScreen may show a warning on first run.</b> Confirm you
          downloaded Atlas from atlas-repo-chi.vercel.app, then click <b> More info → Run anyway</b>.
        </div>
      </div>
      <h3>Release notes</h3>
      <ul className="prose" style={{ paddingLeft: 20 }}>
        <li>v{ENV.appVersion} — local-first repository memory, Plan Change, Impact, Debug, and Claude/Cursor/Codex connection.</li>
      </ul>
    </div>
  );
}
