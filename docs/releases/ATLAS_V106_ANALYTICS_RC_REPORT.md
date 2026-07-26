# Atlas v1.0.6 analytics RC verification

Date: 2026-07-26

Verdict: **NOT READY**

The installed-client analytics 4xx was diagnosed and fixed with a minimal
sender-only change. A new RC2 installer was built and passed the affected
fresh-install, upgrade, packaging, privacy, retry, deduplication, and opt-out
verification. The two production validation gaps now have a narrow local
server fix with passing affected tests, build, route QA, and bundle scans.
Deployment was withheld because the required production dependency audit
reports two high-severity findings. Production therefore still accepts
malformed installation UUIDs and nested metadata.

No deployment, upload, tag, merge, release replacement, account change, RLS
change, grant change, or unrelated migration was performed.

## Release identity

- Branch: `release/atlas-v1.0.6-analytics-rc`
- Packaged desktop commit:
  `753ddc38a9bccc7010931c7903795280c9091a1a`
- Website commit:
  `d6565ec57af5988d5c5e28a9a7557f69897796d4`
- Undeployed server-validation fix:
  `ee5656cd028d1c3ca23a0f10ec453e704ce28dba`
- Production migration:
  `20260724120103_v106_analytics_production_state_reconciliation`
- RC2 installer:
  `C:\J.A.R.V.I.S\.atlas-private\atlas-v106-rc\Atlas_Setup_v1.0.6_RC2.exe`
- Size: 12,229,183 bytes
- SHA-256:
  `2D53AAD6BB4D48EEBF9DE407DAFE9BE58BF591C05099402941CCA733D8BB5ADA`
- File version: `1.0.6 (2026-07-26) 7`
- Product version: `1.0.6.0`
- Authenticode status: unsigned
- Superseded failed RC artifact: removed from the private RC directory

The staged payload contained the v1.0.6 sender at commit `753ddc38`.
`AtlasAccounts.exe` was absent. The embedded build metadata contained no
source-root path.

## Server-validation follow-up

The frozen contract requires every desktop event to carry a canonical UUID
installation identifier. It does not permit omission, coercion, trimming, or
server-generated replacement of a malformed value. Metadata is a one-level
object whose values may only be JSON strings, finite numbers, or booleans.
Nested objects, arrays, and `null` are invalid; unknown primitive keys continue
to be discarded by the existing sanitizer.

Two route-validation gaps caused the production failures:

1. The desktop route passed `installationId` directly to the generic
   `sanitizeIdentifier` path. That sanitizer accepts safe arbitrary text and
   was never intended to prove UUID identity.
2. The route checked nested content only for privacy markers. Safe nested
   objects therefore reached `sanitizeProperties`, which silently discarded
   nonprimitive values and allowed the event.

Commit `ee5656cd028d1c3ca23a0f10ec453e704ce28dba` adds two narrow runtime
predicates before normalization and storage:

- canonical, lowercase UUID syntax for required desktop `installationId`;
- one-level finite JSON primitive values for desktop `properties`.

The route retains the existing `invalid_event` HTTP 400 response. It does not
echo rejected values, bodies, validation internals, or stack traces. Rate
limiting still runs before validation. The server remains authoritative for
`is_internal`, and service-role handling, deduplication, storage payloads,
event allowlists, privacy keys, database schema, accounts, Auth, billing, Ask,
Graph, Impact, and MCP are unchanged.

Changed files:

- `websites/atlas-web/app/_lib/analytics-contract.ts`
- `websites/atlas-web/app/api/analytics/desktop-events/route.ts`
- `websites/atlas-web/qa/analytics-auth.spec.ts`
- `websites/atlas-web/docs/analytics/event-contract.md`

Predeployment verification:

- Clean `npm ci`: passed; 336 packages reproduced from the lockfile.
- Analytics/auth and frozen-contract tests: 28 passed, 0 failed.
- Production build: passed; 42 pages generated.
- Public-site QA: 42 desktop/mobile route views passed with zero page errors,
  overflow, broken links, or accessibility violations. An initial QA harness
  run used the production origin while browsing localhost and correctly
  received 403 from browser-write protection; the isolated server was
  restarted with its localhost origin and the complete run passed.
- Client bundle: zero credential values, server-secret names, or retired
  internal-test capability remnants.
- Server bundle: zero credential values or retired internal-test capability
  remnants. Two literal `sb_secret_` sanitizer patterns were classified as
  validation code, not secret values.
