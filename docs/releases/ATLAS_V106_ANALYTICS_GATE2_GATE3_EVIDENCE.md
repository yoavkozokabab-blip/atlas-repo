# Atlas v1.0.6 analytics Gate 2/3 evidence

Status: **READY FOR GATE 4 - GATE 2 AND GATE 3 PASSED**

Gate 2 was captured on 2026-07-24 and Gate 3 on 2026-07-25 from branch
`release/atlas-v1.0.6-analytics-rc`. The temporary capability commit was
`2bfa64d2`; the cleaned production source commit is `12bed385`.

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

A temporary server-only endpoint was added in `2bfa64d2`. It used a dedicated
short-lived sensitive production variable and a protected header, compared
SHA-256 digests with `timingSafeEqual`, rejected missing or weak configuration,
and set `is_internal=true` only during server-side row construction. The normal
desktop route was unchanged and continued to reject a client-controlled
`internal` field.

Before production use:

- clean `npm ci`: completed
- analytics/auth/internal-capability tests: 39 passed
- production build: passed, 42 static pages generated
- client bundle scan: zero matches for the variable name or protected header
- missing, wrong, correct, weak, and body-override behavior: passed locally

The first Vercel attempt was rejected by the 15,000-file upload limit, without
deploying. The next attempt was blocked because the local commit used a
placeholder author email that did not match the authenticated GitHub/Vercel
identity. Its short-lived variable was removed and the blocked deployment was
deleted. A source-neutral identity commit, `edff7607`, used the linked GitHub
owner's public noreply identity; no product source changed.

Temporary production deployment `dpl_JAUbgxiimLyf1GD4R9r55MHeAbaA` then
reached `READY`. The controlled request results were:

| Probe | Result |
| --- | --- |
| missing secret | HTTP 404 `not_found` |
| wrong secret | HTTP 404 `not_found` |
| protected body `internal=true` override | HTTP 400 `invalid_event` |
| public body `internal=true` override | HTTP 400 `invalid_event` |
| `desktop_launched` | HTTP 202, recorded 1 |
| duplicate `desktop_launched` delivery | HTTP 202, recorded 0 |
| `sample_scan_completed` | HTTP 202, recorded 1 |
| `graph_opened` | HTTP 202, recorded 1 |
| malformed installation UUID | HTTP 400 `invalid_event` |
| unsupported event name | HTTP 400 `invalid_event` |
| forbidden top-level metadata | HTTP 400 `invalid_event` |
| forbidden nested source metadata | HTTP 400 `invalid_event` |
| oversized metadata | HTTP 400 `invalid_event` |

Database verification found exactly three rows for the unique synthetic
installation ID, one per valid event. All three have `is_internal=true`.
The duplicate created no second row. Global searches found zero rows containing
either forbidden privacy marker.

The live analytics count at database verification was 1,125:

- Gate 2 baseline: 1,106
- ordinary non-internal website events received after Gate 2: 16
- controlled Gate 3 internal rows: 3

The 16 ordinary events were classified only by event name and source and were
not modified. `analytics_identities` remained 36, `public.users` remained 14,
and migration history remained five rows with `20260724120103` present.

Supabase API logs show four successful HTTP 201 analytics upsert calls during
the controlled window: the three inserts and the duplicate conflict path.
There was no PostgREST 400 or schema-cache error. Sanitized Vercel log scanning
found no 5xx response, schema-related message, credential pattern, secret
variable name, protected header, or forbidden marker.

The three synthetic rows were retained with recorded IDs because they are
marked internal. No non-synthetic row was deleted or modified.

## Gate 3 cleanup

- the short-lived production variable was removed and independently confirmed
  absent
- the temporary route, secret helper, and dedicated QA file were deleted in
  cleanup commit `12bed385`
- cleanup deployment `dpl_9ji1orenMyZcWNeomoiQZ7eq5pBj` reached `READY` and
  owns the production alias
- the removed endpoint returns HTTP 404
- the normal public endpoint still rejects body `internal=true` with HTTP 400
- the historical temporary deployment was deleted, removing its unique route
  and encrypted environment snapshot
- the blocked intermediate deployment was also deleted

Private sanitized Gate 3 evidence:

`C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate3-20260725T-login-confirmed`

## Production safety

- Production DDL: only the reviewed analytics reconciliation
- Production data rows changed by Gate 2: none
- Migration-history change: exactly one approved row
- RLS or grant change: none
- Non-analytics schema change: none
- Synthetic production ingestion: three retained internal-only rows
- Credentials printed: no
- Credentials persisted: no
- Temporary deployment: deleted after verification
- Cleaned production deployment: ready
- Merge, tag, release upload, installer build, or public installer replacement:
  no
