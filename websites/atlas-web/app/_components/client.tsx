"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { trackAnalyticsEvent } from "./AnalyticsClient";

async function postJson(url: string, body?: unknown) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  return { res, data } as { res: Response; data: Record<string, unknown> };
}

type Mode = "login" | "signup" | "forgot";

export function AuthForm({ next }: { next: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setInfo("");
    try {
      if (mode === "forgot") {
        const { data } = await postJson("/api/auth/forgot", { email });
        setInfo(String(data.message || "If an account exists, a reset link has been sent."));
        return;
      }
      const url = mode === "signup" ? "/api/auth/register" : "/api/auth/login";
      const startedEvent = mode === "signup" ? "signup_started" : "login_started";
      const successEvent = mode === "signup" ? "signup_success" : "login_success";
      const failedEvent = mode === "signup" ? "signup_failed" : "login_failed";
      trackAnalyticsEvent(startedEvent, { deduplicationKey: crypto.randomUUID() });
      const { res, data } = await postJson(url, { email, password, name });
      if (!res.ok) {
        trackAnalyticsEvent(failedEvent, {
          properties: { http_status: res.status, reason_code: `http_${res.status}` },
          deduplicationKey: crypto.randomUUID(),
        });
        setError(String(data.error || "Something went wrong."));
        return;
      }
      trackAnalyticsEvent(successEvent, { deduplicationKey: crypto.randomUUID() });
      router.push(next || "/account");
      router.refresh();
    } catch {
      if (mode !== "forgot") {
        trackAnalyticsEvent(mode === "signup" ? "signup_failed" : "login_failed", {
          properties: { reason_code: "network_error" },
          deduplicationKey: crypto.randomUUID(),
        });
      }
      setError("Account service is temporarily unavailable. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 460 }}>
      <div className="seg" role="tablist" aria-label="Auth mode">
        <button type="button" className={mode === "login" ? "seg-on" : ""} onClick={() => setMode("login")}>Sign in</button>
        <button type="button" className={mode === "signup" ? "seg-on" : ""} onClick={() => setMode("signup")}>Create account</button>
        <button type="button" className={mode === "forgot" ? "seg-on" : ""} onClick={() => setMode("forgot")}>Forgot</button>
      </div>

      <form className="form" onSubmit={submit} style={{ marginTop: 18 }}>
        {mode === "signup" && (
          <div className="field">
            <label htmlFor="name">Name (optional)</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </div>
        )}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@company.com" />
        </div>
        {mode !== "forgot" && (
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"} />
          </div>
        )}
        {error && <p style={{ color: "var(--risk)", fontSize: "0.9rem" }}>{error}</p>}
        {info && <p style={{ color: "var(--ok)", fontSize: "0.9rem" }}>{info}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Please wait…" : mode === "signup" ? "Create account" : mode === "forgot" ? "Send reset link" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

export function LogoutButton() {
  const router = useRouter();
  return (
    <button className="btn btn-ghost" onClick={async () => { await postJson("/api/auth/logout"); router.push("/"); router.refresh(); }}>
      Sign out
    </button>
  );
}

export function CheckoutButton({ plan, label, className }: { plan: string; label: string; className?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <button className={className || "btn btn-primary"} disabled={busy} onClick={async () => {
      setBusy(true);
      const { res, data } = await postJson("/api/checkout", { plan });
      setBusy(false);
      if (res.status === 401) { router.push(`/login?next=/checkout/plan/${plan}`); return; }
      if (data.url) { router.push(String(data.url)); router.refresh(); }
    }}>
      {busy ? "Starting…" : label}
    </button>
  );
}

export function ManageBillingButton() {
  const router = useRouter();
  return (
    <button className="btn btn-ghost" onClick={async () => {
      const { data } = await postJson("/api/billing/portal");
      if (data.url) router.push(String(data.url));
    }}>Manage billing</button>
  );
}

export function BillingActionButton({ action, label, className }: { action: "cancel" | "renew"; label: string; className?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <button className={className || "btn btn-ghost"} disabled={busy} onClick={async () => {
      setBusy(true); await postJson("/api/billing/cancel", { action }); setBusy(false); router.refresh();
    }}>{busy ? "Working…" : label}</button>
  );
}

export function DeleteAccountForm() {
  const router = useRouter();
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <form className="form" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setError("");
      const { res, data } = await postJson("/api/account/delete", { confirm });
      setBusy(false);
      if (!res.ok) { setError(String(data.error || "Could not delete account.")); return; }
      router.push("/"); router.refresh();
    }}>
      <div className="field">
        <label htmlFor="confirm">Type DELETE to confirm</label>
        <input id="confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="DELETE" />
      </div>
      {error && <p style={{ color: "var(--risk)", fontSize: "0.9rem" }}>{error}</p>}
      <button className="btn" style={{ background: "var(--risk)", color: "#fff" }} type="submit" disabled={busy || confirm !== "DELETE"}>
        {busy ? "Deleting…" : "Permanently delete my account"}
      </button>
    </form>
  );
}

type AdminUser = {
  id: string; email: string; name?: string; role: string; status: string;
  plan: string; planStatus: string; createdAt: string; lastLoginAt?: string | null; downloads: number;
};
type AdminAudit = { id: string; at: string; actorEmail: string; action: string; targetEmail?: string };

type AnalyticsSummary = {
  since: string;
  timezone: string;
  environment: string | null;
  build_commit: string | null;
  include_internal: boolean;
  unique_visitors: number;
  sessions: number;
  page_views: number;
  downloads_attempted: number;
  downloads_unavailable: number;
  successful_installs: number;
  first_launches: number;
  scans_completed: number;
  ask_completed: number;
  agents_connected: number;
  signup_success: number;
  signup_failed: number;
  active_users: number;
  returning_users: number;
  top_routes: { route: string; views: number }[];
};

function percentage(numerator: number, denominator: number) {
  if (!denominator) return "0.0%";
  return `${((numerator / denominator) * 100).toFixed(1)}%`;
}

function AnalyticsDashboard() {
  const [days, setDays] = useState(7);
  const [environment, setEnvironment] = useState("production");
  const [build, setBuild] = useState("");
  const [includeInternal, setIncludeInternal] = useState(false);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      days: String(days),
      environment,
      include_internal: String(includeInternal),
    });
    if (build) params.set("build", build);
    setLoading(true);
    setError("");
    fetch(`/api/admin/analytics?${params}`, { cache: "no-store", signal: controller.signal })
      .then(async (res) => ({ res, data: await res.json().catch(() => ({})) }))
      .then(({ res, data }) => {
        if (!res.ok) throw new Error(String(data.error || "analytics_unavailable"));
        setSummary(data.summary as AnalyticsSummary);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setSummary(null);
        setError("Analytics are unavailable for the selected environment.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [days, environment, build, includeInternal]);

  const metrics = summary
    ? [
        ["Unique visitors", summary.unique_visitors],
        ["Sessions", summary.sessions],
        ["Page views", summary.page_views],
        ["Download attempts", summary.downloads_attempted],
        ["Download unavailable", summary.downloads_unavailable],
        ["Installations", summary.successful_installs],
        ["First launches", summary.first_launches],
        ["Signup success", summary.signup_success],
        ["Signup failed", summary.signup_failed],
        ["Active users", summary.active_users],
        ["Returning users", summary.returning_users],
        ["Scan completed", summary.scans_completed],
        ["Ask completed", summary.ask_completed],
        ["Agents connected", summary.agents_connected],
      ]
    : [];

  return (
    <section aria-labelledby="analytics-heading" style={{ marginBottom: 40 }}>
      <h3 id="analytics-heading">Product analytics</h3>
      <p className="muted">
        UTC aggregates. Production is selected by default; preview and internal traffic stay separate.
      </p>
      <div className="form" style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "end", marginBottom: 18 }}>
        <div className="field">
          <label htmlFor="analytics-days">Range</label>
          <select id="analytics-days" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>1 day</option><option value={7}>7 days</option><option value={30}>30 days</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="analytics-environment">Environment</label>
          <select id="analytics-environment" value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            <option value="production">Production</option><option value="preview">Preview</option>
            <option value="development">Development</option><option value="test">Test</option>
            <option value="unknown">Unknown / legacy</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="analytics-build">Build commit (optional)</label>
          <input id="analytics-build" className="mono" value={build} onChange={(e) => setBuild(e.target.value.trim())} placeholder="7-40 hex chars" />
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "center", paddingBottom: 10 }}>
          <input type="checkbox" checked={includeInternal} onChange={(e) => setIncludeInternal(e.target.checked)} />
          Include internal traffic
        </label>
      </div>
      {loading && <p className="muted">Loading analytics...</p>}
      {error && <div className="note-accent">{error}</div>}
      {summary && !loading && (
        <>
          <div className="grid-3" style={{ marginBottom: 18 }}>
            {metrics.map(([label, value]) => (
              <div className="card" key={String(label)}><div className="muted">{label}</div><strong>{value}</strong></div>
            ))}
          </div>
          <p className="muted">
            Download CTR {percentage(summary.downloads_attempted, summary.unique_visitors)} · Signup conversion {percentage(summary.signup_success, summary.unique_visitors)} · Returning-user rate {percentage(summary.returning_users, summary.active_users)}
          </p>
          <h4>Top routes</h4>
          <table className="tbl">
            <thead><tr><th>Route</th><th>Views</th></tr></thead>
            <tbody>
              {summary.top_routes.map((row) => <tr key={row.route}><td className="mono">{row.route}</td><td>{row.views}</td></tr>)}
              {summary.top_routes.length === 0 && <tr><td colSpan={2} className="muted">No matching route views.</td></tr>}
            </tbody>
          </table>
          <div className="note-accent" style={{ marginTop: 18 }}>
            Funnel totals are partial whenever the corresponding canonical event is not emitted by a verified website or desktop flow. Missing events are shown as zero, never estimated.
          </div>
        </>
      )}
    </section>
  );
}