- Production dependency audit: **failed** with two high-severity findings,
  `next` through transitive `sharp`, and `sharp <0.35.0`
  (`GHSA-f88m-g3jw-g9cj`).

The dependency finding is outside the authorized analytics-validator diff.
No override, forced audit fix, framework downgrade, or unrelated dependency
change was made. Because the request required a green audit with no ignored
failures, commit `ee5656cd` was not deployed. There is no deployment ID, and
no follow-up production validation or RC2 post-deployment request was sent.

## Runtime-token containment

The exposed value was generated by the installed Atlas process and was usable
only as a bearer credential for that process's authenticated loopback API on
`127.0.0.1`. It was held in memory and in the user-scoped, integrity-protected
runtime descriptor. It could authorize local Atlas API responses, including
responses derived from the locally opened repository, while the issuing
process was running. It could not authenticate to Supabase, the website,
accounts, or any non-loopback service.

The issuing Atlas process and related verification helpers were stopped. Its
runtime descriptor was deleted, and the old credential no longer authenticated.
A subsequent isolated start created a different 43-character URL-safe token
and independent instance identity. Four RC2 fresh-profile starts and four RC2
upgrade-profile starts also produced distinct instance credentials. No token
was written to retained logs or evidence.

After cleanup:

- Atlas processes: 0
- Retained runtime descriptors: 0
- Credential-marker matches in retained private evidence: 0
- Privacy-marker matches in retained private evidence: 0
- Token matches in tracked files, AppData logs, and PowerShell history: 0

The token was strictly loopback-only, process-bound, invalidated, and not a
non-local security incident.

## Installed-client 4xx root cause

The original installed `desktop_launched` request used the canonical seven
top-level fields, UTF-8 JSON without BOM or trailing newline, and a valid UUID.
The 281-byte production request was recorded successfully, but the client did
not observe the response within its two-second transport window and retained
the event for retry.

The retry path stored local bookkeeping directly in the queued event:

`_delivery_attempts`

The next serialization sent that private bookkeeping field over the wire. The
retry request grew from 281 to 304 bytes and production correctly rejected the
extra top-level field with HTTP 400 and `invalid_event`. The direct diagnostic
request and frozen contract payload both remained canonical and returned 202.
After normalizing IDs and timestamps, `_delivery_attempts` was the only
field-level difference.

This affected newly generated v1.0.6 events after an ambiguous or transient
delivery result and any legacy queued event carrying the same local retry
bookkeeping. It was not caused by a stale bundle, old contract, malformed
fresh/upgrade event, server schema, or packaging omission.

## Minimum fix

Commit `753ddc38a9bccc7010931c7903795280c9091a1a` changes:

- `atlas_desktop/analytics_remote.py`
- `atlas_desktop/tests/test_remote_analytics.py`

The transport now creates a wire-only event representation that excludes
exactly `_delivery_attempts`; the bounded local outbox continues tracking retry
attempts. The test proves that all three retry attempts retain the canonical
seven-field wire contract.

Verification:

- Remote analytics tests: 30 passed
- Affected pre-build guards: 115 passed
- Packaging and hardening checks: 39 passed, 0 skipped
- Test-secret and retired internal-endpoint markers in the installer: 0
- Database URL, service-role, and credential markers in the installer: 0
- Repository/privacy markers in the installer: 0

## Fresh-profile RC2 verification

The final isolated fresh profile used a newly generated valid installation
UUID. Health, guest mode, sample scan, real-repository scan, Graph, Impact,
MCP, two restarts, and opt-out all passed.

Production accepted these eight events:

- `desktop_launched`: 3
- `sample_scan_completed`: 1
- `real_repo_scan_completed`: 1
- `graph_opened`: 1
- `impact_completed`: 1
- `mcp_connected`: 1

Four batched requests returned 202 with recorded counts 1, 5, 1, and 1.
Diagnostics ended at accepted 8, rejected 0, retries 0. Every event used the
seven-field contract, version 1.0.6, build `753ddc38`, source `desktop`,
platform `windows`, and environment `production`. Opt-out persisted across
restart and produced zero subsequent analytics requests.

## Upgrade-profile RC2 verification

The exact v1.0.4 public baseline installer was installed in an isolated
profile. Guest mode, sample scan, real-repository scan, Graph, Impact, MCP, and
two restarts passed before upgrade. The v1.0.4 profile state hashes for account
state, scan registry, and MCP cursor were recorded.

