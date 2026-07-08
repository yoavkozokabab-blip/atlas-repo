#!/usr/bin/env node
/**
 * E2E analytics probe — production Supabase + website API.
 *
 * Usage:
 *   node scripts/analytics-e2e-probe.mjs
 *   node scripts/analytics-e2e-probe.mjs --web https://atlas-repo-chi.vercel.app
 *
 * Loads env from websites/jarvis-landing/.env.production.local when present.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");

function loadEnvFile(file) {
  try {
    for (const line of fs.readFileSync(file, "utf8").split("\n")) {
      const m = line.match(/^([^#=]+)=(.*)$/);
      if (!m) continue;
      const key = m[1].trim();
      let val = m[2].trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      if (!val || val === '""' || val === "''") continue;
      if (!cleanEnv(process.env[key])) process.env[key] = val;
    }
  } catch {
    /* optional */
  }
}

function cleanEnv(v) {
  if (v == null) return "";
  let s = String(v).trim();
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    s = s.slice(1, -1).trim();
  }
  return s;
}

if (!cleanEnv(process.env.SUPABASE_URL) || !cleanEnv(process.env.SUPABASE_SERVICE_ROLE_KEY)) {
  loadEnvFile(path.join(ROOT, "websites/jarvis-landing/.env.production.local"));
  loadEnvFile(path.join(ROOT, "websites/jarvis-landing/.env.local"));
}

const WEB = (process.argv.find((a) => a.startsWith("--web=")) || "--web=https://atlas-repo-chi.vercel.app")
  .split("=")[1]
  .replace(/\/+$/, "");
const SUPABASE_URL = cleanEnv(process.env.SUPABASE_URL).replace(/\/+$/, "").replace(/\/rest\/v1$/i, "");
const KEY = cleanEnv(process.env.SUPABASE_SERVICE_ROLE_KEY);
const REST = `${SUPABASE_URL}/rest/v1`;
const probeId = `rc_probe_${Date.now()}`;

const rows = [];

function record(check, result, evidence) {
  rows.push({ check, result, evidence });
}

async function sb(pathAndQuery, init = {}) {
  const res = await fetch(`${REST}/${pathAndQuery}`, {
    ...init,
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  const text = await res.text();
  return { ok: res.ok, status: res.status, text, json: text ? JSON.parse(text) : null };
}

async function main() {
  if (!SUPABASE_URL || !KEY) {
    record("Supabase env", "FAIL", "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
    printTable();
    process.exit(2);
  }

  const counts = await sb(
    "analytics_events?select=event_name&limit=5000"
  );
  if (!counts.ok) {
    record(
      "Supabase analytics_events query",
      "FAIL",
      `${counts.status}: ${counts.text.slice(0, 200)}`
    );
  } else {
    const byName = {};
    for (const row of counts.json || []) {
      byName[row.event_name] = (byName[row.event_name] || 0) + 1;
    }
    const total = (counts.json || []).length;
    record("Supabase analytics_events query", "PASS", `sampled ${total} rows`);
    record("Supabase analytics_events count (sample)", total > 0 ? "PASS" : "WARN", String(total));
    record("Supabase event_name breakdown", "INFO", JSON.stringify(byName).slice(0, 300));
  }

  const idRes = await sb("analytics_identities?select=identity_key&limit=1");
  if (!idRes.ok) {
    record("Supabase analytics_identities query", "FAIL", `${idRes.status}: ${idRes.text.slice(0, 200)}`);
  } else {
    const countRes = await sb("analytics_identities?select=identity_key&limit=5000");
    const n = (countRes.json || []).length;
    record("Supabase analytics_identities query", "PASS", `${n} identities (sampled)`);
  }

  const eventBody = {
    event_name: "site_visit",
    anonymous_id: probeId,
    source: "website",
    metadata: { page: "/rc_probe", source_kind: "rc_probe" },
  };
  const postRes = await fetch(`${WEB}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eventBody),
  });
  const postJson = await postRes.json().catch(() => ({}));
  record(
    "Website POST /api/events",
    postRes.ok && postJson.ok ? "PASS" : "FAIL",
    `${postRes.status} ${JSON.stringify(postJson)}`
  );

  if (postRes.ok && postJson.ok) {
    const found = await sb(
      `analytics_events?select=event_name,anonymous_id&anonymous_id=eq.${encodeURIComponent(probeId)}&limit=1`
    );
    record(
      "Probe event in Supabase",
      found.ok && (found.json || []).length > 0 ? "PASS" : "FAIL",
      found.ok ? `rows=${(found.json || []).length}` : found.text.slice(0, 200)
    );
  }

  const dashRes = await fetch(`${WEB}/api/auth/desktop/admin/analytics/dashboard`);
  const dashJson = await dashRes.json().catch(() => ({}));
  const dashType = dashRes.headers.get("content-type") || "";
  record(
    "Desktop dashboard route JSON",
    dashType.includes("json") ? "PASS" : "FAIL",
    `${dashRes.status} content-type=${dashType}`
  );
  record(
    "Dashboard without auth",
    dashRes.status === 403 ? "PASS" : "WARN",
    JSON.stringify(dashJson).slice(0, 120)
  );

  printTable();
  const failed = rows.some((r) => r.result === "FAIL");
  process.exit(failed ? 1 : 0);
}

function printTable() {
  console.log("\n| Check | Result | Evidence |");
  console.log("| ----- | ------ | -------- |");
  for (const r of rows) {
    const ev = String(r.evidence).replace(/\|/g, "/").replace(/\n/g, " ").slice(0, 120);
    console.log(`| ${r.check} | ${r.result} | ${ev} |`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
