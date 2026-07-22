# Atlas v1.0.6 analytics RC — production backup gate

Status: **BLOCKED pending operator backup**

The analytics DDL has not been applied by this branch. No Supabase credentials
or dashboard session are available in the local workspace, so a restorable
production backup cannot be truthfully claimed.

Before applying `websites/atlas-web/supabase/migrations/20260722090000_v106_analytics_only.sql`, an operator with access to the `atlas-prod` Supabase project must capture, privately:

- `public.analytics_events` data and schema (including rows, indexes, constraints, grants, and RLS state)
- `public.analytics_identities` data and schema
- migration history (`supabase_migrations.schema_migrations` or dashboard export)
- the current 1,106-row count (before synthetic events)

Preferred methods, in order: Supabase dashboard database export, `supabase db dump`,
`pg_dump`, then table-level CSV/JSON plus schema export. Backup files must remain
outside Git and must never contain a service-role key in reports or logs.

## Restoration procedure

1. Stop analytics senders and prevent new writes.
2. Restore the captured schema/data into a disposable database first.
3. Verify row counts, indexes, constraints, grants, and RLS against the capture.
4. If the v1.0.6 migration was applied, run
   `websites/atlas-web/supabase/rollbacks/20260722090000_v106_analytics_only.rollback.sql`
   only after all senders have been rolled back.
5. Re-run the analytics contract and ingestion tests before reconnecting production.

Required operator input to clear this gate: a restorable backup artifact and the
non-secret Supabase project reference/command output proving the backup can be
restored. Do not provide the service-role URL or key in chat, commits, or reports.