RC2 upgraded the same installation in place. Account state, the scan registry
at the upgrade boundary, and MCP cursor were preserved. The legacy
installation identifier migrated once to a valid UUID and remained stable.
A simulated pre-fix queued event carrying `_delivery_attempts` was delivered
with only the seven canonical wire fields and returned 202.

Production accepted nine upgrade events:

- `desktop_launched`: 4
- `sample_scan_completed`: 1
- `real_repo_scan_completed`: 1
- `graph_opened`: 1
- `impact_completed`: 1
- `mcp_connected`: 1

Four forwarded requests returned 202 with recorded counts 2, 5, 1, and 1.
Diagnostics ended at accepted 10, rejected 0, retries 0, including the
simulated legacy event. Two post-upgrade restarts restored state. Opt-out
persisted and produced zero future analytics requests.

## Production validation matrix

- Unsupported event: HTTP 400, `invalid_event`
- Invalid `event_version`: HTTP 400
- Forbidden top-level repository metadata: HTTP 400
- Oversized metadata: HTTP 400
- Client-provided `is_internal`: HTTP 400
- Malformed installation UUID: HTTP 202, one row recorded — **FAIL**
- Nested metadata object: HTTP 202, one row recorded after server-side
  sanitization — **FAIL**

The sender fix did not broaden the allowlist, sanitizer, event version,
payload limit, or internal-event controls. The production results in this
matrix predate undeployed validation commit `ee5656cd`.

## Production database evidence and cleanup

The final valid RC2 verification produced exactly 17 expected rows:

- Fresh profile: 8
- Upgrade profile: 9

Across those rows:

- Event counts were bounded and matched the expected six-event allowlist.
- Deduplication keys were unique.
- Source was `desktop`.
- App version was `1.0.6`.
- Platform was `windows`.
- Environment was `production`.
- Build commit was `753ddc38a9bccc7010931c7903795280c9091a1a`.
- `is_internal` was false.
- No repository paths, names, filenames, source code, symbols, Graph data,
  Impact paths, account events, Ask events, heartbeat events, UI-render
  events, or `api_me_success` events were present.
- No schema-related HTTP 400 occurred for valid events.
- No valid event produced a validation 400 after the sender fix.

The exact synthetic set contained 31 rows: 17 final valid rows, 12 controlled
diagnostic/harness rows, and the two accepted negative probes. Cleanup matched
exactly 31 rows by the isolated installation identifiers and the two verified
build commits, then deleted exactly 31. Read-only post-cleanup verification
found no rows for the isolated identifiers.

Post-cleanup production invariants:

- `analytics_events`: 1,129
- `analytics_identities`: 36
- `public.users`: 14
- Internal analytics rows: 9
- Approved migration-history rows for version `20260724120103`: 1

No unrelated analytics rows, identities, users, migration history, RLS,
grants, accounts, sessions, billing, entitlements, or non-analytics objects
were changed.

## Local cleanup and public state

All isolated verification profiles, queues, rejected payloads, runtime
descriptors, raw request captures, temporary scripts, temporary repository,
and ignored PyInstaller build cache were removed. Only sanitized evidence,
hashes, the registry backup, and the RC2 artifact remain in the Git-external
private directory. The superseded failed RC was removed.

The original Atlas 1.0.5 uninstall registry entry was restored. The tracked
build, staging, and output trees were restored to the committed baseline.

The live website returned HTTP 200. The public `/download/atlas` route still
returned HTTP 302 to the existing v1.0.4 GitHub release asset. No production
deployment or public installer replacement occurred.

The RC2 installer remains 12,229,183 bytes with SHA-256
`2D53AAD6BB4D48EEBF9DE407DAFE9BE58BF591C05099402941CCA733D8BB5ADA`.
No desktop rebuild was performed. The generated `.next` tree, Playwright
results, local server logs, and route screenshots from the follow-up were
deleted.

## Remaining blockers

1. The required production dependency audit reports two high-severity findings
   through Next's transitive `sharp <0.35.0` dependency. This predeployment
   gate is not green.
2. Server-validation commit `ee5656cd` is intentionally undeployed, so
   production still accepts malformed installation UUIDs and nested metadata.
3. The bounded production negative matrix, one valid control request, exact
   database cleanup, and RC2 post-deployment compatibility check cannot run
   until deployment is authorized by a fully green predeployment gate.

Atlas v1.0.6 remains **NOT READY**. No production behavior or public release
was changed during this follow-up.
