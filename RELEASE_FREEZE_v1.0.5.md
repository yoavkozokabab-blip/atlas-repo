# Atlas v1.0.5 — Release Freeze

**Frozen:** 2026-07-21 (UTC)
**Status:** Final public build. Frozen for reproducibility, audit, and rollback.

This document records the exact released state of Atlas v1.0.5. The installer is
**unsigned** (Windows SmartScreen will warn on first run); verify the SHA-256
below before running.

## Release identity

| Field | Value |
|---|---|
| Desktop version | 1.0.5 |
| Desktop branch | `release/atlas-v1.0.5-final` |
| Desktop commit | `db887f626290d9909266e2f690c805acb7fe10fd` |
| Website branch | `release/atlas-web-v105-final` |
| Website commit | `002d4b0972286312ddfb4fb1cc780ae58029b622` |
| Public release tag | `v1.0.5` |
| Desktop freeze tag | `v1.0.5-final` → `db887f62…` |
| Website freeze tag | `atlas-web-v1.0.5-final` → `002d4b09…` |
| Installer filename | `Atlas-Setup-1.0.5.exe` |
| Installer SHA-256 | `D093D17ABEE5A6B2D8149EAB62D4041AD26BDA387122627B5E7FA76E3001DB53` |
| Installer size | 43,294,830 bytes (41.3 MB) |
| Signed | No (unsigned; SmartScreen warning expected) |
| Ask feature | Disabled for launch |

## Public URLs

- Public website: https://atlas-repo-wu76.vercel.app
- Public download (CTA): https://atlas-repo-wu76.vercel.app/download → `/download/atlas`
- GitHub release: https://github.com/yoavkozokabab-blip/atlas-repo/releases/tag/v1.0.5
- Direct installer: https://github.com/yoavkozokabab-blip/atlas-repo/releases/download/v1.0.5/Atlas-Setup-1.0.5.exe

## Application identity (from installed `/api/health`)

- version: `1.0.5`
- build_commit: `db887f626290d9909266e2f690c805acb7fe10fd`

## Verification summary (verified on the public CTA-downloaded installer)

**Automated tests (desktop suite @ db887f62):** 1599 passed, 19 skipped, 0 failed.
(The 19 skips are environmental — an external Home Assistant repository is not
present on the build machine.)

**Sample repository (bundled):**
- Scan: 18 files
- Graph: 17 nodes / 24 links
- Impact `services/billing.py`: 8 affected files

**Large real repository (scan-disconnect fix):**
- Repository: a 3.2 GB / ~49,540-file real project
- Scan: completed to SUCCESS (7248 files indexed, massive/sampled mode)
- Duration: ~39 s — ran well past the old 15 s client abort with **no** false
  "Atlas lost contact with the local runtime" failure and **no** "Atlas stopped
  responding" banner
- Graph: 234 nodes / 404 links
- Impact on a real hub: 31 affected files
- Repository identity: top bar and sidebar agreed throughout (no contradictory
  "repository name + No repository" state)

**Restart persistence:** two close/reopen cycles — repository restored, 0 changed
files, fresh; "Repository ready" and "Memory current" shown; no "No repository",
no "Repository needs refresh", no "Full rescan required".

**Ask disabled:** navigation entry and home composer absent; direct navigation
shows an honest "temporarily unavailable" state; no public surface advertises
in-app Ask as available.

## Known accepted limitations

- Unsigned installer / Windows SmartScreen warning on first run.
- In-app Ask (repository Q&A) is disabled for this release.
- Uninstall may leave local residue under the install directory.
- The local account helper can fail to reach its service on some machines
  ("account_service_unavailable"); the prominent "Continue without an account"
  local path is unaffected and works.
- Brief (~1 s) trust-chip settling period after a cold start.

## Rollback artifact (previous public build)

If a rollback is required, the immediately-previous public installer identity was:

| Field | Value |
|---|---|
| Installer SHA-256 | `24E0BD8169E1ADC9868CB7EAEE311B108E4463280C52A54CF523A3F81C3399F6` |
| Installer size | 43,294,766 bytes |
| Desktop commit | `ffa7152af471430e6932514ca1fd87dd4d61178b` |

A byte-exact copy of that previous installer is preserved in the local release
archive alongside this freeze.

## What changed since the previous public build (ffa7152a → db887f62)

Single fix: large-repository scans no longer false-fail as a runtime disconnect.
The scan request now uses a long client timeout (so a healthy multi-minute index
is governed by the progress + cancel controls, not a premature 15 s transport
abort), and repository labels reconcile to one consistent state on any scan
failure. Frontend-only; installer identity is otherwise the v1.0.5 line.
