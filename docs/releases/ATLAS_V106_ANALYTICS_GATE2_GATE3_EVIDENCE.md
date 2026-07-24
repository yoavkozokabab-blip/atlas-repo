# Atlas v1.0.6 analytics Gate 2/3 evidence

Status: **NOT READY - GATE 2 PASSED; GATE 3 BLOCKED BEFORE INGESTION**

Captured on 2026-07-24 from branch
`release/atlas-v1.0.6-analytics-rc` at migration HEAD `60b20a04`.

## Repository hygiene

- No path under `.atlas-private/` is tracked.
- The operational runners and all production evidence remain in the
  Git-external `C:\J.A.R.V.I.S\.atlas-private` directory.
- The credential-pattern scan previously recorded for changes since
  `f843538e` found no credential value.
- No repository hygiene correction was required.

## Gate 2 - migration

Applied exactly:

`20260724120103_v106_analytics_production_state_reconciliation.sql`

The private isolated Supabase CLI workdir contained the four exact
production-recorded migration versions and the approved reconciliation as its
only pending version. It did not contain `20260722090000`.

The Gate 1 custom archive remained readable:

- SHA-256:
  `237C6F065B63AF36B44F4DB656ACC4E736243998C3732D735ACFBF0416B30B0B`
- catalog entries: 576
- archive hash match: yes

Pre- and post-migration counts:

| Relation | Before | After |
| --- | ---: | ---: |
| `public.analytics_events` | 1,106 | 1,106 |
| `public.analytics_identities` | 36 | 36 |
| `public.users` | 14 | 14 |

Migration history increased from four rows to five rows. The only new row is:

`20260724120103 v106_analytics_production_state_reconciliation`

Verified target definitions:

- `installation_id text null`, without a default
- `duration_active_ms bigint null`, without a default
- `duration_elapsed_ms bigint null`, without a default
- `analytics_events_installation_created_at_idx` on
  `(installation_id, created_at desc)` where `installation_id is not null`
- `analytics_events_event_created_at_idx` on
  `(event_name, created_at desc)`

The first post-check stopped on a verifier-scope false positive: the catalog
fingerprint classified the two new analytics index relations as non-analytics.
No unexpected database object was found. A normalized full pre/post schema
comparison then proved that the only schema differences were the three
approved columns, their three comments, and the two approved indexes. The
corrected verification passed.

Additional passed checks:

- all 1,106 existing analytics rows were preserved
- analytics constraints were unchanged
- analytics RLS, policies, and grants were unchanged
- global relation security and default grants were unchanged
- public functions and execute grants were unchanged
- non-analytics schema was unchanged
- `public.users` and `auth.users` row-content hashes were unchanged
- PostgREST schema reload was requested successfully
- PostgREST returned HTTP 200 when selecting all three new columns
- no credential or credential-bearing URL was printed or persisted

Private sanitized evidence:

`C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate23-20260724T124810Z`

Prepared rollback, not executed:

`websites/atlas-web/supabase/rollbacks/20260724120103_v106_analytics_production_state_reconciliation.rollback.sql`

## Gate 3 - ingestion

Gate 3 stopped before sending any production request.

The production desktop endpoint allowlist accepts:

`eventName`, `installationId`, `sessionId`, `appVersion`, `buildCommit`,
`properties`, and `eventId`.

It does not accept an `internal` field. In the production environment,
`buildAnalyticsRow` otherwise sets `is_internal=false`. Therefore the actual
Atlas production desktop ingestion route cannot currently create the required
synthetic `is_internal=true` rows.

An otherwise-valid internal-capability probe was prepared but was not
transmitted because it could have created a non-internal production analytics
row. Consequently:

- valid desktop event tests: not sent
- duplicate-delivery test: not sent
- malformed UUID test: not sent
- unsupported event test: not sent
- forbidden metadata tests: not sent
- oversized metadata test: not sent
- synthetic rows retained or deleted: none
- analytics row count after Gate 2 remains 1,106

This is an application-contract blocker, not a database schema-cache failure.
Gate 2's direct PostgREST column probe succeeded.

## Production safety

- Production DDL: only the reviewed analytics reconciliation
- Production data rows changed by Gate 2: none
- Migration-history change: exactly one approved row
- RLS or grant change: none
- Non-analytics schema change: none
- Synthetic production ingestion: none
- Credentials printed: no
- Credentials persisted: no
- Deployment, merge, tag, upload, installer build, or public replacement: no
