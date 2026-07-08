-- Analytics tables: RLS lockdown + service_role grants (required for PostgREST).
-- Without these GRANTs, inserts/selects return 42501 and the dashboard shows silent zeros.
-- Run after 0003_analytics_events.sql and 0004_analytics_identities.sql.

alter table if exists public.analytics_events enable row level security;
alter table if exists public.analytics_identities enable row level security;

grant select, insert, update, delete on
  public.analytics_events, public.analytics_identities
  to service_role;
