"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type FunnelStep = {
  key: string;
  label: string;
  count: number;
  conversionFromPrev: number | null;
};

type DashboardData = {
  ok: boolean;
  generated_at: string;
  funnel: FunnelStep[];
  ttfv: Record<string, number | null>;
  retention: { d1: number; d7: number; d30: number };
  agents: {
    most_used: string;
    connected: Record<string, number>;
    used: Record<string, number>;
  };
  drop_off: { from: string; to: string; dropPct: number } | null;
  identity_rollups: Record<string, number>;
};

function fmtSec(sec: number | null | undefined): string {
  if (sec == null) return "—";
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
}

export function AnalyticsDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/admin/analytics/dashboard")
      .then((r) => r.json())
      .then((d) => {
        if (!d.ok) setError(String(d.error || "Failed to load"));
        else setData(d);
      })
      .catch(() => setError("Failed to load dashboard"));
  }, []);

  if (error) return <div className="note-accent">{error}</div>;
  if (!data) return <p>Loading analytics…</p>;

  const notice = (data as DashboardData & { notice?: string }).notice;

  return (
    <div style={{ maxWidth: 960 }}>
      <p style={{ opacity: 0.7, marginBottom: 16 }}>
        Generated {new Date(data.generated_at).toLocaleString()} ·{" "}
        <Link href="/admin">← Admin home</Link>
      </p>
      {notice ? <div className="note-accent" style={{ marginBottom: 16 }}>{notice}</div> : null}

      <h3 style={{ marginBottom: 12 }}>Launch funnel</h3>
      <table className="table" style={{ width: "100%", marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Step</th>
            <th>Count</th>
            <th>Conversion from prev</th>
          </tr>
        </thead>
        <tbody>
          {data.funnel.map((step) => (
            <tr key={step.key}>
              <td>{step.label}</td>
              <td>{step.count}</td>
              <td>{step.conversionFromPrev == null ? "—" : `${step.conversionFromPrev}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ marginBottom: 12 }}>Time to first value (avg)</h3>
      <ul style={{ marginBottom: 24 }}>
        <li>Install → Open: {fmtSec(data.ttfv.install_to_open_sec)}</li>
        <li>Open → Login: {fmtSec(data.ttfv.open_to_login_sec)}</li>
        <li>Login → Repo: {fmtSec(data.ttfv.login_to_repo_sec)}</li>
        <li>Repo → First context: {fmtSec(data.ttfv.repo_to_first_context_sec)}</li>
        <li>Total TTFV: {fmtSec(data.ttfv.total_ttfv_sec)}</li>
      </ul>

      <h3 style={{ marginBottom: 12 }}>Retention</h3>
      <p style={{ marginBottom: 24 }}>
        Day 1: {data.retention.d1}% · Day 7: {data.retention.d7}% · Day 30: {data.retention.d30}%
      </p>

      <h3 style={{ marginBottom: 12 }}>Agents</h3>
      <p style={{ marginBottom: 8 }}>Most used: <strong>{data.agents.most_used}</strong></p>
      <p style={{ marginBottom: 24, opacity: 0.85 }}>
        Connected — Cursor: {data.agents.connected.cursor}, Claude: {data.agents.connected.claude}, Codex:{" "}
        {data.agents.connected.codex}
        <br />
        Used — Cursor: {data.agents.used.cursor}, Claude: {data.agents.used.claude}, Codex:{" "}
        {data.agents.used.codex}
      </p>

      {data.drop_off && (
        <p className="note-accent" style={{ marginBottom: 24 }}>
          Biggest drop-off: {data.drop_off.from} → {data.drop_off.to} ({data.drop_off.dropPct}% lost)
        </p>
      )}

      <h3 style={{ marginBottom: 12 }}>Identity rollups</h3>
      <ul>
        <li>Identities tracked: {data.identity_rollups.total_identities}</li>
        <li>With full TTFV: {data.identity_rollups.with_ttfv}</li>
        <li>Avg tool calls / identity: {data.identity_rollups.avg_tool_calls}</li>
        <li>Avg sessions / identity: {data.identity_rollups.avg_sessions}</li>
      </ul>
    </div>
  );
}
