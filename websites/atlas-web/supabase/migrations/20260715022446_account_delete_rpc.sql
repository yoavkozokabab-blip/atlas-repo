-- Atomic account deletion for the production website.
--
-- Forward-only and non-destructive to unrelated data. The function is invoked
-- only from trusted server routes with the Supabase service-role key.

create or replace function public.atlas_delete_account(
  p_user_id uuid,
  p_user_email text
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  normalized_email text := lower(trim(p_user_email));
begin
  if p_user_id is null or normalized_email = '' then
    raise exception 'account delete requires user id and email'
      using errcode = '22023';
  end if;

  -- Preserve product analytics without retaining a direct account reference.
  update public.analytics_events
     set user_id = null
   where user_id = p_user_id;

  update public.analytics_identities
     set user_id = null,
         updated_at = now()
   where user_id = p_user_id;

  delete from public.reset_tokens
   where lower(email) = normalized_email;

  insert into public.audit (
    id,
    at,
    actor_id,
    actor_email,
    action,
    target_id,
    target_email,
    meta
  ) values (
    gen_random_uuid(),
    now(),
    p_user_id::text,
    normalized_email,
    'account_self_delete',
    p_user_id::text,
    normalized_email,
    jsonb_build_object('source', 'account_delete_rpc')
  );

  delete from public.users
   where id = p_user_id
     and lower(email) = normalized_email;

  if not found then
    raise exception 'account not found'
      using errcode = 'P0002';
  end if;
end;
$$;

revoke execute on function public.atlas_delete_account(uuid, text)
  from public, anon, authenticated;
grant execute on function public.atlas_delete_account(uuid, text)
  to service_role;

comment on function public.atlas_delete_account(uuid, text) is
  'Server-only atomic Atlas account deletion with audit entry and analytics anonymization.';
