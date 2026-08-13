import { requireAdmin } from "@/app/_lib/auth";
import { funnelRows } from "@/app/_lib/store";
import { buildHnFunnel, launchHealth, type HnFunnel } from "@/app/_lib/hn-funnel";
import { CURRENT_WINDOWS_RELEASE } from "@/app/_config";

export const dynamic = "force-dynamic";
export const metadata = { title: "HN Launch - Atlas admin" };

const WINDOWS: [string, number, string][] = [
  ["15m", 15, "15 min"],
  ["1h", 60, "1 hour"],
  ["6h", 360, "6 hours"],
  ["24h", 1_440, "Launch day"],
  ["7d", 10_080, "7 days"],
  ["30d", 43_200, "All time"],
];

function pct(value: number | null): string {
  return value === null ? "-" : `${(value * 100).toFixed(1)}%`;
}

function ms(value: number | null): string {
  if (value === null) return "-";
  if (value < 1_000) return `${value} ms`;
  if (value < 60_000) return `${(value / 1_000).toFixed(1)} s`;
  return `${(value / 60_000).toFixed(1)} min`;
}

function Tile({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="dl-card" style={{ padding: "14px 16px" }}>
      <p className="mono" style={{ margin: 0, fontSize: 12, opacity: 0.7 }}>{label}</p>
      <strong style={{ fontSize: 26, display: "block", margin: "4px 0" }}>{value}</strong>
      {note ? <p className="note" style={{ margin: 0, fontSize: 12 }}>{note}</p> : null}
    </div>
  );
}

