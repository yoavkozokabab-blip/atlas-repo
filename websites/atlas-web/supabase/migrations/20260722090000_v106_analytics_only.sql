-- Atlas v1.0.6 analytics-only additive migration.
--
-- Apply only after a restorable production backup has been captured. This file
-- intentionally does not alter accounts/Auth/session tables, RLS policies,
-- grants, functions, existing rows, or existing event data.

alter table public.analytics_events
  add column if not exists installation_id text,
  add column if not exists duration_active_ms bigint,
  add column if not exists duration_elapsed_ms bigint;

create index if not exists analytics_events_installation_created_at_idx
  on public.analytics_events (installation_id, created_at desc)
  where installation_id is not null;

create index if not exists analytics_events_event_created_at_idx
  on public.analytics_events (event_name, created_at desc);

comment on column public.analytics_events.installation_id is
  'Random per-Windows-user Atlas installation UUID; never a device fingerprint or repository identifier.';
comment on column public.analytics_events.duration_active_ms is
  'Bounded coarse active duration in milliseconds.';
comment on column public.analytics_events.duration_elapsed_ms is
  'Bounded coarse elapsed duration in milliseconds.';

-- Rollback is recorded in ../rollbacks/20260722090000_v106_analytics_only.rollback.sql.
