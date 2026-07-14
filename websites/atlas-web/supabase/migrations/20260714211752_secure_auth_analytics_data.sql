-- Atlas auth + analytics hardening.
--
-- Forward-only, non-destructive migration. Existing rows are preserved.
-- Rollback notes:
--   * Drop only the indexes/functions/views created here if rollback is needed.
--   * Added columns may remain nullable/defaulted; dropping them would discard
--     newly collected data and is intentionally not part of an automatic rollback.
--   * To restore the old (unsafe) rate-limit ACL, EXECUTE would have to be
--     granted back to PUBLIC/anon/authenticated. Do not do that in production.

create table if not exists public.analytics_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  user_id uuid,
  anonymous_id text,
  event_name text not null,
  source text,
  app_version text,
  platform text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.analytics_identities (
  id uuid primary key default gen_random_uuid(),
  identity_key text not null unique,
  user_id uuid references public.users(id),
  anonymous_id text,
  installation_id text,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  days_active integer not null default 1,
  sessions_count integer not null default 0,
  installed_at timestamptz,
  opened_at timestamptz,
  login_success_at timestamptz,
  repo_connected_at timestamptz,
  first_context_at timestamptz,
  cursor_connected_at timestamptz,
  claude_connected_at timestamptz,
  codex_connected_at timestamptz,
  cursor_used_count integer not null default 0,
  claude_used_count integer not null default 0,
  codex_used_count integer not null default 0,
  tool_calls_count integer not null default 0,
  context_injections_count integer not null default 0,
  repositories_count integer not null default 0,
  install_to_open_sec integer,
  open_to_login_sec integer,
  login_to_repo_sec integer,
  repo_to_first_context_sec integer,
  total_ttfv_sec integer,
  ttfv_computed_at timestamptz,
  updated_at timestamptz not null default now()
);

-- Reconcile the account schema with the Paddle fields used by the production
-- server. Preserve the legacy stripe_customer_id column if it exists.
alter table public.users
  add column if not exists paddle_customer_id text,
  add column if not exists paddle_subscription_id text;

alter table public.analytics_events
  add column if not exists session_id text,
  add column if not exists environment text not null default 'unknown',
  add column if not exists route text,
  add column if not exists build_commit text,
  add column if not exists event_version integer not null default 1,
  add column if not exists deduplication_key text,
  add column if not exists is_internal boolean not null default false;

alter table public.analytics_identities
  add column if not exists environment text not null default 'unknown',
  add column if not exists is_internal boolean not null default false;

alter table public.analytics_events enable row level security;
alter table public.analytics_identities enable row level security;
alter table public.users enable row level security;
alter table public.audit enable row level security;
alter table public.reset_tokens enable row level security;
alter table public.waitlist enable row level security;
alter table public.rate_limits enable row level security;

-- This application uses the Data API only from trusted server routes with the
-- service-role key. Browser roles intentionally receive no table privileges and
-- no RLS policies; they cannot read existing analytics rows or forge user_id.
revoke all on table public.analytics_events from public, anon, authenticated;
revoke all on table public.analytics_identities from public, anon, authenticated;
grant select, insert, update on table public.analytics_events to service_role;
grant select, insert, update on table public.analytics_identities to service_role;
revoke all on table public.users, public.audit, public.reset_tokens,
  public.waitlist, public.rate_limits from public, anon, authenticated;
grant select, insert, update, delete on table public.users, public.audit,
  public.reset_tokens, public.waitlist, public.rate_limits to service_role;

create unique index if not exists analytics_events_deduplication_key_uidx
  on public.analytics_events (deduplication_key);
create index if not exists analytics_events_environment_created_at_idx
  on public.analytics_events (environment, created_at desc);
create index if not exists analytics_events_environment_event_created_at_idx
  on public.analytics_events (environment, event_name, created_at desc);
create index if not exists analytics_events_session_created_at_idx
  on public.analytics_events (session_id, created_at desc)
  where session_id is not null;
create index if not exists analytics_events_route_created_at_idx
  on public.analytics_events (route, created_at desc)
  where route is not null;

-- Existing server-only rate limiting must not be callable with a publishable
-- key. The website invokes it only with service_role from _lib/ratelimit.ts.
revoke execute on function public.atlas_rate_limit_hit(text, integer, integer)
  from public, anon, authenticated;
grant execute on function public.atlas_rate_limit_hit(text, integer, integer)
  to service_role;

-- Ensure future objects are opt-in to the Data API. Explicit grants in reviewed
-- migrations remain possible and RLS is still required separately.
alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated;

create or replace function public.atlas_analytics_summary(
  p_since timestamptz,
  p_environment text default null,
  p_build_commit text default null,
  p_include_internal boolean default false
) returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  with filtered as (
    select *
    from public.analytics_events
    where created_at >= p_since
      and (p_environment is null or environment = p_environment)
      and (p_build_commit is null or build_commit = p_build_commit)
      and (p_include_internal or not is_internal)
  ), identities as (
    -- Prefer the stable anonymous installation/browser identity so the same
    -- visitor is not double-counted when a user signs in mid-session.
    select coalesce(anonymous_id, user_id::text) as identity,
           count(distinct created_at::date) as active_days
    from filtered
    where coalesce(anonymous_id, user_id::text) is not null
    group by coalesce(anonymous_id, user_id::text)
  ), top_routes as (
    select route, count(*) as views
    from filtered
    where event_name = 'page_view' and route is not null
    group by route
    order by views desc, route
    limit 10
  )
  select jsonb_build_object(
    'since', p_since,
    'timezone', 'UTC',
    'environment', p_environment,
    'build_commit', p_build_commit,
    'include_internal', p_include_internal,
    'unique_visitors', count(distinct coalesce(anonymous_id, user_id::text))
      filter (where event_name in ('site_visit', 'page_view')),
    'sessions', count(distinct session_id) filter (where session_id is not null),
    'page_views', count(*) filter (where event_name = 'page_view'),
    'downloads_attempted', count(*) filter (where event_name in ('download_clicked', 'installer_download_started')),
    'downloads_unavailable', count(*) filter (where event_name = 'download_unavailable_seen'),
    'successful_installs', count(*) filter (where event_name = 'desktop_installed'),
    'first_launches', count(*) filter (where event_name = 'desktop_launched'),
    'scans_completed', count(*) filter (where event_name = 'scan_completed'),
    'ask_completed', count(*) filter (where event_name = 'ask_completed'),
    'agents_connected', count(*) filter (where event_name = 'agent_connected'),
    'signup_success', count(*) filter (where event_name = 'signup_success'),
    'signup_failed', count(*) filter (where event_name = 'signup_failed'),
    'active_users', (select count(*) from identities),
    'returning_users', (select count(*) from identities where active_days >= 2),
    'top_routes', coalesce((select jsonb_agg(jsonb_build_object('route', route, 'views', views)) from top_routes), '[]'::jsonb)
  )
  from filtered;
$$;

revoke execute on function public.atlas_analytics_summary(timestamptz, text, text, boolean)
  from public, anon, authenticated;
grant execute on function public.atlas_analytics_summary(timestamptz, text, text, boolean)
  to service_role;

comment on table public.analytics_events is
  'Privacy-filtered Atlas product events. No source code, repository paths, raw prompts, tokens, or secrets.';
comment on column public.analytics_events.deduplication_key is
  'Server-hashed idempotency key; unique when present.';
comment on function public.atlas_analytics_summary(timestamptz, text, text, boolean) is
  'Server-only aggregate metrics for the authorized Atlas admin dashboard.';
