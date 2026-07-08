#!/usr/bin/env node
/**
 * Launch funnel analytics summary (Supabase PostgREST).
 *
 * Usage:
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... node scripts/analytics-summary.mjs
 *   node scripts/analytics-summary.mjs --probe   # insert one test event, then summarize
 */

const SUPABASE_URL = (process.env.SUPABASE_URL || "").replace(/\/+$/, "").replace(/\/rest\/v1$/i, "");
const KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const REST = `${SUPABASE_URL}/rest/v1`;

const FAIL_EVENTS = new Set([
  "signup_failed",
  "api_desktop_login_failed",
  "api_me_failed",
  "desktop_login_failed",
  "desktop_me_failed",
]);

async function sb(path, init = {}) {
  const res = await fetch(`${REST}/${path}`, {
    ...init,
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} failed: ${res.status} ${text.slice(0, 300)}`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : [];
}

function countBy(events, key) {
  const out = {};
  for (const row of events) {
    const k = row[key] || "unknown";
    out[k] = (out[k] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(out).sort((a, b) => b[1] - a[1]));
}

function avg(nums) {
  const v = nums.filter((n) => typeof n === "number");
  return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null;
}

async function probe() {
  const row = {
    event_name: "site_visit",
    source: "analytics_probe",
    anonymous_id: `probe-${Date.now()}`,
    app_version: "probe",
    platform: "node",
    metadata: { page: "/probe" },
  };
  await sb("analytics_events", { method: "POST", body: JSON.stringify(row), headers: { Prefer: "return=minimal" } });
  console.log("Probe event inserted: site_visit (source=analytics_probe)");
}

async function main() {
  if (!SUPABASE_URL || !KEY) {
    console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
    process.exit(2);
  }
  if (process.argv.includes("--probe")) {
    await probe();
  }

  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const [users, recentUsers, events, lastEvents, identities] = await Promise.all([
    sb("users?select=id"),
    sb(`users?select=id,created_at&created_at=gte.${encodeURIComponent(since)}`),
    sb("analytics_events?select=event_name,metadata,created_at&order=created_at.desc&limit=5000"),
    sb("analytics_events?select=event_name,source,created_at,metadata&order=created_at.desc&limit=20"),
    sb("analytics_identities?select=total_ttfv_sec,install_to_open_sec,open_to_login_sec,login_to_repo_sec,repo_to_first_context_sec,first_seen,last_seen,days_active,sessions_count,tool_calls_count&limit=5000").catch(() => []),
  ]);

  const byName = countBy(events, "event_name");
  const failures = events.filter((e) => FAIL_EVENTS.has(e.event_name));
  const failuresByReason = {};
  for (const row of failures) {
    const reason = row.metadata?.reason || row.metadata?.error_code || "unknown";
    const key = `${row.event_name}:${reason}`;
    failuresByReason[key] = (failuresByReason[key] || 0) + 1;
  }

  const ttfvRows = (identities || []).filter((r) => r.total_ttfv_sec != null);
  const ttfvAvg = {
    install_to_open_sec: avg(ttfvRows.map((r) => r.install_to_open_sec)),
    open_to_login_sec: avg(ttfvRows.map((r) => r.open_to_login_sec)),
    login_to_repo_sec: avg(ttfvRows.map((r) => r.login_to_repo_sec)),
    repo_to_first_context_sec: avg(ttfvRows.map((r) => r.repo_to_first_context_sec)),
    total_ttfv_sec: avg(ttfvRows.map((r) => r.total_ttfv_sec)),
  };

  console.log("=== Atlas Launch Analytics (RC) ===");
  console.log(`Total users: ${users.length}`);
  console.log(`Users created last 24h: ${recentUsers.length}`);
  console.log(`Identities tracked: ${(identities || []).length}`);
  console.log("");
  console.log("Events by event_name:");
  for (const [name, count] of Object.entries(byName)) {
    console.log(`  ${name}: ${count}`);
  }
  console.log("");
  console.log("Funnel highlights:");
  for (const key of [
    "site_visit",
    "download_clicked",
    "desktop_installed",
    "desktop_opened",
    "desktop_login_success",
    "desktop_login_failed",
    "desktop_me_success",
    "repo_connected",
    "first_context_generated",
    "cursor_connected",
    "claude_connected",
    "codex_connected",
    "cursor_used",
    "claude_used",
    "codex_used",
    "atlas_tool_call",
    "agent_context_injected",
  ]) {
    console.log(`  ${key}: ${byName[key] || 0}`);
  }
  console.log("");
  console.log("Average TTFV (seconds, from analytics_identities):");
  for (const [k, v] of Object.entries(ttfvAvg)) {
    console.log(`  ${k}: ${v ?? "n/a"}`);
  }
  console.log("");
  console.log("Failures grouped by event_name:reason:");
  for (const [key, count] of Object.entries(failuresByReason).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${key}: ${count}`);
  }
  console.log("");
  console.log("Last 20 events:");
  for (const row of lastEvents) {
    console.log(`  ${row.created_at}  ${row.event_name}  source=${row.source}`);
  }
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
