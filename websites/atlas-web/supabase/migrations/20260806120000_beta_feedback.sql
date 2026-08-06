-- Atlas beta feedback intake (v1.0.6-beta.1).
--
-- Additive only. Does not alter accounts, Auth, sessions, analytics, RLS on
-- existing tables, grants, or any existing row.
--
-- Before this table existed the desktop feedback form told the user their
-- report had been saved while writing it only to a local JSONL file on their
-- own machine, so nothing ever reached the product owner. The desktop now
-- posts here, and the UI states truthfully whether delivery succeeded.
--
-- Privacy contract enforced by app/api/feedback/route.ts and the desktop's
-- install_support._redact_support_text: no source code, file paths,
-- repository names, prompt text, or credentials. The reporter's email is
-- optional and supplied deliberately by the user so they can be answered.

create table if not exists public.beta_feedback (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  feedback_id     text not null unique,
  category        text not null,
  message         text not null,
  reply_email     text,
  page            text,
  app_version     text,
  build_commit    text,
  installation_id text,
  environment     text not null default 'production',
  diagnostics     jsonb not null default '{}'::jsonb
);

create index if not exists beta_feedback_created_at_idx
  on public.beta_feedback (created_at desc);

-- No public policies: RLS on, and only the service role (which bypasses RLS)
-- reaches this table, exactly like public.rate_limits.
alter table public.beta_feedback enable row level security;

comment on table public.beta_feedback is
  'Beta feedback submitted from the Atlas desktop app. Redacted client-side and server-side; never contains source code, file paths, repository names or prompts.';
comment on column public.beta_feedback.feedback_id is
  'Client-generated id, unique so a desktop retry cannot create a duplicate row.';
comment on column public.beta_feedback.reply_email is
  'Optional, user-supplied so the owner can reply. Never harvested from the machine.';
comment on column public.beta_feedback.installation_id is
  'Random per-installation identifier; never a device fingerprint or repository identifier.';
