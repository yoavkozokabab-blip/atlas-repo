# Atlas v1.0.6 analytics Gate 2/3 evidence

Status: **NOT READY - STOPPED ON MIGRATION-HISTORY DRIFT**

Captured on 2026-07-24 from branch
`release/atlas-v1.0.6-analytics-rc` at preflight HEAD `a0af94bc`.

## Repository hygiene

- No path under `.atlas-private/` is tracked in the worktree or commit
  `a0af94bc`.
- The private runner is outside the worktree at
  `C:\J.A.R.V.I.S\.atlas-private\gate1_backup_runner.ps1`.
- Files changed since `f843538e` contain no credential-format matches.
- The phrase `access token` in the Gate 1 documentation is an operational
  warning, not a credential.
- No corrective commit was required.

## Reviewed v1.0.6 migration

Migration: `20260722090000_v106_analytics_only.sql`

The reviewed migration is additive and limited to:

- nullable `public.analytics_events.installation_id text`
- nullable `public.analytics_events.duration_active_ms bigint`
- nullable `public.analytics_events.duration_elapsed_ms bigint`
- partial index `analytics_events_installation_created_at_idx`
- index `analytics_events_event_created_at_idx`
- comments on the three new columns

It contains no account, user, authentication, session, password, executable,
RLS, policy, or grant changes.

## Gate 2 pre-migration evidence

Private sanitized evidence:

`C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate2-20260724T113743Z`

The existing Gate 1 archive remained readable:

- SHA-256:
  `237C6F065B63AF36B44F4DB656ACC4E736243998C3732D735ACFBF0416B30B0B`
- catalog entries: 576
- archive hash match: yes

Production baseline:

- `public.analytics_events`: 1,106 rows
- `public.analytics_identities`: 36 rows
- `public.users`: 14 rows
- target v1.0.6 columns already present: 0
- target v1.0.6 indexes already present: 0
- RLS on all three inspected tables: enabled
- anon/authenticated grants on all three inspected tables: none
- analytics function execution: `service_role` only

## Migration-history drift

Production records:

- `20260714221741 website_analytics_and_rate_limit_security`
- `20260714221812 remove_duplicate_analytics_created_index`
- `20260715002312 secure_auth_analytics_data`
- `20260715022446 account_delete_rpc`

The repository contains:

- `0001_init.sql`
- `0002_rate_limits.sql`
- `20260714211752_secure_auth_analytics_data.sql`
- `20260715022446_account_delete_rpc.sql`
- `20260716200846_v105_analytics_engagement_and_desktop_ingestion.sql`
- `20260716213027_v105_entitlements_and_billing_foundation.sql`
- `20260717103000_v105_server_authoritative_sessions.sql`
- `20260722080817_existing_user_auth_bridge.sql`
- `20260722090000_v106_analytics_only.sql`

Only `20260715022446` is common by version. Production has three versions not
represented by local migration filenames, while the repository has eight
versions not recorded in production, including the v1.0.6 migration.

The release instruction requires an immediate stop on migration-history drift.
No migration push, history repair, SQL migration, schema-cache reload, rollback,
or production DDL was run.

Prepared rollback, not executed:

`websites/atlas-web/supabase/rollbacks/20260722090000_v106_analytics_only.rollback.sql`

It drops the two v1.0.6 indexes and then the three nullable columns. It is only
safe after all senders that use those columns have been rolled back.

## Gate 3

Gate 3 was not started because Gate 2 did not pass. No synthetic production
events were sent, retained, or deleted.

## Production safety

- Production DDL applied: no
- Production data changed: no
- Migration history changed: no
- Credentials printed: no
- Credentials persisted: no
- Non-analytics objects changed: no
- Deployment, merge, tag, upload, installer build, or public replacement: no

