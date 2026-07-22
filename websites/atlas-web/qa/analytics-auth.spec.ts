import { test, expect } from "playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  DESKTOP_ANALYTICS_EVENT_KEYS,
  analyticsBody,
  eventBatch,
  MAX_ANALYTICS_DEPTH,
  WEBSITE_ANALYTICS_EVENT_KEYS,
} from "../app/_lib/analytics-ingestion";
import {
  classifyBrowser,
  classifyDevice,
  classifyReferrer,
  analyticsEnvironment,
  isAnalyticsEvent,
  sanitizeIdentifier,
  sanitizeProperties,
  sanitizeRoute,
} from "../app/_lib/analytics-contract";
import { buildAnalyticsRow } from "../app/_lib/analytics-server";
import { createToken, hashPassword, sessionClaimsMatchRecord, verifyPassword, verifySessionToken, verifyToken } from "../app/_lib/auth";
import { PAID_PLANS_ENABLED } from "../app/_config";
import { BILLING_NOT_AVAILABLE, DisabledBillingProvider, proCheckoutReady } from "../app/_lib/billing";
import { isTrustedBrowserWrite } from "../app/_lib/request-security";
import { hasPaidAccess, transitionEntitlement } from "../app/_lib/billing-state";
import { parseWaitlistForm } from "../app/_lib/waitlist-form";
import {
  FeatureGate,
  FREE_ADVANCED_IMPACT_LIMIT,
  FreeOnlyEntitlementService,
  InMemoryUsageMeter,
} from "../app/_lib/free-plan";

test.beforeEach(() => {
  const env = process.env as Record<string, string | undefined>;
  env.AUTH_SECRET = "qa-only-stable-secret-with-more-than-32-bytes";
  env.NODE_ENV = "test";
  delete env.VERCEL_ENV;
});

test("canonical contract rejects unknown events and sensitive payloads", () => {
  expect(isAnalyticsEvent("site_visit")).toBe(true);
  expect(isAnalyticsEvent("installer_download_completed")).toBe(false);
  expect(isAnalyticsEvent("installer_download_started")).toBe(true);
  expect(isAnalyticsEvent("desktop_launched")).toBe(true);
  expect(isAnalyticsEvent("screen_active_ended")).toBe(false);
  expect(isAnalyticsEvent("api_me_success")).toBe(false);
  expect(sanitizeRoute("/pricing?email=private@example.com")).toBe("/pricing");
  expect(sanitizeRoute("C:\\Users\\private\\repo")).toBeNull();
  expect(sanitizeIdentifier("not valid spaces")).toBeNull();
  expect(sanitizeProperties({
    status: "ok",
    http_status: 202,
    password: "do-not-store",
    token: "do-not-store",
    surface: "C:\\Users\\private\\repo",
    prompt: "private code",
  })).toEqual({ status: "ok", http_status: 202 });
  expect(sanitizeProperties({ screen: "graph", duration_active_ms: 1200, duration_elapsed_ms: 2000 })).toEqual({
    screen: "graph", duration_active_ms: 1200, duration_elapsed_ms: 2000,
  });
});

test("analytics envelopes reject unknown fields and hostile nested payloads", async () => {
  expect(eventBatch({ eventName: "site_visit", unknown: "no" }, WEBSITE_ANALYTICS_EVENT_KEYS)).toBeNull();
  expect(eventBatch({ events: [{ eventName: "desktop_launched", installationId: "install-12345678" }], extra: true }, DESKTOP_ANALYTICS_EVENT_KEYS)).toBeNull();
  expect(eventBatch({ eventName: "site_visit", anonymousId: "anonymous-12345678" }, WEBSITE_ANALYTICS_EVENT_KEYS)).toHaveLength(1);
  let nested: unknown = "leaf";
  for (let index = 0; index <= MAX_ANALYTICS_DEPTH; index += 1) nested = { nested };
  const deepRequest = new Request("http://localhost/api/analytics/events", { method: "POST", body: JSON.stringify(nested) });
  expect(await analyticsBody(deepRequest)).toBeNull();
  expect(sanitizeProperties({ repo: "repo-name", status: "ok", token: "eyJ.fake.secret" })).toEqual({ status: "ok" });
});

test("request context is classified without persisting raw referrers or user agents", () => {
  expect(classifyReferrer("https://www.google.com/search?q=atlas")).toBe("search");
  expect(classifyReferrer("https://news.ycombinator.com/item?id=1")).toBe("social");
  expect(classifyDevice("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)")).toBe("mobile");
  expect(classifyBrowser("Mozilla/5.0 Chrome/124.0.0.0 Safari/537.36")).toBe("chrome");
});

