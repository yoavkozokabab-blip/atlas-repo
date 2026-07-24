# Atlas v1.0.6 analytics-only release candidate

Verdict: **NOT READY**

## Latest evidence-gate attempt

Gate 2 preflight ran after the completed live PostgreSQL 17.10 Gate 1 backup.
The archive SHA-256 was reverified as
`237C6F065B63AF36B44F4DB656ACC4E736243998C3732D735ACFBF0416B30B0B`,
and `pg_restore --list` still reports 576 catalog entries.

The required stop condition then triggered: production migration history does
not match the repository migration set. Production records four versions,
while only `20260715022446` is common by version with the local files.
Production has three recorded versions absent from local filenames, and the
repository has eight versions not recorded in production, including
`20260722090000_v106_analytics_only`.

No migration, migration-history repair, schema-cache reload, rollback, or
synthetic ingestion was run. Counts remain 1,106 analytics events, 36 analytics
identities, and 14 public users. Full sanitized drift evidence is in
`ATLAS_V106_ANALYTICS_GATE2_GATE3_EVIDENCE.md`.

This is a new evidence pass on `release/atlas-v1.0.6-analytics-rc`. No
deployment, upload, tag, public-installer replacement, or merge was performed.

## Branch and build

- Branch: `release/atlas-v1.0.6-analytics-rc`
- Branch HEAD: report-only commit after the RC build (the packaged code commit is listed below)
- Packaged desktop/website source commit: `6bdaf6eafd62fbd90af85d461acbadba5396fc8b`
- Migration: `20260722090000_v106_analytics_only`
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
ingestion was executed.

Gate 2 is blocked by migration-history drift. The reviewed v1.0.6 migration was
not applied, and Gate 3 did not start.

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
its terminal summary transiently reported four high findings; the immediate
post-install audit was clean, so this discrepancy must be rechecked by the
release operator before publication.

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
- Production migration: **not run** because migration-history drift triggered
  the mandatory stop condition.
- Synthetic production ingestion: **not run** because Gate 2 did not pass.
- Production migration/RLS/grant verification after migration, packet capture,
  fresh-profile install, and upgrade-over-v1.0.5 verification remain
  incomplete.

## Release blockers

1. Production migration history and repository migration files have unresolved
   drift. The exact correspondence and schema effects must be reconciled
   without force-repairing or marking unrelated migrations as applied.
2. The v1.0.6 migration and production ingestion verification are unexecuted.
3. Fresh Windows profile, upgrade-over-v1.0.5, offline/opt-out packet capture,
   and installed-application verification remain unproven.
4. The full desktop suite is not green because of pre-existing accounts-test
   fixture contamination; the accounts feature is intentionally disabled in
   this RC, but the suite result must be reconciled before a public release.

Manual release review can begin only after these blockers are resolved. The
current public installer was not replaced.
