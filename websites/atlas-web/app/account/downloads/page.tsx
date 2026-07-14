import { currentUser } from "../../_lib/auth";
import InstallerWaitState from "../../_components/InstallerWaitState";

export const dynamic = "force-dynamic";

export default async function DownloadsPage() {
  const user = await currentUser();
  if (!user) return null;
  return (
    <div>
      <div className="dl-card" style={{ marginBottom: 22 }}>
        <h3>Atlas for Windows</h3>
        <InstallerWaitState />
        <p className="dl-meta" style={{ marginTop: 10 }}>You have downloaded Atlas {user.downloads} time(s).</p>
      </div>
      <h3>Release notes</h3>
      <ul className="prose" style={{ paddingLeft: 20 }}>
        <li>Local-first repository memory, Plan Change, Impact, Debug, and Claude/Cursor/Codex connection.</li>
      </ul>
    </div>
  );
}
