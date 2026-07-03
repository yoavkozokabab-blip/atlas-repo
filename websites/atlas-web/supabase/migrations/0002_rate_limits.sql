-- Atlas website — shared, atomic rate limiting (Phase 186D).
-- Apply via: Supabase Dashboard → SQL Editor → paste & run,
--        or: supabase db push
--
-- Replaces the per-process in-memory limiter (useless on serverless, where each
-- instance has its own memory). _lib/ratelimit.ts calls atlas_rate_limit_hit()
-- through PostgREST with the SERVICE ROLE key. RLS stays enabled with no public
-- policies; only the service role (which bypasses RLS) can touch this.

-- Fixed-window counters keyed by "<key>:<window_start_epoch>".
create table if not exists public.rate_limits (
  bucket     text primary key,
  count      integer not null default 0,
  expires_at timestamptz not null
);
create index if not exists rate_limits_expires_idx on public.rate_limits (expires_at);

alter table public.rate_limits enable row level security;

-- Atomic increment-and-check. Returns TRUE when the request is UNDER the limit
-- (allow), FALSE when it should be throttled. The upsert is a single statement,
-- so concurrent invocations across serverless instances increment safely.
create or replace function public.atlas_rate_limit_hit(
  p_key text,
  p_window_seconds integer,
  p_max integer
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_window_start bigint;
  v_bucket text;
  v_count integer;
begin
  v_window_start := floor(extract(epoch from now()) / p_window_seconds)::bigint * p_window_seconds;
  v_bucket := p_key || ':' || v_window_start::text;

  insert into public.rate_limits (bucket, count, expires_at)
    values (v_bucket, 1, to_timestamp(v_window_start + p_window_seconds))
  on conflict (bucket)
    do update set count = public.rate_limits.count + 1
    returning count into v_count;

  -- Opportunistic cleanup so the table cannot grow unbounded.
  delete from public.rate_limits where expires_at < now() - interval '1 hour';

  return v_count <= p_max;
end;
$$;
