# Atlas v1.0.6 analytics RC — production backup gate

Status: **COMPLETE**

The analytics DDL has not been applied by this branch. Gate 1 completed at
2026-07-23T22:04:00Z through a live, non-dry-run PostgreSQL 17.10 logical
backup.

Private Git-external evidence directory:

`C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate1-direct-20260723T220310Z`

Captured and verified:

- custom-format production archive:
  `atlas-prod-pre-v106.full.custom`
- archive size: 359,845 bytes
- archive SHA-256:
  `237C6F065B63AF36B44F4DB656ACC4E736243998C3732D735ACFBF0416B30B0B`
- roles export with role passwords excluded
- `pg_restore --list`: passed, 576 catalog entries
- required archive objects: `public.analytics_events`,
  `public.analytics_identities`, and
  `supabase_migrations.schema_migrations`
- restore SQL extraction: passed, 490,158 bytes
- post-backup counts: 1,106 analytics events, 36 analytics identities,
  and 14 public users
- migration history remains the four pre-v1.0.6 production migrations
- production DDL applied: no
- Gates 2–6 attempted: no
- credentials or database URL recorded: no

The Supabase Management API returned no managed backup records; PITR is
disabled and WALG is enabled. The private logical archive is therefore the
Gate 1 restore artifact.

## Restoration procedure

1. Stop analytics senders and prevent new writes.
2. Restore the captured schema/data into a disposable database first.
3. Verify row counts, indexes, constraints, grants, and RLS against the capture.
4. If the v1.0.6 migration was applied, run
   `websites/atlas-web/supabase/rollbacks/20260722090000_v106_analytics_only.rollback.sql`
   only after all senders have been rolled back.
5. Re-run the analytics contract and ingestion tests before reconnecting production.

The archive catalog and restore-SQL extraction prove that the custom archive is
readable by PostgreSQL 17. A destructive restore rehearsal was not run against
production. Do not provide the database URL or access token in chat, commits,
or reports.
