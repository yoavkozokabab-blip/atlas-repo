# Atlas v1.0.6 migration drift reconciliation

Verdict: **READY FOR AN AUTHORIZED GATE 2 RETRY**

This document reconciles the migration history and schema captured from
`atlas-prod` with repository baseline commit `52072605` plus the Strategy B
files created by this task. It does not authorize or record any production DDL,
migration-history repair, ingestion, deployment, or release action.

## Evidence used

- Gate 1 PostgreSQL 17.10 custom archive:
  `C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate1-direct-20260723T220310Z\atlas-prod-pre-v106.full.custom`
- Verified archive SHA-256:
  `237C6F065B63AF36B44F4DB656ACC4E736243998C3732D735ACFBF0416B30B0B`
- Gate 2 production snapshot:
  `C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate2-20260724T113743Z`
- Disposable PostgreSQL 17 evidence:
  `C:\J.A.R.V.I.S\.atlas-private\analytics-v106-drift-test-20260724T115250Z`
- Repository migration SQL and Git history across all local refs and worktrees
- The migration SQL stored in
  `supabase_migrations.schema_migrations.statements` inside the Gate 1 archive

Private evidence paths are recorded for auditability. Their contents are not
tracked by Git and contain no connection credentials.

## Summary

- Production history contains four migrations.
- Before this reconciliation, the repository contained nine migration files.
- Three production versions had no same-version repository file.
- Eight pre-existing repository versions were not recorded in production.
- `20260715022446` is the only version present in both places.
- The new Strategy B migration created by this reconciliation is also not yet
  recorded in production, bringing the current repository-only count to nine.
- No production object was changed.

## Production migration inventory

| Version | Recorded name | Purpose | Affected schema and objects | Repository presence | Observable effect |
| --- | --- | --- | --- | --- | --- |
| `20260714221741` | `website_analytics_and_rate_limit_security` | Create/harden website analytics and the rate-limit RPC | `public.analytics_events`; analytics indexes; `public.atlas_rate_limit_hit` ACL/search path | No same-version file. Related Git file `0003_analytics_and_rpc_security.sql` was added in `8fd0cb08` and deleted in `3db27448`. | Analytics table and RLS exist; rate-limit function is server-only with empty search path. Its temporary `analytics_events_created_idx` is absent after the next migration. |
| `20260714221812` | `remove_duplicate_analytics_created_index` | Remove the temporary duplicate created-time index | `public.analytics_events_created_idx` | No repository file or Git-ref match | Effect is present: the index is absent. |
| `20260715002312` | `secure_auth_analytics_data` | Harden analytics/account tables, add analytics identity and dedupe schema, and add the server-only summary function | `public.users`, `audit`, `reset_tokens`, `waitlist`, `rate_limits`, `analytics_events`, `analytics_identities`, `atlas_rate_limit_hit`, `atlas_analytics_summary` | No same-version filename. Its normalized SQL is an exact MD5/length match for `20260714211752_secure_auth_analytics_data.sql`. | Intended schema, dedupe index, RLS, grants, comments, and functions are present. |
| `20260715022446` | `account_delete_rpc` | Add server-only atomic account deletion | `public.atlas_delete_account(uuid,text)` and related table access inside the function | Present as `20260715022446_account_delete_rpc.sql` | Function, security-definer posture, search path, and service-role-only ACL are present. Recorded SQL differs from the file only by terminal punctuation in the function comment. |

## Production-only analysis

### `20260714221741`

The exact recorded SQL was recovered from the Gate 1 archive. It is closely
related to the deleted Git migration `0003_analytics_and_rpc_security.sql`, but
it is not byte-identical: the production statement attempted to create
`analytics_events_created_idx`, while the Git file used
`analytics_events_created_at_idx`.

The follow-up production migration immediately removed the temporary
`analytics_events_created_idx`. The durable effects are the analytics table,
RLS, server grants, and hardened rate-limit function. This was an application
migration recorded by Supabase, not an unrelated platform migration. The exact
tool or branch used to submit it is not recoverable from the archive, so any
claim that it was a Dashboard, CLI, or MCP application would be inference.

Risk: low for v1.0.6 because its durable prerequisites are present, but the
version cannot be mapped to the old Git file as an exact source copy.

### `20260714221812`

The exact one-statement SQL was recovered:

```sql
drop index if exists public.analytics_events_created_idx;
```

No repository or Git-ref file contains this version. The resulting effect is
fully observable and present. It is a tracked application cleanup, not a
Supabase platform migration.

Risk: low; no replay or history repair is required.

### `20260715002312`

The recorded SQL was recovered and compared after newline normalization and
trimming. It exactly matches
`20260714211752_secure_auth_analytics_data.sql`: both have 9,086 characters and
MD5 `4b39a2a6fe0a6af3d8051eeea9a536f9`.

