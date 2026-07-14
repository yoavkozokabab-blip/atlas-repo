-- Privacy-preserving website analytics and existing RPC hardening.

create table if not exists public.analytics_events (
  id         uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  user_id    uuid references public.users(id) on delete set null,
  anonymous_id text,
  event_name text not null,
  source     text,
  app_version text,
  platform   text,
  metadata   jsonb not null default '{}'::jsonb
);
create index if not exists analytics_events_created_at_idx on public.analytics_events (created_at desc);
create index if not exists analytics_events_event_name_idx on public.analytics_events (event_name, created_at desc);

alter table public.analytics_events enable row level security;
grant select, insert on public.analytics_events to service_role;

alter function public.atlas_rate_limit_hit(text, integer, integer) set search_path = '';
revoke execute on function public.atlas_rate_limit_hit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.atlas_rate_limit_hit(text, integer, integer) to service_role;
