# Atlas v1.0.5 — Final Candidate Artifact Manifest

Built: 2026-07-18 from a fresh detached worktree at the exact final source
commit, with all prior build/dist/staging/installer output deleted first.

| Field | Value |
| --- | --- |
| Final source commit | `d72f6223a9e25b1898c4d0e6c1a0d0ebf9f2505f` |
| Version | 1.0.5 |
| Channel | candidate (public production continues to serve v1.0.4) |
| Build worktree | `C:\J.A.R.V.I.S\atlas-v105-final-build-d72f6223` (detached) |
| Installer | `packaging\installer\output\Atlas_Setup.exe` |
| Installer size | 41.25 MB |
| Installer SHA-256 | `63980A6A7D4C377F08C815C710DC8C56C464387F1E77741C4076D387199EF2B0` |
| Installed Atlas.exe SHA-256 | `A712AF9E48F9FD832E6BB9AD8C3A27F41E9384E000B069CD154769D548EDF1FB` |
| Staged payload size | 118 MB (Atlas.exe + _internal + accounts sidecar + assets) |
| Accounts sidecar | `accounts\AtlasAccounts.exe` (16.13 MB, PyInstaller) |
| Embedded metadata | `build_info.json`: product ATLAS, version 1.0.5, commit d72f6223…, build_date 2026-07-18 |
| Inno defines | MyAppVersion 1.0.5 / MyCommitHash d72f6223… |
| Website bundle | `websites/atlas-web/.next` production build from the same commit (deterministic `npm ci`) |

## Installer content audit

Staged payload top level: `Atlas.exe`, `_internal`, `accounts`, `assets` only.

- No Atlas test files, fixtures, screenshots, logs, JSONL analytics data,
  source maps, or `.env` files in the payload.
- No private user paths embedded in `atlas_desktop` payload files.
- The only "test"-named files are vendored third-party library internals
  (colorama/greenlet self-tests, anyio testing helpers) and `certifi`'s
  public CA bundle (`cacert.pem`) — standard PyInstaller collection.
- Installer self-test passed during staging (launch UX + payload +
  shortcuts + notes).

## Note on post-final-commit repository commits

Commits after `d72f6223` on `launch/claude-v105-completion` contain release
tooling and documentation only (acceptance/soak harnesses, benchmark and
manifest docs). No shipped product source differs from `d72f6223`.
