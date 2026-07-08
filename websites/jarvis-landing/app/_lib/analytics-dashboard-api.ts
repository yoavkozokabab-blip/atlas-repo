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

type LoadResult<T> = { data: T; error?: string };

async function loadEvents(limit = 10000): Promise<LoadResult<{ event_name: string; created_at: string }[]>> {
  if (!ENV.hasSupabase) {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const file = path.join(process.cwd(), ENV.dataDir, "analytics_events.jsonl");
    try {
      const lines = fs.readFileSync(file, "utf8").trim().split("\n").filter(Boolean);
      return {
        data: lines
          .map((line) => JSON.parse(line) as { event_name: string; created_at: string })
          .slice(-limit),
      };
    } catch {
      return { data: [] };
    }
  }
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) {
    return { data: [], error: "Analytics backend is not configured." };
  }
  const res = await fetch(
    `${restBase()}/analytics_events?select=event_name,created_at&order=created_at.desc&limit=${limit}`,
    {
      cache: "no-store",
      headers: { apikey: key, Authorization: `Bearer ${key}` },
    }
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    const hint = res.status === 404 || body.includes("analytics_events")
      ? " Run Supabase migrations 0003–0005 on the production project."
      : "";
    return {
      data: [],
      error: `Analytics backend error: analytics_events query failed (${res.status}).${hint}`,
    };
  }
  return { data: (await res.json()) as { event_name: string; created_at: string }[] };
}

export async function buildAnalyticsDashboardPayload() {
  const [eventLoad, identityLoad] = await Promise.all([loadEvents(), loadAllIdentities()]);
  const events = eventLoad.data;
  const identities = identityLoad.data;
  const backendError = eventLoad.error || identityLoad.error;

  if (backendError) {
    return {
      ok: false,
      error: backendError,
      backend: ENV.hasSupabase ? "supabase" : "file",
      generated_at: new Date().toISOString(),
      events_total: 0,
      funnel: [],
      conversion: [],
      ttfv: {},
      retention: { d1: 0, d7: 0, d30: 0 },
      agents: {
        most_used: "none",
        connected: { cursor: 0, claude: 0, codex: 0 },
        used: { cursor: 0, claude: 0, codex: 0 },
      },
      drop_off: null,
      identity_rollups: {
        total_identities: 0,
        with_ttfv: 0,
        avg_tool_calls: 0,
        avg_sessions: 0,
      },
    };
  }

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

  const payload = {
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

  if (events.length === 0) {
    return { ...payload, notice: "No analytics events found yet." };
  }
  return payload;
}
