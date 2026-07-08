import { ENV } from "./config";
import {
  activeUsersToday,
  averageTtfvFromIdentities,
  buildFunnel,
  countEventsByName,
  findDropOff,
  mostUsedAgent,
  returningUsers,
} from "./analytics-dashboard";
import { loadAllIdentities, retentionRates } from "./analytics-identity";

function restBase(): string {
  const raw = (process.env.SUPABASE_URL || "").trim().replace(/\/+$/, "");
  const origin = raw.replace(/\/rest\/v1$/i, "");
  return `${origin}/rest/v1`;
}

async function loadEvents(limit = 10000): Promise<{ event_name: string; created_at: string }[]> {
  if (ENV.hasSupabase) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
    const res = await fetch(
      `${restBase()}/analytics_events?select=event_name,created_at&order=created_at.desc&limit=${limit}`,
      {
        cache: "no-store",
        headers: { apikey: key, Authorization: `Bearer ${key}` },
      }
    );
    if (!res.ok) return [];
    return (await res.json()) as { event_name: string; created_at: string }[];
  }
  const fs = await import("node:fs");
  const path = await import("node:path");
  const file = path.join(process.cwd(), ENV.dataDir, "analytics_events.jsonl");
  try {
    const lines = fs.readFileSync(file, "utf8").trim().split("\n").filter(Boolean);
    return lines
      .map((line) => JSON.parse(line) as { event_name: string; created_at: string })
      .slice(-limit);
  } catch {
    return [];
  }
}

export async function buildAnalyticsDashboardPayload() {
  const [events, identities] = await Promise.all([loadEvents(), loadAllIdentities()]);
  const byName = countEventsByName(events);
  const funnel = buildFunnel(byName);
  const dropOff = findDropOff(funnel);
  const ttfv = averageTtfvFromIdentities(identities);
  const retention = retentionRates(identities);

  const extraSteps = [
    { key: "active_today", label: "Active Users Today", count: activeUsersToday(identities) },
    { key: "returning", label: "Returning Users", count: returningUsers(identities) },
    { key: "paying", label: "Paying Users (placeholder)", count: 0 },
  ];

  return {
    ok: true,
    backend: ENV.hasSupabase ? "supabase" : "file",
    generated_at: new Date().toISOString(),
    funnel: [...funnel, ...extraSteps.map((s) => ({ ...s, conversionFromPrev: null }))],
    conversion: funnel.filter((s) => s.conversionFromPrev != null),
    ttfv,
    retention,
    agents: {
      most_used: mostUsedAgent(byName, identities),
      connected: {
        cursor: byName.cursor_connected || 0,
        claude: byName.claude_connected || 0,
        codex: byName.codex_connected || 0,
      },
      used: {
        cursor: byName.cursor_used || 0,
        claude: byName.claude_used || 0,
        codex: byName.codex_used || 0,
      },
    },
    drop_off: dropOff,
    identity_rollups: {
      total_identities: identities.length,
      with_ttfv: identities.filter((r) => r.total_ttfv_sec != null).length,
      avg_tool_calls:
        identities.length > 0
          ? Math.round(
              identities.reduce((a, r) => a + Number(r.tool_calls_count || 0), 0) / identities.length
            )
          : 0,
      avg_sessions:
        identities.length > 0
          ? Math.round(
              identities.reduce((a, r) => a + Number(r.sessions_count || 0), 0) / identities.length
            )
          : 0,
    },
    events_total: events.length,
  };
}
