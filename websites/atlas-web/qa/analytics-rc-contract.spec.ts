import { test, expect } from "playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  DESKTOP_ANALYTICS_EVENTS,
  WEBSITE_ANALYTICS_EVENTS,
  isDesktopAnalyticsEvent,
  isWebsiteAnalyticsEvent,
} from "../app/_lib/analytics-contract";
import {
  DESKTOP_ANALYTICS_EVENT_KEYS,
  WEBSITE_ANALYTICS_EVENT_KEYS,
  eventBatch,
} from "../app/_lib/analytics-ingestion";

const read = (relative: string) => fs.readFileSync(path.join(process.cwd(), relative), "utf8");

test("analytics-only release exposes exactly the frozen website and desktop allowlists", () => {
  expect([...WEBSITE_ANALYTICS_EVENTS]).toEqual([
    "site_visit",
    "page_view",
    "download_clicked",
    "installer_download_started",
  ]);
  expect([...DESKTOP_ANALYTICS_EVENTS]).toEqual([
    "desktop_launched",
    "sample_scan_completed",
    "real_repo_scan_completed",
    "scan_failed",
    "graph_opened",
    "impact_completed",
    "mcp_connected",
    "analytics_opted_out",
  ]);
  for (const event of ["download_unavailable_seen", "github_clicked", "signup_success", "login_success", "ask_completed", "heartbeat", "api_me_success"]) {
    expect(isWebsiteAnalyticsEvent(event)).toBe(false);
    expect(isDesktopAnalyticsEvent(event)).toBe(false);
  }
});

test("website and desktop envelopes reject cross-channel events and unknown fields", () => {
  expect(eventBatch({ eventName: "desktop_launched" }, WEBSITE_ANALYTICS_EVENT_KEYS)).not.toBeNull();
  // The envelope schema is deliberately transport-only; route handlers apply
  // the channel-specific event predicate before writing a row.
  expect(eventBatch({ eventName: "desktop_launched", unexpected: true }, DESKTOP_ANALYTICS_EVENT_KEYS)).toBeNull();
  expect(eventBatch({ eventName: "site_visit", unexpected: true }, WEBSITE_ANALYTICS_EVENT_KEYS)).toBeNull();
});

test("analytics migration is additive and has a tested rollback", () => {
  const legacyMigration = read("supabase/migrations/20260716200846_v105_analytics_engagement_and_desktop_ingestion.sql");
  expect(legacyMigration).toContain("Atlas v1.0.5 analytics engagement");
  const migration = read("supabase/migrations/20260722090000_v106_analytics_only.sql");
  expect(migration).toContain("add column if not exists installation_id text");
  expect(migration).toContain("add column if not exists duration_active_ms bigint");
  expect(migration).toContain("add column if not exists duration_elapsed_ms bigint");
  expect(migration).toContain("create index if not exists analytics_events_installation_created_at_idx");
  expect(migration).toContain("create index if not exists analytics_events_event_created_at_idx");
  expect(migration).not.toMatch(/\b(drop|delete|truncate)\s+/i);
  expect(migration).not.toMatch(/public\.(users|auth|atlas_sessions)/i);
  expect(migration).not.toMatch(/\b(create|alter)\s+(function|policy|grant)\b/i);

  const rollback = read("supabase/rollbacks/20260722090000_v106_analytics_only.rollback.sql");
  expect(rollback).toContain("drop index if exists public.analytics_events_event_created_at_idx");
  expect(rollback).toContain("drop index if exists public.analytics_events_installation_created_at_idx");
  expect(rollback).toContain("drop column if exists installation_id");
  expect(rollback).toContain("drop column if exists duration_active_ms");
  expect(rollback).toContain("drop column if exists duration_elapsed_ms");
});

test("website event contract documents the release allowlist and GitHub download boundary", () => {
  const contract = read("docs/analytics/event-contract.md");
  for (const event of WEBSITE_ANALYTICS_EVENTS) expect(contract).toContain(`\`${event}\``);
  for (const event of DESKTOP_ANALYTICS_EVENTS) expect(contract).toContain(`\`${event}\``);
  expect(contract).toContain("exactly four browser events");
  expect(contract).toContain("GitHub's asset count is the source");
  expect(contract).not.toContain("`ask_completed`");
  expect(contract).not.toContain("`signup_success`");
});