Git commit `3b0bcd4d` added the local file. Production recorded the same SQL
under a later version and the same descriptive name. Prior
`docs/analytics/supabase-audit.md` reports that the production version was
applied.

Risk: low for schema understanding. The different version means the local file
must not be replayed or marked applied.

## Repository migration inventory and classification

The required classifications mean:

- **A** — schema effect already exists in production
- **B** — schema effect partially exists in production
- **C** — schema effect is absent from production
- **D** — migration is superseded by another production change
- **E** — migration is not required for analytics-only v1.0.6
- **F** — migration is unsafe or unrelated to this release

| Version | Repository file | Purpose and affected objects | Production history | Production effect | Class | Required for v1.0.6 | Account/session/Auth related | Action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `0001` | `0001_init.sql` | Initial `public.users`, `audit`, `reset_tokens`, `waitlist`, indexes, RLS, service grants | No | All intended objects/effects exist; production has an additional legacy Stripe column | **A** | Only as an already-satisfied prerequisite | Yes, account foundation | Do not replay; safe to ignore for this release |
| `0002` | `0002_rate_limits.sql` | `public.rate_limits` and `atlas_rate_limit_hit` | No | Table/index/function exist; function search path and ACL were later hardened | **D** | No | No | Do not replay; production hardening supersedes it |
| `20260714211752` | `20260714211752_secure_auth_analytics_data.sql` | Analytics identity/dedupe/security foundation plus limited account-column reconciliation | No | Exact SQL is recorded as production `20260715002312`; all durable effects exist | **D** | Yes, but already satisfied | Partly | Do not replay or mark applied |
| `20260715022446` | `20260715022446_account_delete_rpc.sql` | Server-only account-delete RPC | Yes | Present; same behavior, one comment-punctuation difference | Exact version/name match | No | Yes | Leave unchanged |
| `20260716200846` | `20260716200846_v105_analytics_engagement_and_desktop_ingestion.sql` | Three event columns, two indexes, five-argument summary function, purge function, analytics ACL reinforcement | No | RLS/ACL foundation exists; the three columns, two indexes, five-argument summary, and purge function are absent | **B** | Only the three columns and two indexes | No | Never replay as a whole; isolate the v1.0.6 delta |
| `20260716213027` | `20260716213027_v105_entitlements_and_billing_foundation.sql` | Entitlements, usage windows, billing events, usage RPC | No | All tables, indexes, constraints, and RPC are absent | **F** | No | Billing/account related | Exclude from analytics release |
| `20260717103000` | `20260717103000_v105_server_authoritative_sessions.sql` | `public.atlas_sessions` and active-session index | No | Table and index are absent | **F** | No | Session related | Exclude from analytics release |
| `20260722080817` | `20260722080817_existing_user_auth_bridge.sql` | Supabase Auth link columns, queue, trigger, functions, normalized indexes | No | All columns, table, indexes, trigger, and functions are absent | **F** | No | Auth/account related | Exclude from analytics release |
| `20260722090000` | `20260722090000_v106_analytics_only.sql` | Three nullable event columns, two indexes, comments | No | All five objects are absent | **C** | Yes | No | Keep as blocked historical candidate; superseded for `atlas-prod` |
| `20260724120103` | `20260724120103_v106_analytics_production_state_reconciliation.sql` | Verified production prerequisites plus the same three columns, two indexes, and comments | No; newly proposed | Absent before application; fully verified on the disposable restore | Strategy B | Yes | No | Apply only in a separately authorized Gate 2 retry |

## True v1.0.6 analytics delta

The frozen sender writes:

- `installation_id`: sanitized string; the desktop supplies a random UUID
- `duration_active_ms`: bounded integer milliseconds
- `duration_elapsed_ms`: bounded integer milliseconds
- `deduplication_key`: server-generated SHA-256 hex text used by PostgREST
  `on_conflict=deduplication_key`

The exact missing database delta is:

| Object | Required definition | Current production state |
| --- | --- | --- |
| `public.analytics_events.installation_id` | `text null`, no default | Missing |
| `public.analytics_events.duration_active_ms` | `bigint null`, no default | Missing |
| `public.analytics_events.duration_elapsed_ms` | `bigint null`, no default | Missing |
| `analytics_events_installation_created_at_idx` | `(installation_id, created_at desc) where installation_id is not null` | Missing |
| `analytics_events_event_created_at_idx` | `(event_name, created_at desc)` | Missing |

The existing unique
`analytics_events_deduplication_key_uidx(deduplication_key)` is present and is
the required PostgREST conflict target. No new unique constraint is required.

All three columns are nullable with no defaults, so the existing 1,106 rows
remain valid and receive null values. No data rewrite is required.

No function, trigger, constraint, RLS, policy, table grant, default privilege,
account object, session object, or Auth object is part of the delta.

