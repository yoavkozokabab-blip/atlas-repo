import Link from "next/link";
import { currentUser } from "../_lib/auth";
import { LogoutButton } from "../_components/client";

export const dynamic = "force-dynamic";

function statusBadge(plan: string, planStatus: string) {
  if (plan === "free") return <span className="badge muted">Free</span>;
  if (planStatus === "trialing") return <span className="badge warn">Pro · trial</span>;
  if (planStatus === "active") return <span className="badge ok">Pro · active</span>;
  if (planStatus === "canceled") return <span className="badge warn">Canceled</span>;
  return <span className="badge muted">{plan}</span>;
}

export default async function AccountOverview() {
  const user = await currentUser();
  if (!user) return null;
  return (
    <div>
      <div className="card" style={{ marginBottom: 22 }}>
        <h3 style={{ marginBottom: 14 }}>Plan {statusBadge(user.plan, user.planStatus)}</h3>
        <dl className="kv">
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Plan</dt><dd>{user.plan}</dd>
          <dt>Status</dt><dd>{user.planStatus}</dd>
          {user.trialEndsAt ? (<><dt>Trial ends</dt><dd>{new Date(user.trialEndsAt).toLocaleDateString()}</dd></>) : null}
          <dt>Member since</dt><dd>{new Date(user.createdAt).toLocaleDateString()}</dd>
        </dl>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Link className="btn btn-primary" href="/account/downloads">Download Atlas</Link>
        {user.plan === "free"
          ? <Link className="btn btn-ghost" href="/pricing">Upgrade to Pro</Link>
          : <Link className="btn btn-ghost" href="/account/billing">Manage billing</Link>}
        <LogoutButton />
      </div>
    </div>
  );
}
