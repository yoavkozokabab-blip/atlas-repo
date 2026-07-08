-- RC analytics: identity rollups, TTFV milestones, retention primitives.

create table if not exists public.analytics_identities (
  id                        uuid primary key default gen_random_uuid(),
  identity_key              text not null unique,
  user_id                   uuid references public.users(id) on delete set null,
  anonymous_id              text,
  installation_id           text,
  first_seen                timestamptz not null default now(),
  last_seen                 timestamptz not null default now(),
  days_active               integer not null default 1,
  sessions_count            integer not null default 0,
  installed_at              timestamptz,
  opened_at                 timestamptz,
  login_success_at          timestamptz,
  repo_connected_at         timestamptz,
  first_context_at          timestamptz,
  cursor_connected_at       timestamptz,
  claude_connected_at       timestamptz,
  codex_connected_at        timestamptz,
  cursor_used_count         integer not null default 0,
  claude_used_count         integer not null default 0,
  codex_used_count          integer not null default 0,
  tool_calls_count          integer not null default 0,
  context_injections_count  integer not null default 0,
  repositories_count        integer not null default 0,
  install_to_open_sec       integer,
  open_to_login_sec         integer,
  login_to_repo_sec         integer,
  repo_to_first_context_sec integer,
  total_ttfv_sec            integer,
  ttfv_computed_at          timestamptz,
  updated_at                timestamptz not null default now()
);

create index if not exists analytics_identities_first_seen_idx
  on public.analytics_identities (first_seen desc);

create index if not exists analytics_identities_last_seen_idx
  on public.analytics_identities (last_seen desc);

create index if not exists analytics_identities_user_id_idx
  on public.analytics_identities (user_id);
