import { PageShell } from "../_components/site";
import { requireAdmin } from "../_lib/auth";
import { AdminConsole } from "../_components/client";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const admin = await requireAdmin();
  if (!admin) {
    return (
      <PageShell eyebrow="Admin" title="Access denied">
        <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
          <div className="container">
            <div className="note-accent" style={{ maxWidth: 600 }}>
              You need an admin account to view this page. Admin access is role-based —
              set <code>ADMIN_EMAILS</code> in the environment (or assign the admin role).
              No admin password is hardcoded anywhere.
            </div>
          </div>
        </section>
      </PageShell>
    );
  }
  return (
    <PageShell eyebrow="Admin" title="Admin dashboard" intro="Users, plans, downloads and the audit log. Every action is recorded.">
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container">
          <AdminConsole />
        </div>
      </section>
    </PageShell>
  );
}
