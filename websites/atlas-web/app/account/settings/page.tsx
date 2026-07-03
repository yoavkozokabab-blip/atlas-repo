import Link from "next/link";
import { currentUser } from "../../_lib/auth";
import { LogoutButton } from "../../_components/client";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const user = await currentUser();
  if (!user) return null;
  return (
    <div>
      <div className="card" style={{ marginBottom: 22 }}>
        <h3 style={{ marginBottom: 14 }}>Account</h3>
        <dl className="kv">
          <dt>Name</dt><dd>{user.name || "—"}</dd>
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Role</dt><dd>{user.role}</dd>
          <dt>Last sign-in</dt><dd>{user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString() : "—"}</dd>
        </dl>
      </div>

      <div className="card" style={{ marginBottom: 22 }}>
        <h3 style={{ marginBottom: 10 }}>Privacy &amp; data</h3>
        <p className="note">Atlas is local-first — your code never leaves your machine. Account and
          license data is the minimum needed to run your plan. See the{" "}
          <Link href="/privacy" style={{ color: "var(--accent)" }}>Privacy</Link> and{" "}
          <Link href="/security" style={{ color: "var(--accent)" }}>Security</Link> pages.</p>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <LogoutButton />
        <Link className="btn btn-ghost" href="/account/delete" style={{ color: "var(--risk)", borderColor: "var(--risk)" }}>
          Delete account
        </Link>
      </div>
    </div>
  );
}
