-- Atlas v1.0.6 analytics-only production-state reconciliation.
--
-- This migration supersedes 20260722090000_v106_analytics_only for the
-- drifted atlas-prod history. It is based on the verified Gate 1 production
-- backup and must never be used to mark any older repository migration as
-- applied. It changes only public.analytics_events.

do $$
declare
  dedupe_definition text;
begin
  if to_regclass('public.analytics_events') is null then
    raise exception 'required table public.analytics_events is missing';
  end if;

  if not exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = 'analytics_events'
      and c.relrowsecurity
  ) then
    raise exception 'public.analytics_events must retain RLS before reconciliation';
  end if;

  if has_table_privilege('anon', 'public.analytics_events', 'select,insert,update,delete')
     or has_table_privilege('authenticated', 'public.analytics_events', 'select,insert,update,delete') then
    raise exception 'browser roles must not have analytics_events table privileges';
  end if;

  if to_regclass('public.analytics_events_deduplication_key_uidx') is null then
    raise exception 'required analytics deduplication index is missing';
  end if;

  select pg_get_indexdef(i.indexrelid)
    into dedupe_definition
  from pg_index i
  where i.indexrelid = to_regclass('public.analytics_events_deduplication_key_uidx')
    and i.indisunique;

  if dedupe_definition is null
     or regexp_replace(dedupe_definition, '\s+', ' ', 'g') <>
        'CREATE UNIQUE INDEX analytics_events_deduplication_key_uidx ON public.analytics_events USING btree (deduplication_key)' then
    raise exception 'analytics deduplication index does not match the verified production prerequisite';
  end if;
end
$$;

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

do $$
declare
  installation_index_definition text;
  event_index_definition text;
begin
  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'analytics_events'
      and (
        (column_name = 'installation_id' and data_type = 'text')
        or (column_name in ('duration_active_ms', 'duration_elapsed_ms') and data_type = 'bigint')
      )
      and is_nullable = 'YES'
      and column_default is null
  ) <> 3 then
    raise exception 'v1.0.6 analytics columns do not match the frozen sender contract';
  end if;

  select pg_get_indexdef(to_regclass('public.analytics_events_installation_created_at_idx'))
    into installation_index_definition;
  if installation_index_definition is null
     or regexp_replace(installation_index_definition, '\s+', ' ', 'g') <>
        'CREATE INDEX analytics_events_installation_created_at_idx ON public.analytics_events USING btree (installation_id, created_at DESC) WHERE (installation_id IS NOT NULL)' then
    raise exception 'installation analytics index does not match the reviewed definition';
  end if;

  select pg_get_indexdef(to_regclass('public.analytics_events_event_created_at_idx'))
    into event_index_definition;
  if event_index_definition is null
     or regexp_replace(event_index_definition, '\s+', ' ', 'g') <>
        'CREATE INDEX analytics_events_event_created_at_idx ON public.analytics_events USING btree (event_name, created_at DESC)' then
    raise exception 'event analytics index does not match the reviewed definition';
  end if;
end
$$;
