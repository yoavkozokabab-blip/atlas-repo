# Atlas v1.0.6 analytics-only release candidate

Gate 4 pre-build verdict: **READY TO BUILD V1.0.6 RC**

Final-publication verdict: **NOT READY** until the RC is built and the
post-build install, upgrade, packet-capture, packaging, and public-identity
gates pass.

The completed, superseding Gate 4 environment and public-identity baseline is
recorded in `ATLAS_V106_GATE4_PREBUILD_BASELINE.md`. The blocked attempt below
is retained as historical evidence and must not be read as the current Gate 4
result.

## Gate 4-6 attempt (2026-07-25)

Gate 4 did not pass, so no v1.0.6 installer was built and Gates 5-6 were not
started. No installer was run, no production analytics request was sent, and no
deployment, merge, tag, release upload, or public-installer replacement was
performed.

Release identity at the start of the attempt:

- Branch: `release/atlas-v1.0.6-analytics-rc`
- HEAD: `8da893799e2421d91db450e687498c362ab9b094`
- Last committed desktop source change: `6bdaf6eafd62fbd90af85d461acbadba5396fc8b`
- Last committed website source change: `12bed38574efd4066db930d134f1e1c1166d5205`
- Production migration:
  `20260724120103_v106_analytics_production_state_reconciliation`
- Target desktop version: `1.0.6`
- Worktree: clean at entry; dirty at exit with uncommitted fixture,
  v1.0.6 identity, Ask-disabled copy, and sharp-reachability mitigation changes

Accounts remain hidden, local-only mode remains the default, the accounts
helper is not started in local-only mode, and packaging excludes
`AtlasAccounts.exe` unless the explicit future `-IncludeAccounts` option is
used. Ask remains disabled by the launch guard loaded last in the desktop UI.
The frozen analytics allowlists and sanitizers were not broadened.

The live download route did not match the stated v1.0.5-hotfix1 baseline. On
2026-07-25 it redirected to the public v1.0.4 GitHub asset. That asset was
43,212,710 bytes, SHA-256
`2A1EAA9EEC99311E44496DA04157AD1DB1F60C4373ECD5FFB33D52127CDFFF8A`,
file version `1.0.4 (2026-07-16) a`, and unsigned. The public v1.0.5 release
asset was also downloaded without execution for upgrade provenance: 43,296,784
bytes, SHA-256
`B2531078FC814B9D2AA454FAFD31711AE353AAFCD336C6E39D21B4645A9573EF`,
file version `1.0.5 (2026-07-21) 4`, and unsigned. The tracked v1.0.5 release
manifest records a different size and hash, so it cannot currently establish
the public upgrade baseline.

The clean desktop baseline collected 1,659 tests and produced **1,637 passed,
21 skipped, 1 failed, 0 errors**. The single failure was a stale fixture:
`test_copy_review_table_exists` escaped the repository through `parents[3]`
and succeeded only when an unrelated sibling workspace report existed. The
correction keeps the same copy assertion and points to a tracked repository
fixture. The other source changes set desktop metadata and visible version copy
to v1.0.6 while preserving the existing Ask-disabled launch guard.

The 21 skips were classified as follows:

- 19 explicit external-repository skips: Home Assistant was not present and
  six slow Home Assistant route tests require `ATLAS_RUN_HA=1`. These are
  acceptable in the unit suite only if the required large-repository installed
  test is later completed.
- 2 release-relevant packaging skips: fresh `dist/Atlas` and
  `generated_version.iss` do not exist until a fresh packaging run. They must
  pass after the release build and are not waived.

Targeted and full reruns could not execute because pytest lost access to each
new Windows temp root during its mandatory autouse `tmp_path` setup. A
sandbox-external rerun could not be approved because the approval service
reported its usage limit. Playwright likewise failed before assertions at
worker creation with `spawn EPERM`. These are test-environment failures, not
product passes.

Dependency reproduction identified a newly published advisory that npm's
current audit response did not include:

- Locked runtime: Next `15.5.18`, React/React DOM `19.2.6`, sharp `0.34.5`,
  Supabase JS `2.110.8`; development Supabase CLI `2.109.1`.
- `npm audit --omit=dev --json`: 0 critical, 0 high, 0 total.
- Full `npm audit --json`: 0 critical, 0 high, 0 total.
- GitHub-reviewed `GHSA-f88m-g3jw-g9cj`: 1 high-severity sharp finding,
  affecting `<0.35.0`; patched in `0.35.0`.
- Next `15.5.18` and `15.5.19` both declare `sharp ^0.34.3`, so the patched
  sharp line is not compatible with the supported Next 15 dependency range.
  No override, forced audit fix, lockfile regeneration, or framework major
  upgrade was used.
- Atlas has no `next/image` import. A source change sets
  `images.unoptimized=true`, the supported Next switch that disables the
  Image Optimization API, and adds an assertion that the app remains free of
  `next/image`. Static configuration inspection passed, but the clean build and
  runtime route verification are blocked, so reachability is not yet accepted
  as closed.

Clean `npm ci` failed during lifecycle-script process creation with
`spawn EPERM`; the partially created dependency tree is not release evidence.
The clean production build and 42-route check were therefore not run.

The removed Gate 3 endpoint is absent from source. A stale ignored
`websites/atlas-web/.next` cache still contained an old compiled copy of the
retired endpoint and the environment-variable name, but no secret value.
Removal was attempted against the exact validated cache path and could not be
approved because the approval service reported its usage limit. This stale
cache was not packaged or deployed, but it must be deleted and the clean build
must prove that the endpoint is absent before release.

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

The earlier npm-only conclusion is superseded by the Gate 4-6 attempt above.
npm currently reports zero vulnerabilities, but the July 21 GitHub-reviewed
sharp advisory applies to the locked sharp `0.34.5`. The supported
image-optimization-disable mitigation is present but cannot be accepted until
the clean build and runtime route verification pass.

## Tests and verification

- Website analytics/contract QA: **22 passed**.
- Desktop analytics/privacy/opt-out/helper targeted tests: **44 passed**.
- Local-only/packaging account suppression tests: **15 passed**.
- Website production build: **passed** (42 routes generated).
- Installer staging self-test: **passed**; no accounts helper staged during the
  RC build (tracked staging was restored after the external RC copy was saved).
- Clean desktop baseline: **1,637 passed, 21 skipped, 1 failed, 0 errors** out
  of 1,659 collected. The prior reported SQLite contamination did not
  reproduce. The one stale copy-review fixture was corrected without weakening
  its assertion, but mandatory reruns are blocked by the Windows temp-root ACL
  failure and cannot yet be reported green.
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

1. Targeted and full desktop reruns are blocked by the pytest temp-root ACL
   failure; zero release-relevant failures has not been demonstrated.
2. Clean `npm ci`, analytics/auth tests, clean production build, and the
   42-route check are blocked by `spawn EPERM`.
3. The sharp high-severity advisory is not represented in npm's audit result.
   The supported reachability mitigation is unverified at build/runtime level.
4. The stale ignored `.next` cache still contains a compiled copy of the
   retired Gate 3 endpoint and must be deleted before a clean build.
5. No v1.0.6 installer was built because the prerequisite gates did not pass.
   Fresh-profile, upgrade, packet-capture, installed-app, production analytics,
   and final-installer verification therefore remain incomplete.
6. The live download route points to v1.0.4, not the stated v1.0.5-hotfix1
   baseline, and the tracked v1.0.5 manifest does not match the public v1.0.5
   asset.

The current public installer was not replaced. **NOT READY**.
