# Atlas account authority transition

## Current staged model

The bridge is disabled unless `ATLAS_SUPABASE_AUTH_BRIDGE=1`. Enabling it is
allowed only after the Auth bridge and `atlas_sessions` migrations are applied.
The desktop remains local-first and never receives a Supabase service-role key.

While the bridge is disabled, the legacy `public.users.password_hash` verifier
remains authoritative. While enabled:

- an already migrated user authenticates only through Supabase Auth;
- an unmigrated user may authenticate once with the existing scrypt hash;
- the trusted website server creates a Supabase Auth identity only when no Auth
  identity with that normalized email already exists;
- an existing Auth identity is linked only if the supplied password also signs
  in to that Auth identity;
- `atlas_link_auth_identity` verifies the email match in Postgres, links the
  identities, clears the legacy hash, disables legacy authentication, and writes
  a secret-free audit event in one transaction;
- a failed link is retryable because the legacy row remains authoritative until
  the RPC completes.

## Session authority

Supabase Auth is the target password and identity authority. During the staged
release, `atlas_sessions` is the application-session authority for both the
httpOnly website cookie and desktop bearer token. The HMAC is only a signed
transport envelope containing the application session id; every request must
match an unrevoked, unexpired server row. Logout and account deletion revoke the
row. `AtlasAccounts.exe` remains a local development fallback and is not needed
by packaged website-authority mode.

This transitional application-session layer may be removed after every active
client can use and refresh Supabase Auth sessions directly without putting a
service-role credential in a shipped binary.

## Conflict behavior

The bridge never links solely from caller-supplied email. If the legacy password
is valid but a different Auth password owns the same email, login returns the
same generic invalid-credentials response and performs no link. Recovery must
verify email ownership through Supabase Auth before an operator-approved link.

## Deployment order

1. Verify and record a restorable production backup.
2. Test the migration against representative legacy fixtures in an isolated
   Supabase environment.
3. Apply the Auth bridge migration and verify columns, indexes, RPC grants, RLS,
   row counts, and normalized-email uniqueness.
4. Deploy server code with the bridge flag still disabled.
5. Enable the bridge for synthetic accounts, verify audit and rollback behavior,
   then widen deliberately.
6. Move new registration and password recovery to Supabase Auth before declaring
   the legacy verifier retired.

## Rollback

Disable `ATLAS_SUPABASE_AUTH_BRIDGE` first. Unmigrated users immediately return
to legacy verification. Migrated users cannot use a cleared legacy hash; keep
the bridge code available during the rollback window or require verified Auth
recovery. Do not drop migration columns or the RPC while any account is marked
migrated. The commented SQL in the migration is destructive rollback guidance,
not an automatic down migration.
