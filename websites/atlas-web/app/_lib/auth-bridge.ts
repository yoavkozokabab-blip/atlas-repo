export type PasswordSignInResult =
  | { status: "authenticated"; userId: string }
  | { status: "invalid" }
  | { status: "unavailable" };

export type IdentityLookupResult =
  | { status: "found"; userId: string }
  | { status: "missing" }
  | { status: "unavailable" };

export type IdentityCreateResult =
  | { status: "created"; userId: string }
  | { status: "exists"; userId?: string }
  | { status: "unavailable" };

export interface PasswordAuthority {
  signIn(email: string, password: string): Promise<PasswordSignInResult>;
  findByEmail(email: string): Promise<IdentityLookupResult>;
  createLegacyIdentity(email: string, password: string): Promise<IdentityCreateResult>;
}

export interface LegacyBridgeStore {
  linkAuthIdentity(userId: string, authUserId: string): Promise<boolean>;
}

export type LegacyBridgeResult =
  | { status: "migrated"; authUserId: string }
  | { status: "authenticated"; authUserId: string }
  | { status: "invalid" }
  | { status: "unavailable" }
  | { status: "conflict" };

export async function authenticateOrMigrateLegacyUser(input: {
  userId: string;
  email: string;
  password: string;
  legacyPasswordValid: boolean;
  linkedAuthUserId?: string | null;
  legacyAuthDisabledAt?: string | null;
  authority: PasswordAuthority;
  bridgeStore: LegacyBridgeStore;
}): Promise<LegacyBridgeResult> {
  const authority = input.authority;
  const email = input.email.trim().toLowerCase();
  if (input.linkedAuthUserId || input.legacyAuthDisabledAt) {
    if (!input.linkedAuthUserId) return { status: "conflict" };
    const signedIn = await authority.signIn(email, input.password);
    if (signedIn.status !== "authenticated") return signedIn;
    return signedIn.userId === input.linkedAuthUserId
      ? { status: "authenticated", authUserId: signedIn.userId }
      : { status: "conflict" };
  }

  if (!input.legacyPasswordValid) return { status: "invalid" };

  const existingSignIn = await authority.signIn(email, input.password);
  if (existingSignIn.status === "unavailable") return existingSignIn;
  let authUserId: string;
  if (existingSignIn.status === "authenticated") {
    authUserId = existingSignIn.userId;
  } else {
    const lookup = await authority.findByEmail(email);
    if (lookup.status === "unavailable") return lookup;
    // Never seize an existing Auth identity merely because its email matches a
    // verified legacy record. The password must authenticate both identities.
    if (lookup.status === "found") return { status: "conflict" };
    const created = await authority.createLegacyIdentity(email, input.password);
    if (created.status === "unavailable") return created;
    if (created.status === "exists") return { status: "conflict" };
    authUserId = created.userId;
  }

  try {
    const linked = await input.bridgeStore.linkAuthIdentity(input.userId, authUserId);
    return linked ? { status: "migrated", authUserId } : { status: "conflict" };
  } catch {
    // The Auth identity may already exist after a partial failure. A retry is
    // safe: sign-in succeeds, then the idempotent link RPC runs again.
    return { status: "unavailable" };
  }
}
