-- Launch funnel analytics (minimal, privacy-safe).
-- Operator note: this table may already exist in production; migration is idempotent.

create table if not exists public.analytics_events (
  id            uuid primary key default gen_random_uuid(),
  created_at    timestamptz not null default now(),
  user_id       uuid references public.users(id) on delete set null,
  anonymous_id  text,
  event_name    text not null,
  source        text not null default 'unknown',
  app_version   text,
  platform      text,
  metadata      jsonb not null default '{}'::jsonb
);

create index if not exists analytics_events_created_at_idx
  on public.analytics_events (created_at desc);

create index if not exists analytics_events_event_name_idx
  on public.analytics_events (event_name);

create index if not exists analytics_events_user_id_idx
  on public.analytics_events (user_id);
