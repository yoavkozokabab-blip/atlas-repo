import { test, expect } from "playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  analyticsEnvironment,
  isAnalyticsEvent,
  sanitizeIdentifier,
  sanitizeProperties,
  sanitizeRoute,
} from "../app/_lib/analytics-contract";
import { buildAnalyticsRow } from "../app/_lib/analytics-server";
import { createToken, hashPassword, verifyPassword, verifyToken } from "../app/_lib/auth";

test.beforeEach(() => {
  const env = process.env as Record<string, string | undefined>;
  env.AUTH_SECRET = "qa-only-stable-secret-with-more-than-32-bytes";
  env.NODE_ENV = "test";
  delete env.VERCEL_ENV;
});

test("canonical contract rejects unknown events and sensitive payloads", () => {
  expect(isAnalyticsEvent("site_visit")).toBe(true);
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
});

test("server owns environment, identity, version and deterministic deduplication", () => {
  expect(analyticsEnvironment()).toBe("test");
  const input = {
    eventName: "signup_success" as const,
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

test("password hashes and signed sessions validate and expire", () => {
  const hash = hashPassword("correct horse battery staple");
  expect(hash).not.toContain("correct horse");
  expect(verifyPassword("correct horse battery staple", hash)).toBe(true);
  expect(verifyPassword("wrong password", hash)).toBe(false);

  const valid = createToken("qa-user", 60);
  const expired = createToken("qa-user", -1);
  expect(verifyToken(valid)).toBe("qa-user");
  expect(verifyToken(expired)).toBeNull();
  expect(verifyToken(`${valid}tampered`)).toBeNull();
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
});