test("server owns environment, identity, version and deterministic deduplication", () => {
  expect(analyticsEnvironment()).toBe("test");
  const input = {
    eventName: "account_create_success" as const,
    source: "website" as const,
    anonymousId: "anonymous-12345678",
    sessionId: "session-12345678",
    route: "/login",
    deduplicationKey: "attempt-12345678",
    userId: "00000000-0000-4000-8000-000000000001",
  };
  const first = buildAnalyticsRow(input);
  const retry = buildAnalyticsRow(input);
  expect(first.id).not.toBe(retry.id);
  expect(first.deduplication_key).toBe(retry.deduplication_key);
  expect(first.environment).toBe("test");
  expect(first.is_internal).toBe(true);
  expect(first.user_id).toBe(input.userId);
  expect(first.metadata).toEqual({});
});

test("desktop version accepts a safe semver without treating it as an identifier", () => {
  const row = buildAnalyticsRow({
    eventName: "desktop_launched", source: "desktop", installationId: "installation-12345678",
    sessionId: "desktop-session-12345678", appVersion: "1.0.5", buildCommit: "a".repeat(40),
    properties: { screen: "home", duration_active_ms: 1000 },
  });
  expect(row.app_version).toBe("1.0.5");
  expect(row.duration_active_ms).toBe(1000);
  expect(row.metadata).toEqual({ screen: "home", duration_active_ms: 1000 });
});

test("password hashes and signed sessions validate and expire", () => {
  const hash = hashPassword("correct horse battery staple");
  expect(hash).not.toContain("correct horse");
  expect(verifyPassword("correct horse battery staple", hash)).toBe(true);
  expect(verifyPassword("wrong password", hash)).toBe(false);

  const valid = createToken("qa-user", 60);
  const expired = createToken("qa-user", -1);
  expect(verifyToken(valid)).toBe("qa-user");
  expect(verifySessionToken(valid)?.sid).toHaveLength(36);
  expect(verifyToken(expired)).toBeNull();
  expect(verifyToken(`${valid}tampered`)).toBeNull();
});

test("server session records rotate, revoke, expire, and cannot cross identities", () => {
  const first = createToken("qa-user", 60);
  const second = createToken("qa-user", 60);
  expect(first).not.toBe(second);
  const claims = verifySessionToken(first)!;
  const validRecord = {
    id: claims.sid, userId: claims.sub, expiresAt: new Date(Date.now() + 60_000).toISOString(), revokedAt: null,
  };
  expect(sessionClaimsMatchRecord(claims, validRecord)).toBe(true);
  expect(sessionClaimsMatchRecord(claims, { ...validRecord, revokedAt: new Date().toISOString() })).toBe(false);
  expect(sessionClaimsMatchRecord(claims, { ...validRecord, userId: "another-user" })).toBe(false);
  expect(sessionClaimsMatchRecord(claims, { ...validRecord, expiresAt: new Date(Date.now() - 1).toISOString() })).toBe(false);
});

test("authenticated requests are bound to an opaque server session record", () => {
  const auth = fs.readFileSync(path.join(process.cwd(), "app", "_lib", "auth.ts"), "utf8");
  const migration = fs.readFileSync(
    path.join(process.cwd(), "supabase", "migrations", "20260717103000_v105_server_authoritative_sessions.sql"),
    "utf8"
  );
  expect(auth).toContain("await store.getSession(claims.sid)");
  expect(auth).toContain("await store.revokeSession(claims.sid)");
  expect(auth).toContain("crypto.randomBytes(32)");
  const deletion = fs.readFileSync(path.join(process.cwd(), "app", "api", "account", "delete", "route.ts"), "utf8");
  expect(deletion).toContain("await store.revokeSessionsForUser(user.id)");
  expect(migration).toContain("atlas_sessions");
  expect(migration).toContain("enable row level security");
  expect(migration).toContain("on delete cascade");
});

test("migration keeps browser roles server-only", () => {
  const migration = fs.readFileSync(
    path.join(process.cwd(), "supabase", "migrations", "20260714211752_secure_auth_analytics_data.sql"),
    "utf8"
  );
  expect(migration).toContain("revoke all on table public.analytics_events from public, anon, authenticated");
  expect(migration).toContain("revoke execute on function public.atlas_rate_limit_hit");
  expect(migration).toContain("analytics_events_deduplication_key_uidx");
  expect(migration).toContain("grant execute on function public.atlas_analytics_summary");
  const v105 = fs.readFileSync(
    path.join(process.cwd(), "supabase", "migrations", "20260716200846_v105_analytics_engagement_and_desktop_ingestion.sql"),
    "utf8"
  );
  expect(v105).toContain("duration_active_ms");
  expect(v105).toContain("atlas_purge_analytics_events");
  expect(v105).toContain("revoke execute on function public.atlas_purge_analytics_events");
  expect(v105).toContain("event_name = 'graph_opened'");
  expect(v105).toContain("event_name = 'impact_completed'");
  expect(v105).not.toContain("ask_completed");
});

test("paid checkout remains source-disabled regardless of environment configuration", () => {
  expect(PAID_PLANS_ENABLED).toBe(false);
  expect(proCheckoutReady()).toBe(false);
});

