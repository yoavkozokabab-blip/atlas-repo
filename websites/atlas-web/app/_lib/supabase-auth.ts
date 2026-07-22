import "server-only";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { IdentityCreateResult, IdentityLookupResult, PasswordAuthority } from "./auth-bridge";

function serverClient(): SupabaseClient {
  const url = (process.env.SUPABASE_URL || "").trim();
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!url || !key) throw new Error("Supabase Auth server configuration is unavailable");
  return createClient(url, key, {
    auth: {
      autoRefreshToken: false,
      detectSessionInUrl: false,
      persistSession: false,
    },
  });
}

async function findAuthUserByEmail(client: SupabaseClient, email: string): Promise<IdentityLookupResult> {
  const normalized = email.trim().toLowerCase();
  for (let page = 1; page <= 100; page += 1) {
    const { data, error } = await client.auth.admin.listUsers({ page, perPage: 1000 });
    if (error) return { status: "unavailable" };
    const match = data.users.find((user) => (user.email || "").trim().toLowerCase() === normalized);
    if (match) return { status: "found", userId: match.id };
    if (data.users.length < 1000) return { status: "missing" };
  }
  return { status: "unavailable" };
}

export const supabasePasswordAuthority: PasswordAuthority = {
  signIn: async (email, password) => {
    try {
      const { data, error } = await serverClient().auth.signInWithPassword({ email, password });
      if (error || !data.user) {
        const status = Number(error?.status || 0);
        return status >= 500 || status === 429 ? { status: "unavailable" } : { status: "invalid" };
      }
      return { status: "authenticated", userId: data.user.id };
    } catch {
      return { status: "unavailable" };
    }
  },
  findByEmail: async (email) => {
    try {
      return await findAuthUserByEmail(serverClient(), email);
    } catch {
      return { status: "unavailable" };
    }
  },
  createLegacyIdentity: async (email, password) => {
    try {
      const client = serverClient();
      const { data, error } = await client.auth.admin.createUser({
        email,
        password,
        email_confirm: true,
        user_metadata: { atlas_migration: "legacy_password_verified" },
      });
      if (!error && data.user) return { status: "created", userId: data.user.id };
      const status = Number(error?.status || 0);
      if (status === 409 || status === 422) {
        const existing = await findAuthUserByEmail(client, email);
        return existing.status === "found"
          ? { status: "exists", userId: existing.userId }
          : existing.status === "unavailable"
            ? { status: "unavailable" }
            : { status: "exists" };
      }
      return { status: "unavailable" };
    } catch {
      return { status: "unavailable" };
    }
  },
};

export async function createNewAuthIdentity(
  email: string,
  password: string,
): Promise<IdentityCreateResult> {
  try {
    const client = serverClient();
    const { data, error } = await client.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
      user_metadata: { atlas_registration: "server_verified" },
    });
    if (!error && data.user) return { status: "created", userId: data.user.id };
    const status = Number(error?.status || 0);
    return status === 409 || status === 422 ? { status: "exists" } : { status: "unavailable" };
  } catch {
    return { status: "unavailable" };
  }
}

export async function deleteAuthIdentity(userId: string): Promise<boolean> {
  try {
    const { error } = await serverClient().auth.admin.deleteUser(userId);
    return !error;
  } catch {
    return false;
  }
}
