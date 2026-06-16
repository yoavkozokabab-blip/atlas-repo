-- Atlas website — initial schema (Supabase / Postgres).
-- Apply via: Supabase Dashboard → SQL Editor → paste & run,
--        or: supabase db push  (with the Supabase CLI linked to your project).
--
-- The website talks to these tables through PostgREST using the SERVICE ROLE key
-- (server-side only). RLS is ENABLED with no public policies, so the anon/public
-- keys cannot read or write — only the service role (which bypasses RLS) can.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- users — accounts (passwordHash is scrypt; never plaintext)
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id                 uuid primary key default gen_random_uuid(),
  email              text not null unique,
  name               text,
  password_hash      text not null,
  role               text not null default 'user',
  status             text not null default 'active',
  plan               text not null default 'free',
  plan_status        text not null default 'none',
  trial_ends_at      timestamptz,
  renews_at          timestamptz,
  stripe_customer_id text,
  created_at         timestamptz not null default now(),
  last_login_at      timestamptz,
  downloads          integer not null default 0
);
create index if not exists users_email_idx on public.users (lower(email));

-- ---------------------------------------------------------------------------
-- audit — admin + account action log
-- ---------------------------------------------------------------------------
create table if not exists public.audit (
  id           uuid primary key default gen_random_uuid(),
  at           timestamptz not null default now(),
  actor_id     text,
  actor_email  text,
  action       text not null,
  target_id    text,
  target_email text,
  meta         jsonb
);
create index if not exists audit_at_idx on public.audit (at desc);

-- ---------------------------------------------------------------------------
-- reset_tokens — password reset (short-lived)
-- ---------------------------------------------------------------------------
create table if not exists public.reset_tokens (
  token text primary key,
  email text not null,
  exp   bigint not null
);

-- ---------------------------------------------------------------------------
-- waitlist — beta signups (idempotent on email)
-- ---------------------------------------------------------------------------
create table if not exists public.waitlist (
  id         uuid primary key default gen_random_uuid(),
  email      text not null unique,
  role       text,
  source     text,
  created_at timestamptz not null default now()
);
create index if not exists waitlist_created_idx on public.waitlist (created_at desc);

-- ---------------------------------------------------------------------------
-- Lock down: enable RLS, add NO policies. Service role bypasses RLS; anon/public
-- keys get zero access. This is the intended posture for a server-only backend.
-- ---------------------------------------------------------------------------
alter table public.users        enable row level security;
alter table public.audit        enable row level security;
alter table public.reset_tokens enable row level security;
alter table public.waitlist     enable row level security;

-- ---------------------------------------------------------------------------
-- Grants: the server uses the SERVICE ROLE key. service_role has BYPASSRLS, but
-- Postgres still requires table-level privileges (RLS bypass and GRANTs are two
-- separate layers). Without these, every query returns 42501 "permission denied".
-- anon/authenticated are intentionally NOT granted, so RLS + no-policies keeps
-- them locked out. Idempotent — safe to re-run.
-- ---------------------------------------------------------------------------
grant usage on schema public to service_role;
grant select, insert, update, delete on
  public.users, public.audit, public.reset_tokens, public.waitlist
  to service_role;
