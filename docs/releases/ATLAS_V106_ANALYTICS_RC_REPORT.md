# Atlas v1.0.6 analytics-only release candidate

Verdict: **READY FOR GATE 4; PUBLIC RELEASE STILL NOT READY**

## Latest evidence-gate attempt

Gate 2 passed on 2026-07-24. The isolated Supabase CLI workdir contained the
four recovered production migrations and only
`20260724120103_v106_analytics_production_state_reconciliation.sql` as pending.
The CLI applied and recorded that single migration.

The archive SHA-256 was reverified as
`237C6F065B63AF36B44F4DB656ACC4E736243998C3732D735ACFBF0416B30B0B`,
and `pg_restore --list` still reports 576 catalog entries. Counts before and
after migration were 1,106 analytics events, 36 analytics identities, and 14
public users. Exact columns, indexes, history, protected user/auth hashes,
RLS, grants, constraints, functions, and the non-analytics schema passed.
PostgREST recognized all three new columns with HTTP 200.

Gate 3 passed on 2026-07-25 through a temporary server-only endpoint protected
by a dedicated short-lived secret. Normal public ingestion continued to reject
client-controlled `internal` fields. The three valid events were stored exactly
once each with `is_internal=true`; duplicate delivery recorded zero additional
rows; malformed, unsupported, forbidden, nested-source, oversized, and client
override requests returned controlled 4xx responses. No forbidden marker or
schema-related PostgREST 400 was found.

The short-lived variable and temporary deployment were removed after testing.
Cleanup commit `12bed385` removed the endpoint and helper, and cleaned
deployment `dpl_9ji1orenMyZcWNeomoiQZ7eq5pBj` is `READY` on the production
alias. Full sanitized evidence is in
`ATLAS_V106_ANALYTICS_GATE2_GATE3_EVIDENCE.md`.

This is a new evidence pass on `release/atlas-v1.0.6-analytics-rc`. No merge,
tag, release upload, public-installer replacement, or installer build was
performed.

## Branch and build

- Branch: `release/atlas-v1.0.6-analytics-rc`
- Branch HEAD: sanitized evidence-report commit after cleanup (the packaged
  code commit is listed below)
- Packaged desktop/website source commit: `6bdaf6eafd62fbd90af85d461acbadba5396fc8b`
- Production reconciliation migration:
  `20260724120103_v106_analytics_production_state_reconciliation`
- RC payload: `dist/Atlas/Atlas.exe`
- RC size: 3,703,963 bytes
- RC SHA-256: `1E3C9F8A0E66135983009016EB76C2BC512C6A9EFACD5D2C9F50893C8D731C20`
- RC copy retained outside Git: `C:\Users\babi2\.codex\visualizations\2026\07\19\019f7995-b5dd-7051-b6ed-475e40701576\atlas-v106-analytics-rc\Atlas.exe`
- Temporary installer staging was self-tested with `AtlasAccounts.exe` **absent**;
  tracked staging files were restored afterward so the branch stays merge-clean.

## Backup and production migration

Gate 1 is complete. The private Git-external evidence directory is:

`C:\J.A.R.V.I.S\.atlas-private\analytics-v106-gate1-direct-20260723T220310Z`

It contains the custom-format database archive, roles without passwords,
archive catalog, extracted restore SQL, manifest, hashes, and non-secret Gate 1
evidence. The archive catalog includes schema, data, indexes, constraints,
grants, RLS objects, and migration history. No production DDL or synthetic
ingestion had been executed when Gate 1 completed.

Gate 2 is complete. The reviewed production-state reconciliation was applied
without history repair, replaying unrelated migrations, or changing
non-analytics objects.

Gate 3 is complete. The three uniquely identified synthetic rows were retained
because all are marked `is_internal=true`. At verification, the live analytics
total was 1,125: the 1,106 Gate 2 baseline, 16 ordinary non-internal website
events received afterward, and the three internal Gate 3 rows. Identities
remained 36 and public users remained 14.

The private backup/restoration procedure is documented in
`ATLAS_V106_ANALYTICS_BACKUP_GATE.md`.

## Contract and privacy

- Website allowlist: `site_visit`, `page_view`, `download_clicked`,
  `installer_download_started`.
- Desktop allowlist: `desktop_launched`, `sample_scan_completed`,
  `real_repo_scan_completed`, `scan_failed`, `graph_opened`,
  `impact_completed`, `mcp_connected`, `analytics_opted_out`.
- Unsupported account, Ask, heartbeat, health-check, UI-render, and
  `api_me_success` events are rejected.
- Desktop and website sanitizers recursively reject paths, repository/file
  identity, source, prompts, symbols, graph/Impact data, terminal output,
  usernames, emails, tokens, passwords, and path-bearing stack traces.
- Opt-out is persisted locally, clears the outbox, fails closed on persistence
  errors, and prevents remote delivery.
- Local-only startup no longer calls the accounts helper. Packaging omits the
  helper by default; `-IncludeAccounts` remains an explicit future-release
  opt-in.

## Download measurement

The website emits `download_clicked` once per browser click and the download
route emits `installer_download_started` when the response/redirect begins.
GitHub asset download counts remain the source for raw file downloads;
`desktop_launched` is the actual desktop execution signal. No completed install
is inferred from a click.

## Dependency security

Current resolved runtime is Next `15.5.18` with sharp `0.34.5` (same supported
Next major). `npm audit --audit-level=high --omit=dev` and the full current
`npm audit` both report zero vulnerabilities. A clean `npm ci` completed, but
its terminal summary and the cleanup Vercel install transiently reported five
high findings; the immediate post-install local audits were clean, so this
discrepancy must be rechecked by the release operator before publication.

## Tests and verification

- Website analytics/contract QA: **22 passed**.
- Desktop analytics/privacy/opt-out/helper targeted tests: **44 passed**.
- Local-only/packaging account suppression tests: **15 passed**.
- Website production build: **passed** (42 routes generated).
- Installer staging self-test: **passed**; no accounts helper staged during the
  RC build (tracked staging was restored after the external RC copy was saved).
- Full desktop suite: **1,598 passed, 21 skipped, 5 failed, 36 errors** out of
  1,659 collected. The failures/errors are in legacy `phase186`/`phase193`
  accounts tests and arise from shared SQLite fixture contamination (`users`
  already exists / `devices` missing); they are outside the analytics-only
  runtime and were not treated as release evidence.
- Production backup revalidation and Gate 2 pre-migration snapshot: **passed**.
- Production migration and post-migration verification: **passed**.
- PostgREST recognition of the three new analytics columns: **passed**.
- Temporary internal-capability analytics/auth verification: **39 passed**.
- Synthetic production ingestion: **passed**; three retained internal rows,
  duplicate suppressed, invalid/privacy/oversize probes controlled.
- Capability cleanup: **passed**; secret absent, temporary deployment deleted,
  cleaned endpoint HTTP 404.
- Packet capture, fresh-profile install, and upgrade-over-v1.0.5 verification
  remain incomplete.

## Release blockers

1. Fresh Windows profile, upgrade-over-v1.0.5, offline/opt-out packet capture,
   and installed-application verification remain unproven.
2. The full desktop suite is not green because of pre-existing accounts-test
   fixture contamination; the accounts feature is intentionally disabled in
   this RC, but the suite result must be reconciled before a public release.

Gate 4 may begin. Public release review can complete only after the remaining
blockers are resolved. The current public installer was not replaced.
