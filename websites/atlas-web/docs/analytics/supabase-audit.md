# Atlas Supabase and production-data audit

Snapshot: 2026-07-15 UTC. Discovery was read-only through the connected Supabase project and public HTTP probes. Secret values were not read into this report.

## Project and environment identity

The connected intended project is `atlas-prod`, reference `wggjguqcxmskhjznexum`, in `us-east-2`, status `ACTIVE_HEALTHY`, Postgres 17 (`17.6.1.127`), URL `https://wggjguqcxmskhjznexum.supabase.co`. A second connected project, `atlas-waitlist` (`lkbpwhxhvxgawzzxkgjy`, `eu-west-1`), is inactive and is not the production account store.

Public probes found two materially different deployments:

- The legacy Vercel project reported healthy persistence against `wggjguqcxmskhjznexum` before consolidation. Its stale installer redirect was identified without following or downloading the asset.
- The requested production domain `atlas-repo-wu76.vercel.app` reports HTTP 503 and resolves `SUPABASE_URL` to unconnected project reference `qfwmfllcqbngrowzbfpc`.

Therefore the requested production website is not pointing to the connected intended project, and installer suspension is inconsistent across live Atlas aliases. Vercel Preview could not be inventoried because the locally available Vercel credential is invalid. No environment values were printed or changed.

| Variable | Local working copy | Vercel Preview | Requested Production | Desktop runtime |
|---|---|---|---|---|
| `SUPABASE_URL` | example only, unset | unknown | present; wrong project ref | not used |
| `SUPABASE_SERVICE_ROLE_KEY` | example only, unset | unknown | present | not used |
| `NEXT_PUBLIC_SUPABASE_URL` | absent / unused | unknown | not required by code | not used |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | absent / unused | unknown | health endpoint reports an anon key present | not used |
| `SUPABASE_ANON_KEY` | example only; health display only | unknown | presence cannot be distinguished from public alias | not used |
| `AUTH_SECRET` | example only, unset | unknown | present | website-issued bearer token only |
| `ADMIN_EMAILS` | example only, unset | unknown | unknown | not used |
| Analytics-specific keys | none; canonical collector is same-origin | unknown | none required | current desktop analytics are local-only |
| `ATLAS_WEB_URL` | not a website variable | n/a | n/a | optional; defaults to the canonical `atlas-repo-wu76.vercel.app` site |
| `ATLAS_AUTH_MODE` | n/a | n/a | n/a | packaged default `website`, source default `local` |

The service-role key is referenced only from server modules (`store.ts` and `ratelimit.ts`). No browser bundle imports it and no `NEXT_PUBLIC_` service credential exists.

## Schema inventory

There are no public views, triggers, or RLS policies. All seven public tables have RLS enabled and browser roles have no SELECT or INSERT table privileges. This is an intentional server-only model, not anonymous direct-write analytics.

| Table | Purpose and important columns | Keys / indexes | Rows | Time handling | Website/admin use | Finding |
|---|---|---|---:|---|---|---|
| `users` | Custom accounts: UUID, email, name, scrypt hash, role/status, plan/status, trial/renewal, legacy Stripe customer, login time, downloads | PK `id`; unique email; lower-email index | 12 | `created_at=now()`, nullable `last_login_at` | Auth, account, billing, admin | Live DB lacks Paddle customer/subscription columns expected by code |
| `audit` | Admin/self-service action history and metadata | PK `id`; descending `at` index | 22 | `at=now()` | Admin reads last 100; account/admin writes | No pagination beyond hard limit |
| `reset_tokens` | Custom password-reset credentials | PK `token` | 0 | bigint expiry, no created time | Production reset flow is not implemented | Storing raw bearer reset tokens is unsafe for a future live flow |
| `waitlist` | Email signup capture with role/source | PK `id`; unique email; created-desc index | 0 | `created_at=now()` | Public write through server; admin export | Current public product flow does not rely on it |
| `rate_limits` | Server rate-limit buckets | PK `bucket`; expiry index | 1 | `expires_at` | Server RPC only | SECURITY DEFINER RPC is currently executable by browser roles |
| `analytics_events` | Legacy uncontracted events and metadata | PK; event/user/anonymous/time indexes | 1,002 | `created_at=now()` | No production-branch writer or admin reader before this change | 949 rows are repeated `api_me_success`; lacks environment/session/route/build/dedupe |
| `analytics_identities` | Legacy lifecycle rollups, install/open/login/repo/agent counters and timings | PK; unique identity; user/first/last indexes | 36 | first/last/updated defaults | No production-branch writer or admin reader | Duplicates raw-event responsibilities; provenance is not documented |

