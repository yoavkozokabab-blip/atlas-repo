-- Atlas v1.0.5 server-authoritative sessions. REVIEW ONLY: validate in a
-- disposable local Supabase environment before any production application.
-- Signed browser/desktop tokens carry only id/sub/exp; every authenticated
-- request verifies this record so logout, expiration, suspension and account
-- deletion fail closed.

create table if not exists public.atlas_sessions (
  id text primary key check (length(id) >= 32),
  user_id uuid not null references public.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  check (expires_at > created_at)
);

create index if not exists atlas_sessions_user_active_idx
  on public.atlas_sessions(user_id, expires_at)
  where revoked_at is null;

alter table public.atlas_sessions enable row level security;
revoke all on table public.atlas_sessions from public, anon, authenticated;
grant select, insert, update, delete on table public.atlas_sessions to service_role;