export function AdminConsole() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AdminAudit[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(query = "") {
    setLoading(true);
    const res = await fetch(`/api/admin/users${query ? `?q=${encodeURIComponent(query)}` : ""}`);
    const data = await res.json().catch(() => ({}));
    setUsers(data.users || []); setAudit(data.audit || []); setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function act(action: string, targetId: string) {
    await postJson("/api/admin/actions", { action, targetId });
    load(q);
  }

  return (
    <div>
      <AnalyticsDashboard />
      <div className="form" style={{ flexDirection: "row", maxWidth: 520, marginBottom: 18 }}>
        <input className="field" style={{ flex: 1 }} placeholder="Search by email or name" value={q}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") load(q); }} />
        <button className="btn btn-ghost" onClick={() => load(q)}>Search</button>
      </div>

      {loading ? <p className="muted">Loading…</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead><tr><th>Email</th><th>Status</th><th>Plan</th><th>Role</th><th>Downloads</th><th>Actions</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{u.status}</td>
                  <td>{u.plan} / {u.planStatus}</td>
                  <td>{u.role}</td>
                  <td>{u.downloads}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {u.status === "active"
                      ? <button className="lnk" onClick={() => act("suspend", u.id)}>Suspend</button>
                      : <button className="lnk" onClick={() => act("restore", u.id)}>Restore</button>}
                    {" · "}
                    <button className="lnk" onClick={() => act("grant_pro", u.id)}>Grant Pro</button>
                    {" · "}
                    <button className="lnk" onClick={() => act("revoke_license", u.id)}>Revoke</button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && <tr><td colSpan={6} className="muted">No users yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      <h3 style={{ marginTop: 36 }}>Audit log</h3>
      <div style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th></tr></thead>
          <tbody>
            {audit.map((a) => (
              <tr key={a.id}><td className="mono" style={{ fontSize: "0.8rem" }}>{a.at}</td><td>{a.actorEmail}</td><td>{a.action}</td><td>{a.targetEmail || "—"}</td></tr>
            ))}
            {audit.length === 0 && <tr><td colSpan={4} className="muted">No actions logged yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