Current column inventory:

- `users`: `id`, `email`, `name`, `password_hash`, `role`, `status`, `plan`, `plan_status`, `trial_ends_at`, `renews_at`, `stripe_customer_id`, `created_at`, `last_login_at`, `downloads`.
- `audit`: `id`, `at`, `actor_id`, `actor_email`, `action`, `target_id`, `target_email`, `meta`.
- `reset_tokens`: `token`, `email`, `exp`.
- `waitlist`: `id`, `email`, `role`, `source`, `created_at`.
- `rate_limits`: `bucket`, `count`, `expires_at`.
- `analytics_events`: `id`, `created_at`, `user_id`, `anonymous_id`, `event_name`, `source`, `app_version`, `platform`, `metadata`. The migration adds `session_id`, `environment`, `route`, `build_commit`, `event_version`, `deduplication_key`, and `is_internal`.
- `analytics_identities`: `id`, `identity_key`, `user_id`, `anonymous_id`, `installation_id`, `first_seen`, `last_seen`, `days_active`, `sessions_count`, `installed_at`, `opened_at`, `login_success_at`, `repo_connected_at`, `first_context_at`, `cursor_connected_at`, `claude_connected_at`, `codex_connected_at`, `cursor_used_count`, `claude_used_count`, `codex_used_count`, `tool_calls_count`, `context_injections_count`, `repositories_count`, `install_to_open_sec`, `open_to_login_sec`, `login_to_repo_sec`, `repo_to_first_context_sec`, `total_ttfv_sec`, `ttfv_computed_at`, `updated_at`. The migration adds `environment` and `is_internal`.

`analytics_identities.user_id` references `users.id`. `analytics_events.user_id` has no declared foreign key. No subscriptions or contact/feedback table exists. Plan data is embedded in `users`; contact is a `mailto:` link only.

Index inventory: table primary keys; `users_email_key`, `users_email_idx`; `waitlist_email_key`, `waitlist_created_idx`; `audit_at_idx`; `rate_limits_expires_idx`; `analytics_events_created_at_idx`, `analytics_events_event_name_idx`, `analytics_events_user_id_idx`, `analytics_events_anonymous_id_idx`; and `analytics_identities_identity_key_key`, `analytics_identities_user_id_idx`, `analytics_identities_first_seen_idx`, `analytics_identities_last_seen_idx`. The only public function is SECURITY DEFINER `atlas_rate_limit_hit(text, integer, integer)`. It has a fixed `search_path=public`, but `anon` and `authenticated` can execute it. The security advisor reports both grants as warnings. The performance advisor reports five unused indexes (`audit_at_idx`, two analytics event indexes, and two analytics identity indexes); the dataset is too young/small to justify dropping them.

## RLS and access control

Every public table: RLS enabled, forced RLS disabled, no policies, and no `anon`/`authenticated` SELECT/INSERT privilege. Service routes use `service_role`, which bypasses RLS. This prevents a browser from reading rows or choosing another `user_id`; website analytics accepts an untrusted body only at a same-origin server route and derives the authenticated user on the server.

