#!/usr/bin/env node
/**
 * Apply analytics migrations (0003–0005) to Supabase via PostgREST RPC is not possible;
 * this script verifies table access and applies grants when tables exist.
 *
 * For DDL (create tables), run the SQL files in Supabase SQL Editor first.
 *
 * Usage:
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... node scripts/apply-analytics-migration.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");

function cleanEnv(v) {
  if (v == null) return "";
  let s = String(v).trim();
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) s = s.slice(1, -1).trim();
  return s;
}

function loadEnvFile(file) {
  try {
    for (const line of fs.readFileSync(file, "utf8").split("\n")) {
      const m = line.match(/^([^#=]+)=(.*)$/);
      if (!m) continue;
      const key = m[1].trim();
      let val = m[2].trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) val = val.slice(1, -1);
      if (!val) continue;
      if (!cleanEnv(process.env[key])) process.env[key] = val;
    }
  } catch {
    /* optional */
  }
}

loadEnvFile(path.join(ROOT, "websites/jarvis-landing/.env.local"));

const SUPABASE_URL = cleanEnv(process.env.SUPABASE_URL).replace(/\/+$/, "").replace(/\/rest\/v1$/i, "");
const KEY = cleanEnv(process.env.SUPABASE_SERVICE_ROLE_KEY);
const REST = `${SUPABASE_URL}/rest/v1`;

async function rest(pathAndQuery, init = {}) {
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
  return { ok: res.ok, status: res.status, text };
}

async function main() {
  if (!SUPABASE_URL || !KEY) {
    console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY");
    process.exit(2);
  }

  console.log(`Probing ${SUPABASE_URL} ...`);

  const probe = await rest("analytics_events?select=id&limit=1");
  if (!probe.ok) {
    console.error(`analytics_events not readable: ${probe.status} ${probe.text.slice(0, 300)}`);
    console.error("\nRun these SQL files in Supabase SQL Editor (in order):");
    console.error("  websites/jarvis-landing/supabase/migrations/0003_analytics_events.sql");
    console.error("  websites/jarvis-landing/supabase/migrations/0004_analytics_identities.sql");
    console.error("  websites/jarvis-landing/supabase/migrations/0005_analytics_grants.sql");
    process.exit(1);
  }

  const insert = await rest("analytics_events", {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      event_name: "site_visit",
      source: "migration_probe",
      anonymous_id: `migrate_probe_${Date.now()}`,
      metadata: { page: "/migrate_probe" },
    }),
  });
  if (!insert.ok) {
    console.error(`analytics_events insert failed: ${insert.status} ${insert.text.slice(0, 300)}`);
    console.error("\nLikely missing service_role GRANTs. Run:");
    console.error("  websites/jarvis-landing/supabase/migrations/0005_analytics_grants.sql");
    process.exit(1);
  }

  console.log("OK: analytics_events readable and writable.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
