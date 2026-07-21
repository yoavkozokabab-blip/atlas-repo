# Atlas v1.0.5 — Release Freeze (hotfix1)

**Frozen:** 2026-07-21 (UTC)
**Status:** Public hotfix. Local-only first-run. Frozen for reproducibility, audit, and rollback.

This document records the exact released state of Atlas v1.0.5 after the
local-only first-run hotfix. The installer is **unsigned** (Windows SmartScreen
will warn on first run); verify the SHA-256 below before running.

## Release identity

| Field | Value |
|---|---|
| Desktop version | 1.0.5 |
| Desktop branch | `release/atlas-v1.0.5-hotfix1` |
| Desktop commit | `459884c6c89d98eb2aaf7fb33b2815be206b552d` |
| Website branch | `release/atlas-web-v105-final` |
| Website commit | *(updated with installer identity; see release-manifest)* |
| Public release tag | `v1.0.5` (asset replaced) |
| Desktop freeze tag | `v1.0.5-hotfix1` → `459884c6…` |
| Prior desktop freeze tag | `v1.0.5-final` (unchanged) |
| Website freeze tag | `atlas-web-v1.0.5-final` (unchanged) |
| Installer filename | `Atlas-Setup-1.0.5.exe` |
| Installer SHA-256 | `B2531078FC814B9D2AA454FAFD31711AE353AAFCD336C6E39D21B4645A9573EF` |
| Installer size | 43,296,784 bytes (41.3 MB) |
| Signed | No (unsigned; SmartScreen warning expected) |
| Ask feature | Disabled for launch |
| Accounts UI | Temporarily unavailable (local-only first run) |

## Hotfix notes

First-run accounts are temporarily unavailable in v1.0.5.
Atlas launches directly in local mode with no account required.
Graph, Impact, repository scanning, persistence, and MCP remain available.
The account implementation is preserved for a later update.

Do not claim that Sign In or Create Account is currently available.

## Public URLs

- Public website: https://atlas-repo-wu76.vercel.app
- Public download (CTA): https://atlas-repo-wu76.vercel.app/download → `/download/atlas`
- GitHub release: https://github.com/yoavkozokabab-blip/atlas-repo/releases/tag/v1.0.5
- Direct installer: https://github.com/yoavkozokabab-blip/atlas-repo/releases/download/v1.0.5/Atlas-Setup-1.0.5.exe

## Application identity (from installed `/api/health`)

- version: `1.0.5`
- build_commit: `459884c6c89d98eb2aaf7fb33b2815be206b552d`

## Verification summary (verified on the hotfix installer)

**Automated tests (desktop suite @ 459884c6):** 1609 passed, 19 skipped, 0 failed.

**First-run / accounts:**
- Continue without an account is the primary action
- Sign In / Create Account hidden or disabled
- No red `account_service_unavailable` error
- Neutral note: accounts temporarily unavailable; Atlas works fully in local mode
- Works with port 8779 closed and with Supabase unreachable

**Sample repository (bundled):**
- Scan: 18 files
- Graph: 17 nodes / 24 links
- Impact `services/billing.py`: 8 affected files

**Large repository scan:** completed successfully after >15 seconds

**Restart persistence:** two close/reopen cycles preserve repository state

**Ask disabled:** navigation entry and home composer absent; direct navigation
shows an honest "temporarily unavailable" state

**MCP:** remains available

## Known accepted limitations

- Unsigned installer / Windows SmartScreen warning on first run.
- In-app Ask (repository Q&A) is disabled for this release.
- First-run Sign In / Create Account are temporarily hidden; local mode is primary.
- Uninstall may leave local residue under the install directory.
- Brief (~1 s) trust-chip settling period after a cold start.

## Rollback artifact (previous public build)

If a rollback is required, the immediately-previous public installer identity was:

| Field | Value |
|---|---|
| Installer SHA-256 | `D093D17ABEE5A6B2D8149EAB62D4041AD26BDA387122627B5E7FA76E3001DB53` |
| Installer size | 43,294,830 bytes |
| Desktop commit | `db887f626290d9909266e2f690c805acb7fe10fd` |

A byte-exact copy is preserved under
`Atlas-Releases\_backup-public-v1.0.5-pre-hotfix1-20260721-162723`.

## What changed since the previous public build (db887f62 → 459884c6)

Local-only first-run hotfix: when accounts are unreliable, first-run exposes
local mode as the primary path and does not show broken Sign In / Create Account
controls or a red account-service error. Account implementation is preserved.
Installer identity is otherwise the v1.0.5 line.
