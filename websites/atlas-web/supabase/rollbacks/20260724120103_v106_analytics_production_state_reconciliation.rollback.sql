-- Run only after rolling back every sender that references these fields.
-- This removes only objects introduced by the production-state reconciliation.
-- It does not touch rows, grants, RLS, accounts, Auth, or migration history.

drop index if exists public.analytics_events_event_created_at_idx;
drop index if exists public.analytics_events_installation_created_at_idx;

alter table public.analytics_events
  drop column if exists duration_elapsed_ms,
  drop column if exists duration_active_ms,
  drop column if exists installation_id;

