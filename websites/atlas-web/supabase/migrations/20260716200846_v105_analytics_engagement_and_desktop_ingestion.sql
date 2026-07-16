-- Atlas v1.0.5 analytics engagement + desktop ingestion.
-- REVIEW ONLY: apply first to a disposable Supabase branch, never directly to
-- atlas-prod. Browser roles retain zero access to raw analytics rows.

alter table public.analytics_events
  add column if not exists installation_id text,
  add column if not exists duration_active_ms bigint,
  add column if not exists duration_elapsed_ms bigint;

create index if not exists analytics_events_installation_created_at_idx
  on public.analytics_events (installation_id, created_at desc)
  where installation_id is not null;
create index if not exists analytics_events_event_created_at_idx
  on public.analytics_events (event_name, created_at desc);

-- Defense in depth: only server-side service-role routes write or read raw
-- data. RLS remains enabled and there are intentionally no browser policies.
alter table public.analytics_events enable row level security;
revoke all on table public.analytics_events from public, anon, authenticated;
grant select, insert, update, delete on table public.analytics_events to service_role;

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
    select * from public.analytics_events
    where created_at >= p_since
      and (p_environment is null or environment = p_environment)
      and (p_build_commit is null or build_commit = p_build_commit)
      and (p_include_internal or not is_internal)
  ), identities as (
    select coalesce(installation_id, anonymous_id, user_id::text) as identity,
           count(distinct created_at::date) as active_days
    from filtered
    where coalesce(installation_id, anonymous_id, user_id::text) is not null
    group by coalesce(installation_id, anonymous_id, user_id::text)
  ), top_routes as (
    select route, count(*) as views
    from filtered where event_name = 'page_view' and route is not null
    group by route order by views desc, route limit 20
  )
  select jsonb_build_object(
    'since', p_since, 'timezone', 'UTC', 'environment', p_environment,
    'build_commit', p_build_commit, 'include_internal', p_include_internal,
    'unique_visitors', count(distinct coalesce(anonymous_id, user_id::text)) filter (where source = 'website'),
    'sessions', count(distinct session_id) filter (where session_id is not null),
    'page_views', count(*) filter (where event_name = 'page_view'),
    'downloads_attempted', count(*) filter (where event_name = 'download_clicked'),
    'installer_download_responses', count(*) filter (where event_name = 'installer_download_response_started'),
    'downloads_unavailable', count(*) filter (where event_name = 'download_unavailable_seen'),
    'successful_installs', count(distinct installation_id) filter (where event_name = 'app_first_run'),
    'first_launches', count(*) filter (where event_name = 'app_launch'),
    'active_installations', count(distinct installation_id) filter (where event_name = 'app_launch'),
    'scans_completed', count(*) filter (where event_name = 'scan_completed'),
    'ask_completed', count(*) filter (where event_name = 'ask_completed'),
    'agents_connected', count(*) filter (where event_name = 'mcp_connected'),
    'signup_success', count(*) filter (where event_name in ('signup_success', 'account_signup_completed')),
    'login_success', count(*) filter (where event_name in ('login_success', 'account_login_completed')),
    'active_users', (select count(*) from identities),
    'returning_users', (select count(*) from identities where active_days >= 2),
    'average_active_time_ms', coalesce(avg(duration_active_ms) filter (where duration_active_ms is not null), 0),
    'average_session_duration_ms', coalesce(avg(duration_elapsed_ms) filter (where duration_elapsed_ms is not null), 0),
    'top_routes', coalesce((select jsonb_agg(jsonb_build_object('route', route, 'views', views)) from top_routes), '[]'::jsonb)
  ) from filtered;
$$;

-- Retention is operationally invoked by a service-role job after the approved
-- retention window. It has no public RPC surface and never deletes accounts.
create or replace function public.atlas_purge_analytics_events(p_before timestamptz)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare removed bigint;
begin
  delete from public.analytics_events where created_at < p_before;
  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke execute on function public.atlas_analytics_summary(timestamptz, text, text, boolean)
  from public, anon, authenticated;
grant execute on function public.atlas_analytics_summary(timestamptz, text, text, boolean)
  to service_role;
revoke execute on function public.atlas_purge_analytics_events(timestamptz)
  from public, anon, authenticated;
grant execute on function public.atlas_purge_analytics_events(timestamptz)
  to service_role;

comment on column public.analytics_events.installation_id is
  'Random local installation identifier. Never a repository path, user email, or device fingerprint.';
comment on column public.analytics_events.duration_active_ms is
  'Approximate active engagement duration, not open-tab duration.';
comment on function public.atlas_purge_analytics_events(timestamptz) is
  'Service-role-only retention operation. Review the cutoff before running.';