test("disabled billing has no checkout, portal, cancellation, or webhook side effect", async () => {
  const provider = new DisabledBillingProvider();
  const user = { id: "qa-user", email: "qa@example.com" } as never;
  await expect(provider.createCheckout(user, "pro")).rejects.toMatchObject({ code: BILLING_NOT_AVAILABLE });
  await expect(provider.createCustomerPortalSession(user)).rejects.toMatchObject({ code: BILLING_NOT_AVAILABLE });
  await expect(provider.cancelImmediately(user)).rejects.toMatchObject({ code: BILLING_NOT_AVAILABLE });
  expect(provider.verifyWebhook("{}", "ts=1;h1=00")).toBe(false);
  expect(await provider.processWebhookEvent({ event_type: "subscription.created" })).toEqual({ ok: true, action: "ignored_billing_disabled" });
});

test("billing state transitions fail closed and reject out-of-order resurrection", () => {
  const active = { state: "active" as const, revision: 1, observedAt: "2026-07-17T10:00:00.000Z" };
  const scheduled = transitionEntitlement(active, { kind: "schedule_cancellation", observedAt: "2026-07-17T10:01:00.000Z" });
  expect(scheduled.state).toBe("cancel_scheduled");
  expect(hasPaidAccess(scheduled.state)).toBe(true);
  const canceled = transitionEntitlement(scheduled, { kind: "cancel_immediately", observedAt: "2026-07-17T10:02:00.000Z" });
  expect(canceled.state).toBe("canceled");
  expect(hasPaidAccess(canceled.state)).toBe(false);
  expect(transitionEntitlement(canceled, { kind: "provider_observed", state: "active", observedAt: "2026-07-17T10:01:30.000Z" })).toEqual(canceled);
  expect(hasPaidAccess("unknown")).toBe(false);
});

test("free plan limits are server-owned, shared, and resilient to client clock changes", async () => {
  let now = Date.parse("2026-07-17T00:00:00.000Z");
  const meter = new InMemoryUsageMeter(() => now);
  const firstInstance = new FeatureGate(new FreeOnlyEntitlementService(), meter);
  const secondInstance = new FeatureGate(new FreeOnlyEntitlementService(), meter);
  const identity = "account-identity";
  expect((await firstInstance.consume(identity, "active_repository", { demo: true })).used).toBe(0);
  expect((await firstInstance.consume(identity, "active_repository")).allowed).toBe(true);
  expect((await secondInstance.consume(identity, "active_repository")).allowed).toBe(false);
  for (let index = 0; index < FREE_ADVANCED_IMPACT_LIMIT; index += 1) {
    expect((await firstInstance.consume(identity, "advanced_impact")).allowed).toBe(true);
  }
  expect((await secondInstance.consume(identity, "advanced_impact")).allowed).toBe(false);
  now -= 12 * 60 * 60 * 1000;
  expect((await firstInstance.consume(identity, "advanced_impact")).allowed).toBe(false);
});

test("browser writes reject hostile origins while allowing same-origin and native requests", () => {
  expect(isTrustedBrowserWrite(new Request("http://localhost:3000/api/auth/login", {
    method: "POST", headers: { origin: "http://localhost:3000" },
  }))).toBe(true);
  expect(isTrustedBrowserWrite(new Request("http://localhost:3000/api/auth/login", {
    method: "POST", headers: { origin: "https://attacker.example", "sec-fetch-site": "cross-site" },
  }))).toBe(false);
  expect(isTrustedBrowserWrite(new Request("http://localhost:3000/api/auth/login", {
    method: "POST", headers: { "sec-fetch-site": "same-origin" },
  }))).toBe(false);
  expect(isTrustedBrowserWrite(new Request("http://localhost:3000/api/auth/login", { method: "POST" }))).toBe(true);
});

test("waitlist accepts only its bounded public form schema", () => {
  const valid = new FormData(); valid.set("email", "person@example.com"); valid.set("role", "developer");
  expect(parseWaitlistForm(valid)).toEqual({ email: "person@example.com", role: "developer" });
  const forged = new FormData(); forged.set("email", "person@example.com"); forged.set("role", "developer"); forged.set("user_id", "admin");
  expect(parseWaitlistForm(forged)).toBeNull();
  const duplicate = new FormData(); duplicate.append("email", "person@example.com"); duplicate.append("email", "other@example.com");
  expect(parseWaitlistForm(duplicate)).toBeNull();
});

test("security-header baseline denies framing and keeps payment origins absent", () => {
  const config = fs.readFileSync(path.join(process.cwd(), "next.config.mjs"), "utf8");
  expect(config).toContain("X-Frame-Options");
  expect(config).toContain("Content-Security-Policy");
  expect(config).not.toContain("Content-Security-Policy-Report-Only");
  expect(config).not.toContain("unsafe-eval");
  expect(config).toContain("frame-ancestors 'none'");
  expect(config).toContain("Strict-Transport-Security");
  expect(config).not.toMatch(/paddle\.com/i);
});
