# Atlas v1.0.6 analytics-only release candidate

Verdict: **NOT READY**

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

Blocked. No Supabase CLI, production database URL, service-role key, or
dashboard export session was available. No restorable backup was created and
no production DDL or synthetic ingestion was executed.

Required before operator release review:

- private restorable exports of `public.analytics_events` and
  `public.analytics_identities`, schema, migration history, indexes,
  constraints, grants, and RLS;
- verified pre-change count of 1,106 analytics rows and unchanged 14
  `public.users` rows;
- apply and verify only the v1.0.6 additive migration, then run the production
  ingestion checks and remove/mark internal synthetic events.

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
- Production backup, production row-count/RLS/grant verification, synthetic
  production ingestion, packet capture, fresh-profile install, and upgrade-over-
  v1.0.5 verification: **not run** because production credentials and an
  installable unsigned setup artifact were not available/authorized.

## Release blockers

1. Production backup gate is uncleared: no restorable private backup exists.
2. Production migration and ingestion verification are therefore unexecuted.
3. Fresh Windows profile, upgrade-over-v1.0.5, offline/opt-out packet capture,
   and installed-application verification remain unproven.
4. The full desktop suite is not green because of pre-existing accounts-test
   fixture contamination; the accounts feature is intentionally disabled in
   this RC, but the suite result must be reconciled before a public release.

Manual release review can begin only after these blockers are resolved. The
current public installer was not replaced.
