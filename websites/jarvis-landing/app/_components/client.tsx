"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { trackClientEvent } from "../_lib/analytics-client";

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
      if (mode === "signup") {
        await trackClientEvent("signup_started", { page: next || "/account" });
      }
      const url = mode === "signup" ? "/api/auth/register" : "/api/auth/login";
      const { res, data } = await postJson(url, { email, password, name });
      if (!res.ok) {
        if (mode === "signup") {
          await trackClientEvent("signup_failed", { reason: String(data.error || "unknown") });
        }
        setError(String(data.error || "Something went wrong."));
        return;
      }
      if (mode === "signup") {
        await trackClientEvent("signup_success", { page: next || "/account" });
      }
      router.push(next || "/account");
      router.refresh();
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
      <p style={{ marginBottom: 16 }}>
        <a href="/admin/analytics" className="lnk">Launch analytics dashboard →</a>
      </p>
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
