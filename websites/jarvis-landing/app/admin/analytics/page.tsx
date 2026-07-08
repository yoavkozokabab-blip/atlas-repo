import { PageShell } from "../_components/site";
import { AnalyticsDashboard } from "../_components/analytics-dashboard";
import { requireAdmin } from "../_lib/auth";

export const dynamic = "force-dynamic";

export default async function AnalyticsAdminPage() {
  const admin = await requireAdmin();
  if (!admin) {
    return (
      <PageShell eyebrow="Admin" title="Access denied">
        <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
          <div className="container">
            <div className="note-accent" style={{ maxWidth: 600 }}>
              Admin access required. Set <code>ADMIN_EMAILS</code> or assign the admin role.
            </div>
          </div>
        </section>
      </PageShell>
    );
  }
  return (
    <PageShell
      eyebrow="Admin · Analytics"
      title="Launch analytics dashboard"
      intro="Funnel, TTFV, retention, and agent usage — admin only."
    >
      <section className="section" style={{ borderTop: "none", paddingTop: 8 }}>
        <div className="container">
          <AnalyticsDashboard />
        </div>
      </section>
    </PageShell>
  );
}