The versioned migration keeps the server-only model, explicitly revokes table privileges from browser roles, grants only `service_role`, revokes public execution of the rate-limit RPC, sets restrictive default privileges, adds deduplication and query indexes, and exposes an aggregate RPC only to `service_role`. The advisor's `RLS enabled, no policy` notices are informational under this design.

## Authentication

Atlas does not use Supabase Auth for its website accounts. It stores scrypt password hashes in `public.users` and issues custom seven-day HMAC tokens as an HTTP-only `SameSite=Lax`, Secure-in-production cookie or desktop Bearer token. Of 12 custom users, only one email matches the single Supabase Auth user; the two identity systems must not be treated as synchronized.

Strengths: stable production signing secret is mandatory; hash comparison is timing safe; unknown-user login performs a dummy KDF; suspended users are rejected; admin authorization is server-side; service credentials stay server-side.

Risks and corrections:

- Logout is stateless. Browser cookies are cleared but issued tokens cannot be revoked before expiry; desktop logout only discards the local token.
- No refresh token is issued for desktop; expiry requires login again. The cached desktop license can remain accepted for up to seven offline days after the last successful check.
- Supabase Auth email verification, redirect allowlists, CAPTCHA, MFA, and leaked-password protection do not protect the 12 custom accounts. The advisor still reports Supabase Auth leaked-password protection disabled for its one separate user.
- Password reset had no delivery or consumption flow and logged a raw local reset link. Production now returns an honest unavailable response and does not create or log a reset token.
- Auth/account/admin JSON now uses private, no-store caching and converts database outages into generic 503 responses rather than cacheable or raw failures.
- Duplicate signup is checked before insert but remains susceptible to a concurrent race; the database unique constraint preserves integrity, while the losing request may surface as unavailable instead of duplicate.
- Account deletion and billing/admin multi-step writes are not transactional.
- The requested production deployment cannot currently register, restore sessions, or authorize admins because its database fetch fails.

The desktop does not contain a Supabase key. In packaged website-auth mode it calls `/api/auth/desktop/login`, `/register`, `/me`, and `/logout`. Guest/local mode uses local state and the legacy local account service. Desktop product analytics remain local JSONL and do not populate Supabase. The desktop authority default is the healthy `atlas-repo-chi` deployment, not the requested `atlas-repo-wu76` deployment.

## Event quality

Existing distribution: 949 `api_me_success`, 41 `site_visit`, 6 `desktop_opened`, 2 desktop-login-started, 2 desktop-login-success, and 2 manual test rows. Four rows have no user or anonymous identity. No suspicious password/token/path pattern was found in the existing metadata scan, but only five legacy metadata keys occur and no event-contract enforcement exists in the deployed system.

The repeated `api_me_success` rows are 94.7% of all events and represent only two user IDs. They make current activity and conversion reporting untrustworthy. Legacy rows have no environment, session, route, build commit, or deduplication key; the migration deliberately labels them `environment='unknown'` rather than pretending they are production.

## Reliability, logs, and migration state

There are no Edge Functions and no real-time analytics subscription. The website uses raw server-side PostgREST fetches rather than a persistent client pool. Admin lists have fixed limits; the new aggregate RPC performs database-side counts over indexed environment/time/event fields.

Connected-project API logs contained no recent entries. Postgres logs showed missing `supabase_migrations.schema_migrations` lookups caused by the audit tooling; the project has no recorded migrations despite manually existing schema. Auth logs showed a normal GoTrue restart plus deprecation warnings, not application login activity.

Migration `20260714211752_secure_auth_analytics_data.sql` was created with rollback notes and preserved all rows. It was not applied because the requested production deployment points to a different project and a migration against `atlas-prod` would not repair that deployment. No production data was updated, deleted, or relabeled.

## Current decision

Analytics and Supabase are both NO-GO for production reporting until Vercel project identity is reconciled, the alternate live installer redirect is suspended, the migration is reviewed/applied to the actual production project, canonical website changes are deployed, Preview separation is proven, dedicated QA events are queried once, and desktop events exist for every downstream funnel claim.
