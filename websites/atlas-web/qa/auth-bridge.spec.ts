import { expect, test } from "playwright/test";
import fs from "node:fs";
import path from "node:path";

import {
  authenticateOrMigrateLegacyUser,
  type PasswordAuthority,
} from "../app/_lib/auth-bridge";


function authority(overrides: Partial<PasswordAuthority> = {}): PasswordAuthority {
  return {
    signIn: async () => ({ status: "invalid" }),
    findByEmail: async () => ({ status: "missing" }),
    createLegacyIdentity: async () => ({ status: "created", userId: "auth-new" }),
    ...overrides,
  };
}

function input(overrides: Record<string, unknown> = {}) {
  return {
    userId: "legacy-user",
    email: "Legacy@Example.Test ",
    password: "correct-current-password",
    legacyPasswordValid: true,
    authority: authority(),
    bridgeStore: { linkAuthIdentity: async () => true },
    ...overrides,
  };
}

test("legacy password creates, links and disables legacy authority", async () => {
  const calls: string[] = [];
  const result = await authenticateOrMigrateLegacyUser(input({
    authority: authority({
      signIn: async (email) => {
        calls.push(`sign:${email}`);
        return { status: "invalid" };
      },
      findByEmail: async (email) => {
        calls.push(`find:${email}`);
        return { status: "missing" };
      },
      createLegacyIdentity: async (email) => {
        calls.push(`create:${email}`);
        return { status: "created", userId: "auth-new" };
      },
    }),
    bridgeStore: {
      linkAuthIdentity: async (userId: string, authUserId: string) => {
        calls.push(`link:${userId}:${authUserId}`);
        return true;
      },
    },
  }));

  expect(result).toEqual({ status: "migrated", authUserId: "auth-new" });
  expect(calls).toEqual([
    "sign:legacy@example.test",
    "find:legacy@example.test",
    "create:legacy@example.test",
    "link:legacy-user:auth-new",
  ]);
});

test("wrong legacy password never calls Auth Admin", async () => {
  let called = false;
  const result = await authenticateOrMigrateLegacyUser(input({
    legacyPasswordValid: false,
    authority: authority({
      signIn: async () => {
        called = true;
        return { status: "invalid" };
      },
    }),
  }));

  expect(result).toEqual({ status: "invalid" });
  expect(called).toBe(false);
});

test("already migrated users authenticate only against the linked Auth id", async () => {
  const result = await authenticateOrMigrateLegacyUser(input({
    linkedAuthUserId: "auth-linked",
    legacyAuthDisabledAt: "2026-07-22T00:00:00Z",
    legacyPasswordValid: false,
    authority: authority({ signIn: async () => ({ status: "authenticated", userId: "auth-linked" }) }),
  }));

  expect(result).toEqual({ status: "authenticated", authUserId: "auth-linked" });
});

test("duplicate Auth email is not linked without matching Auth password", async () => {
  let linked = false;
  const result = await authenticateOrMigrateLegacyUser(input({
    authority: authority({ findByEmail: async () => ({ status: "found", userId: "auth-other" }) }),
    bridgeStore: { linkAuthIdentity: async () => (linked = true) },
  }));

  expect(result).toEqual({ status: "conflict" });
  expect(linked).toBe(false);
});

test("Supabase outage fails closed without creating or linking", async () => {
  let created = false;
  let linked = false;
  const result = await authenticateOrMigrateLegacyUser(input({
    authority: authority({
      signIn: async () => ({ status: "unavailable" }),
      createLegacyIdentity: async () => {
        created = true;
        return { status: "created", userId: "unexpected" };
      },
    }),
    bridgeStore: { linkAuthIdentity: async () => (linked = true) },
  }));

  expect(result).toEqual({ status: "unavailable" });
  expect(created).toBe(false);
  expect(linked).toBe(false);
});

test("retry after Auth creation can complete the idempotent link", async () => {
  const result = await authenticateOrMigrateLegacyUser(input({
    authority: authority({ signIn: async () => ({ status: "authenticated", userId: "auth-orphan" }) }),
  }));

  expect(result).toEqual({ status: "migrated", authUserId: "auth-orphan" });
});

test("partial link failure stays retryable and never reports success", async () => {
  const result = await authenticateOrMigrateLegacyUser(input({
    bridgeStore: { linkAuthIdentity: async () => { throw new Error("database unavailable"); } },
  }));

  expect(result).toEqual({ status: "unavailable" });
});

test("linked identity mismatch fails closed", async () => {
  const result = await authenticateOrMigrateLegacyUser(input({
    linkedAuthUserId: "auth-linked",
    legacyAuthDisabledAt: "2026-07-22T00:00:00Z",
    authority: authority({ signIn: async () => ({ status: "authenticated", userId: "auth-other" }) }),
  }));

  expect(result).toEqual({ status: "conflict" });
});

test("Auth bridge migration is additive, normalized and server-only", () => {
  const migration = fs.readFileSync(
    path.join(
      process.cwd(),
      "supabase",
      "migrations",
      "20260722080817_existing_user_auth_bridge.sql",
    ),
    "utf8",
  );

  expect(migration).toContain("add column if not exists auth_user_id uuid references auth.users(id) on delete set null");
  expect(migration).toContain("alter column password_hash drop not null");
  expect(migration).toContain("users_email_normalized_uidx");
  expect(migration).toContain("on public.users (lower(email))");
  expect(migration).toContain("atlas_link_auth_identity");
  expect(migration).toContain("password_hash = null");
  expect(migration).toContain("atlas_auth_deletion_queue");
  expect(migration).toContain("alter table public.atlas_auth_deletion_queue enable row level security");
  expect(migration).toMatch(/revoke execute[\s\S]*from public, anon, authenticated/i);
  expect(migration).toMatch(/grant execute[\s\S]*to service_role/i);
});

test("account deletion is bound to the authenticated user and queues Auth cleanup", () => {
  const route = fs.readFileSync(
    path.join(process.cwd(), "app", "api", "account", "delete", "route.ts"),
    "utf8",
  );

  expect(route).toContain("const user = await currentUser()");
  expect(route).toContain("store.deleteAccount(user)");
  expect(route).toContain("deleteAuthIdentity(user.authUserId)");
  expect(route).not.toMatch(/body\.(userId|user_id|email)/);
});
