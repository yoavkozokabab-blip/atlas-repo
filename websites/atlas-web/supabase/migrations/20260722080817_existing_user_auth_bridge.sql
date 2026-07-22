-- Staged legacy-account bridge to Supabase Auth.
--
-- This migration is additive. Existing scrypt hashes remain usable until a
-- successful trusted-server migration links the matching Auth identity. The
-- link RPC clears the legacy hash in the same database transaction.

alter table public.users
  add column if not exists auth_user_id uuid references auth.users(id) on delete set null,
  add column if not exists auth_migrated_at timestamptz,
  add column if not exists legacy_auth_disabled_at timestamptz,
  add column if not exists updated_at timestamptz not null default now();

alter table public.users alter column password_hash drop not null;

do $$
begin
  if exists (
    select 1
    from public.users
    group by lower(email)
    having count(*) > 1
  ) then
    raise exception 'cannot enforce normalized user email uniqueness: duplicates exist';
  end if;
end;
$$;

drop index if exists public.users_email_idx;
create unique index if not exists users_email_normalized_uidx
  on public.users (lower(email));
create unique index if not exists users_auth_user_id_uidx
  on public.users (auth_user_id)
  where auth_user_id is not null;

create table if not exists public.atlas_auth_deletion_queue (
  auth_user_id uuid primary key references auth.users(id) on delete cascade,
  requested_at timestamptz not null default now(),
  attempts integer not null default 0 check (attempts >= 0),
  last_attempt_at timestamptz
);

alter table public.atlas_auth_deletion_queue enable row level security;
revoke all on table public.atlas_auth_deletion_queue from public, anon, authenticated;
grant select, insert, update, delete on table public.atlas_auth_deletion_queue to service_role;

create or replace function public.atlas_queue_auth_identity_deletion()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if old.auth_user_id is not null then
    insert into public.atlas_auth_deletion_queue (auth_user_id, requested_at)
    values (old.auth_user_id, now())
    on conflict (auth_user_id) do update
      set requested_at = excluded.requested_at;
  end if;
  return old;
end;
$$;

drop trigger if exists atlas_users_queue_auth_deletion on public.users;
create trigger atlas_users_queue_auth_deletion
before delete on public.users
for each row execute function public.atlas_queue_auth_identity_deletion();

create or replace function public.atlas_link_auth_identity(
  p_user_id uuid,
  p_auth_user_id uuid
) returns boolean
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  linked_email text;
  auth_email text;
begin
  select lower(email) into linked_email
  from public.users
  where id = p_user_id
  for update;

  select lower(email) into auth_email
  from auth.users
  where id = p_auth_user_id;

  if linked_email is null or auth_email is null or linked_email <> auth_email then
    return false;
  end if;

  update public.users
  set auth_user_id = p_auth_user_id,
      auth_migrated_at = coalesce(auth_migrated_at, now()),
      legacy_auth_disabled_at = coalesce(legacy_auth_disabled_at, now()),
      password_hash = null,
      updated_at = now()
  where id = p_user_id
    and (auth_user_id is null or auth_user_id = p_auth_user_id);

  if not found then
    return false;
  end if;

  insert into public.audit (
    id, at, actor_id, actor_email, action, target_id, target_email, meta
  ) values (
    gen_random_uuid(), now(), p_user_id::text, linked_email,
    'legacy_auth_migrated', p_user_id::text, linked_email,
    jsonb_build_object('authority', 'supabase_auth')
  );
  return true;
end;
$$;

revoke execute on function public.atlas_link_auth_identity(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.atlas_link_auth_identity(uuid, uuid)
  to service_role;
revoke execute on function public.atlas_queue_auth_identity_deletion()
  from public, anon, authenticated;

comment on column public.users.auth_user_id is
  'Server-managed link to the authoritative Supabase Auth identity.';
comment on column public.users.legacy_auth_disabled_at is
  'When set, the legacy scrypt verifier must never authenticate this account.';
comment on function public.atlas_link_auth_identity(uuid, uuid) is
  'Service-role-only, email-matched, transactional completion of legacy Auth migration.';

-- Rollback procedure (manual; application rollback must happen first):
-- drop function if exists public.atlas_link_auth_identity(uuid, uuid);
-- drop trigger if exists atlas_users_queue_auth_deletion on public.users;
-- drop function if exists public.atlas_queue_auth_identity_deletion();
-- drop table if exists public.atlas_auth_deletion_queue;
-- drop index if exists public.users_auth_user_id_uidx;
-- drop index if exists public.users_email_normalized_uidx;
-- create index if not exists users_email_idx on public.users (lower(email));
-- alter table public.users alter column password_hash set not null;
-- alter table public.users
--   drop column if exists updated_at,
--   drop column if exists legacy_auth_disabled_at,
--   drop column if exists auth_migrated_at,
--   drop column if exists auth_user_id;
-- The NOT NULL rollback is valid only after every row has a restored legacy
-- hash; it must not be run after real users have completed migration.