## Strategy evaluation

### Strategy A — apply the old migration unchanged

Rejected for `atlas-prod`. Its SQL is narrowly scoped, but the active
repository migration directory would cause normal CLI application to include
other unrecorded post-production migrations. It also lacks explicit production
prerequisite checks and does not document the supersession.

### Strategy B — production-state-based migration

**Recommended.**

The generated migration is:

`websites/atlas-web/supabase/migrations/20260724120103_v106_analytics_production_state_reconciliation.sql`

It:

- validates the analytics table, RLS, zero browser grants, and exact unique
  dedupe index before DDL
- adds only the three nullable columns
- adds only the two reviewed indexes
- validates exact column and index definitions after DDL
- makes no account, session, Auth, function, RLS, policy, or grant change
- uses `if not exists` for safe reapplication while rejecting wrong existing
  definitions
- supersedes only the blocked `20260722090000` migration for the drifted
  production lineage

Rollback:

`websites/atlas-web/supabase/rollbacks/20260724120103_v106_analytics_production_state_reconciliation.rollback.sql`

### Strategy C — restore production-only source files

Not selected as the release strategy. Exact recorded SQL is recoverable, but
restoring the three missing versions alone does not resolve the eight
pre-existing repository-only versions. The recovered SQL remains valuable for
an isolated CLI deployment workdir and the audit trail.

### Strategy D — baseline or repair history

Rejected. No production history row needs correction, and no unrelated local
migration should be marked applied. Force repair would erase useful evidence
without reducing the schema risk.

## Disposable PostgreSQL 17 test

The Gate 1 archive was restored into PostgreSQL 17.10 on localhost. The
`public` and `supabase_migrations` schemas were restored; the generic PostgreSQL
package does not contain the Supabase-specific extensions required for a full
platform-schema restore, so `auth` was not restored.

Test sequence:

1. Verified baseline counts and absence of the five target objects.
2. Applied `20260724120103` in one transaction.
3. Verified exact types, nullability, defaults, indexes, and null values on all
   existing rows.
4. Applied the same migration again to test guarded idempotency.
5. Executed the rollback in one transaction.
6. Verified the original schema and counts were restored.

Results:

| Check | Result |
| --- | --- |
| Analytics rows | 1,106 before, after apply, after reapply, and after rollback |
| Analytics identities | 36 preserved |
| Public users | 14 preserved |
| Target columns after apply | 3 exact definitions |
| Target indexes after apply | 2 exact definitions |
| Existing rows with populated new values | 0 |
| Unique dedupe index | Preserved |
| Non-analytics schema hash | Unchanged |
| Analytics RLS/grants/policies hash | Unchanged |
| Analytics constraints hash | Unchanged |
| Migration-history hash | Unchanged by direct disposable SQL test |
| Reapplication | Passed |
| Rollback | Passed |
| Production access | None |

Because `auth` was not restored, the Auth non-change result is based on the
reviewed migration containing no `auth` reference and the unchanged
non-analytics `public` schema, not on an `auth.users` data comparison.

## Authorized Gate 2 retry plan

Production must not use the repository's active migration directory directly.

1. Reverify the approved backup hash and readable catalog.
2. Capture a new read-only snapshot. Require unchanged migration history and
   the same object-level prerequisites; row counts may increase through
   legitimate ingestion but must be preserved across the migration.
3. Build a private isolated Supabase CLI workdir containing:
   - the four exact production-recorded versions recovered from the Gate 1
     migration history
   - only
     `20260724120103_v106_analytics_production_state_reconciliation.sql`
     as pending
4. Run `supabase migration list --db-url ...` in that isolated workdir.
   Continue only if the four production versions align and `20260724120103` is
   the sole pending version.
5. Run `supabase migration up --db-url ...` without `--include-all`. This
   executes and records only the new migration; it is not a history repair.
6. Verify the new history row, exact columns/indexes, preserved counts,
   unchanged RLS/grants/policies/constraints, and no non-analytics schema diff.
7. Reload or verify the PostgREST schema cache, then prove the three columns and
   dedupe conflict target through the application route before Gate 3.

Abort before DDL if the backup hash, migration history, prerequisite schema,
RLS, grants, or dedupe index differs from this evidence.

Rollback is triggered by a wrong target definition, row loss, any security or
non-analytics diff, failure to record only the new migration version, or a
schema-cache failure that cannot be resolved without broadening scope. Execute
rollback only while no accepted sender has stored data in the new columns; if
senders have started, stop them first and preserve evidence before deciding.

Supabase's current migration documentation confirms that CLI pushes compare
local files to `supabase_migrations.schema_migrations`, and that direct remote
changes bypassing history create sync errors:
<https://supabase.com/docs/guides/deployment/database-migrations>.