function Funnel({ funnel }: { funnel: HnFunnel }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{ textAlign: "left", opacity: 0.7 }}>
          <th style={{ padding: "6px 8px" }}>Stage</th>
          <th style={{ padding: "6px 8px" }}>Count</th>
          <th style={{ padding: "6px 8px" }}>From previous</th>
          <th style={{ padding: "6px 8px" }}>From HN sessions</th>
        </tr>
      </thead>
      <tbody>
        {funnel.stages.map((stage) => (
          <tr key={stage.key} style={{ borderTop: "1px solid rgba(128,128,128,.25)" }}>
            <td style={{ padding: "6px 8px" }}>
              {stage.label}
              <span className="mono" style={{ opacity: 0.5, fontSize: 11, marginLeft: 8 }}>{stage.unit}</span>
              {stage.aggregateProxy ? (
                <span className="badge" style={{ marginLeft: 8, fontSize: 11 }} title="Website and desktop identities are not correlated; this is a ratio of two independent counters, not a per-user conversion.">
                  aggregate proxy
                </span>
              ) : null}
            </td>
            <td style={{ padding: "6px 8px" }}><strong>{stage.count}</strong></td>
            <td style={{ padding: "6px 8px" }}>{pct(stage.fromPrevious)}</td>
            <td style={{ padding: "6px 8px" }}>{pct(stage.fromTop)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default async function HnLaunchPage({
  searchParams,
}: {
  searchParams: Promise<{ window?: string }>;
}) {
  const admin = await requireAdmin();
  if (!admin) {
    return (
      <main className="section"><div className="container prose">
        <h1>Admin</h1>
        <p>Access denied. This page is role-based; set ADMIN_EMAILS in the environment.</p>
      </div></main>
    );
  }

  const params = await searchParams;
  const key = params.window || "24h";
  const chosen = WINDOWS.find(([k]) => k === key) || WINDOWS[3];
  const since = new Date(Date.now() - chosen[1] * 60_000).toISOString();

  let funnel: HnFunnel | null = null;
  let error: string | null = null;
  try {
    const { rows, truncated } = await funnelRows(since);
    funnel = buildHnFunnel(rows, { since, windowLabel: chosen[2], truncated });
  } catch (e) {
    error = (e as Error)?.message === "analytics backend unavailable"
      ? "Analytics backend unavailable (Supabase not configured for this deployment)."
      : "Could not read analytics.";
  }

  const health = funnel ? launchHealth(funnel, true, funnel.feedback.submitted > 0 || funnel.feedback.opened === 0) : null;
  const colour = health?.level === "red" ? "#e5484d" : health?.level === "amber" ? "#f5a524" : "#30a46c";

  return (
    <main className="section"><div className="container prose" style={{ maxWidth: 1040 }}>
      <h1>HN Launch</h1>
      <p className="note">
        Release {CURRENT_WINDOWS_RELEASE.version} · window: {chosen[2]}
        {funnel ? ` · ${funnel.rowsScanned.toLocaleString()} events scanned` : ""}
        {funnel?.truncated ? " · ROW CAP REACHED, counts are a lower bound" : ""}
      </p>

      <p style={{ margin: "10px 0 18px" }}>
        {WINDOWS.map(([k, , label]) => (
          <a key={k} href={`/admin/hn?window=${k}`} className="btn-line"
             style={{ marginRight: 8, fontWeight: k === key ? 700 : 400 }}>{label}</a>
        ))}
      </p>

      {error ? <div className="dl-warn"><b>{error}</b></div> : null}

      {funnel && health ? (
        <>
          <div className="dl-card" style={{ borderLeft: `4px solid ${colour}`, marginBottom: 20 }}>
            <strong style={{ textTransform: "uppercase" }}>{health.level}</strong>
            <p className="note" style={{ margin: "4px 0 0" }}>{health.reasons.join(" · ")}</p>
          </div>

          <div className="grid-2" style={{ gap: 12, gridTemplateColumns: "repeat(3, minmax(0,1fr))" }}>
            <Tile label="HN sessions" value={funnel.acquisition.hnSessions}
                  note={`${pct(funnel.acquisition.hnShare)} of ${funnel.acquisition.totalSessions} sessions`} />
            <Tile label="Artifact redirects" value={funnel.acquisition.artifactRedirects}
                  note="requests for the installer, not completed downloads" />
            <Tile label="First launches" value={funnel.stages.find((s) => s.key === "first_launch")?.count ?? 0}
                  note="unique installations" />
            <Tile label="Completed scans" value={funnel.reliability.scanCompletions}
                  note={`${pct(funnel.reliability.scanSuccessRate)} of ${funnel.reliability.scanStarts} started`} />
            <Tile label="First values" value={funnel.mcp.firstValueInstallations}
                  note={`activation ${pct(funnel.mcp.activationRate)}`} />
            <Tile label="Feedback" value={funnel.feedback.submitted}
                  note={`${funnel.feedback.opened} opened`} />
          </div>

          <h2>Funnel</h2>
          <Funnel funnel={funnel} />

          <h2>Time to value</h2>
          <p className="note">
            Launch → scan complete: median {ms(funnel.timeToValue.launchToScanMedianMs)},
            p90 {ms(funnel.timeToValue.launchToScanP90Ms)} (N={funnel.timeToValue.scanSampleSize}).<br />
            Launch → first value: median {ms(funnel.timeToValue.launchToValueMedianMs)},
            p90 {ms(funnel.timeToValue.launchToValueP90Ms)} (N={funnel.timeToValue.valueSampleSize}).
            {funnel.timeToValue.valueSampleSize < 5 ? " Sample too small to read as a trend." : ""}
          </p>

          <h2>MCP</h2>
          <p className="note">
            Configured {funnel.mcp.configured} · initialized {funnel.mcp.initialized} ·
            first value {funnel.mcp.firstValueInstallations} · activation {pct(funnel.mcp.activationRate)}
          </p>
          <ul>
            {funnel.mcp.agents.length === 0 ? <li className="note">No MCP configuration yet.</li> : null}
            {funnel.mcp.agents.map((a) => (
              <li key={a.agent}>{a.agent}: {a.installations} installations</li>
            ))}
          </ul>

          <h2>Tool usage</h2>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead><tr style={{ textAlign: "left", opacity: 0.7 }}>
              <th style={{ padding: "6px 8px" }}>Tool</th>
              <th style={{ padding: "6px 8px" }}>Unique installs</th>
              <th style={{ padding: "6px 8px" }}>Total calls</th>
              <th style={{ padding: "6px 8px" }}>Success</th>
            </tr></thead>
            <tbody>
              {funnel.tools.length === 0 ? (
                <tr><td className="note" colSpan={4} style={{ padding: "6px 8px" }}>No tool calls yet.</td></tr>
              ) : null}
              {funnel.tools.map((t) => (
                <tr key={t.tool} style={{ borderTop: "1px solid rgba(128,128,128,.25)" }}>
                  <td style={{ padding: "6px 8px" }}>{t.tool}</td>
                  <td style={{ padding: "6px 8px" }}>{t.uniqueInstallations}</td>
                  <td style={{ padding: "6px 8px" }}>{t.totalCalls}</td>
                  <td style={{ padding: "6px 8px" }}>{pct(t.successRate)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2>Reliability</h2>
          <p className="note">
            Scans {funnel.reliability.scanCompletions}/{funnel.reliability.scanStarts} ({pct(funnel.reliability.scanSuccessRate)}),
            failures {funnel.reliability.scanFailures}.
            Tool calls {funnel.reliability.toolCalls}, failure rate {pct(funnel.reliability.toolFailureRate)}.
          </p>
          <ul>
            {funnel.reliability.topErrorCodes.map((e) => <li key={e.code}>{e.code}: {e.count}</li>)}
            {funnel.reliability.topErrorCodes.length === 0 ? <li className="note">No scan failures.</li> : null}
          </ul>
          <p className="note">
            Active versions: {funnel.reliability.versions.map((v) => `${v.version} (${v.installations})`).join(", ") || "-"}
          </p>

          <h2>Retention</h2>
          <p className="note">
            Installations active today: {funnel.retention.installationsToday} ·
            returning (launched on more than one day): {funnel.retention.returningInstallations} ·
            D1 {funnel.retention.d1 ? `${funnel.retention.d1.returned}/${funnel.retention.d1.cohort}` : "no cohort yet"} ·
            D7 {funnel.retention.d7 ? `${funnel.retention.d7.returned}/${funnel.retention.d7.cohort}` : "no cohort yet"}.
            These are installations, not users.
          </p>

          <h2>Feedback</h2>
          <p className="note">
            Opened {funnel.feedback.opened} · submitted {funnel.feedback.submitted}
            {funnel.feedback.opened > 0 && funnel.feedback.submitted === 0
              ? " - forms opened but nothing stored; check that the beta_feedback migration has been applied."
              : ""}
          </p>
          <ul>
            {funnel.feedback.categories.map((c) => <li key={c.category}>{c.category}: {c.count}</li>)}
          </ul>
          <p className="note">
            Message text is deliberately absent: feedback content is never sent through analytics.
            Read it in the beta_feedback table.
          </p>
        </>
      ) : null}
    </div></main>
  );
}
