-- Atlas v1.0.5 entitlement and dormant billing foundation.
-- REVIEW ONLY: validate on a disposable Supabase branch before production.
-- All mutations are service-role-only; browser clients never choose a plan,
-- customer, subscription, usage counter, or provider event identity.

create table if not exists public.atlas_entitlements (
  user_id uuid primary key references public.users(id) on delete cascade,
  plan text not null default 'free' check (plan in ('free','trialing','active','past_due','paused','cancel_scheduled','canceled','expired','unknown')),
  provider text not null default 'disabled' check (provider in ('disabled','paddle')),
  provider_customer_id text,
  provider_subscription_id text,
  period_ends_at timestamptz,
  source text not null default 'system' check (source in ('system','webhook','reconciliation','admin')),
  revision bigint not null default 0 check (revision >= 0),
  updated_at timestamptz not null default now(),
  last_synced_at timestamptz
);

create unique index if not exists atlas_entitlements_provider_subscription_uidx
  on public.atlas_entitlements(provider, provider_subscription_id)
  where provider_subscription_id is not null;

create table if not exists public.atlas_usage_windows (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete cascade,
  installation_id text,
  identity_key text generated always as (coalesce(user_id::text, installation_id)) stored,
  feature text not null check (feature in ('impact_advanced','mcp_clients','active_repository')),
  window_started_at timestamptz not null,
  window_ends_at timestamptz not null,
  used integer not null default 0 check (used >= 0),
  updated_at timestamptz not null default now(),
  check (window_ends_at > window_started_at),
  check (user_id is not null or installation_id is not null)
);
create unique index if not exists atlas_usage_windows_identity_feature_window_uidx
  on public.atlas_usage_windows(identity_key, feature, window_started_at);

create table if not exists public.atlas_billing_events (
  provider text not null check (provider in ('paddle')),
  provider_event_id text not null,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  outcome text not null default 'received' check (outcome in ('received','applied','ignored','failed')),
  primary key (provider, provider_event_id)
);

-- Existing accounts begin at Free. This does not grant a paid entitlement and
-- deliberately does not infer one from the legacy users.plan field.
insert into public.atlas_entitlements(user_id, plan, provider, source, updated_at)
select id, 'free', 'disabled', 'system', now() from public.users
on conflict (user_id) do nothing;

alter table public.atlas_entitlements enable row level security;
alter table public.atlas_usage_windows enable row level security;
alter table public.atlas_billing_events enable row level security;
revoke all on table public.atlas_entitlements, public.atlas_usage_windows, public.atlas_billing_events from public, anon, authenticated;
grant select, insert, update, delete on table public.atlas_entitlements, public.atlas_usage_windows, public.atlas_billing_events to service_role;

-- Atomic, service-role-only metering. Callers supply an already authenticated
-- server-derived account/installation identity; no browser role may execute it.
create or replace function public.atlas_consume_usage(
  p_user_id uuid,
  p_installation_id text,
  p_feature text,
  p_window_started_at timestamptz,
  p_window_ends_at timestamptz,
  p_limit integer
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare current_used integer;
begin
  if p_limit < 1 or p_feature not in ('impact_advanced','mcp_clients','active_repository') then
    raise exception 'invalid entitlement usage request';
  end if;
  insert into public.atlas_usage_windows(user_id, installation_id, feature, window_started_at, window_ends_at, used)
  values (p_user_id, nullif(p_installation_id, ''), p_feature, p_window_started_at, p_window_ends_at, 0)
  on conflict (identity_key, feature, window_started_at) do nothing;
  select used into current_used from public.atlas_usage_windows
    where identity_key = coalesce(p_user_id::text, nullif(p_installation_id, ''))
      and feature = p_feature and window_started_at = p_window_started_at
    for update;
  if current_used >= p_limit then
    return jsonb_build_object('allowed', false, 'used', current_used, 'limit', p_limit, 'remaining', 0, 'reset_at', p_window_ends_at);
  end if;
  update public.atlas_usage_windows set used = current_used + 1, updated_at = now()
    where identity_key = coalesce(p_user_id::text, nullif(p_installation_id, ''))
      and feature = p_feature and window_started_at = p_window_started_at;
  return jsonb_build_object('allowed', true, 'used', current_used + 1, 'limit', p_limit, 'remaining', p_limit - current_used - 1, 'reset_at', p_window_ends_at);
end;
$$;

revoke execute on function public.atlas_consume_usage(uuid, text, text, timestamptz, timestamptz, integer) from public, anon, authenticated;
grant execute on function public.atlas_consume_usage(uuid, text, text, timestamptz, timestamptz, integer) to service_role;
