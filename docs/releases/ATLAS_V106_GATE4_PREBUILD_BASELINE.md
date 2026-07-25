# Atlas v1.0.6 Gate 4 pre-build baseline

Date: 2026-07-25

Verdict: **READY TO BUILD V1.0.6 RC**

This is a pre-build verdict only. No v1.0.6 installer was built, installed,
uploaded, tagged, or published. No deployment or production analytics change
was made during this gate.

## Source checkpoints

| Scope | Commit |
|---|---|
| Product/version and analytics RC | `d92aee6f84ef659b2f6551f37cfa350b4b69d4f7` |
| Self-contained copy-review fixture | `9c00ebcd8a4a5d3c11c6d912017681c899588e12` |
| Disable image optimization | `0501e1b5ee0fccc7329b2ecf0b6425e142e348ef` |
| Supported Next/PostCSS security patches | `28a3a7725f34927bb617db6c54ea9649bddae9f4` |
| Isolated support-rescan fixture | `0a3ba57ff2640bba252215c221572d3aed22e62d` |
| Earlier blocked-attempt documentation | `f3f2296c2130b5f238b8f8154c11242270eb744b` |

The release branch and isolated verification worktree were clean at the final
checkpoint. Generated `.next`, `node_modules`, pytest roots, Playwright output,
installer output, and private evidence are not tracked.

## Environment diagnosis and remediation

- The pytest ACL failure was caused by sandbox-created mode-0700 child
  directories receiving explicit Windows ACLs that omitted the restricted
  sandbox identities. The same process then could not use its own temp child.
- Node/npm `spawn EPERM` and Playwright worker startup failure were caused by
  the restricted Codex sandbox's child-process policy.
- The earlier stale `.next` deletion failure was an approval-service usage
  limit, not a repository ACL, path length, Defender, or file-lock defect.
- Repository ownership and inherited ACLs were normal. The checkout is not in a
  protected or synchronized folder. Controlled Folder Access was off. Defender
  had no Atlas block event. No Defender exclusion or broad ACL weakening was
  used.
- Stale Atlas and Node processes were stopped. An isolated clean worktree and
  private temp roots under `C:\J.A.R.V.I.S\.atlas-private\tmp` were used.
  Stale generated paths were removed exactly.

Outside the restricted sandbox, all basic probes passed: Node child process,
Python temp create/delete and subprocess, npm lifecycle script, pytest temp
fixture, Playwright worker, and `.next` create/delete.

## Website reproduction and security

- Node: `24.15.0`
- npm: `11.12.1`
- Clean `npm ci`: passed
- Next: `15.5.21`
- React / React DOM: `19.2.6`
- sharp: `0.34.5`
- Supabase JS: `2.110.8`
- Supabase CLI: `2.109.1`
- PostCSS: `8.5.18`
- Analytics/auth contract tests: 23 passed
- Production build: passed; 42/42 static pages generated
- App path manifest: 62 route entries

The final production audit reports 0 critical and 2 high package nodes. Both
nodes represent the single sharp advisory
`GHSA-f88m-g3jw-g9cj`: sharp `<0.35.0` is affected. The supported Next and
PostCSS advisories were cleared by the smallest compatible patch updates.

The sharp package remains installed because Next 15.5.x declares
`sharp ^0.34.3`, while the advisory fix is 0.35.0. It is not reachable in this
application:

- committed `images.unoptimized=true`;
- generated config confirms image optimization is disabled;
- 216 generated server JavaScript/JSON files contain zero sharp package
  imports/requires;
- a production server reached Ready and served the root with
  `node_modules/sharp` physically absent;
- `/_next/image` returned 404 with sharp absent;
- no sharp load or runtime error appeared.

Therefore there is no remaining **reachable** high-severity path in the
verified website build.

## Desktop reproduction

- Corrected support fixture, focused: 6 passed.
- Release-targeted analytics/privacy/retry/opt-out/packaging set:
  116 passed, 1 skipped.
- Full desktop suite: 1,638 passed, 21 skipped, 0 failed.

Skip classification:

- 19 external-integration skips require the optional Home Assistant checkout;
  six also require `ATLAS_RUN_HA=1`. They do not exercise v1.0.6 analytics or
  packaging behavior.
- `test_phase152_packaging.py::test_dist_layout_when_built` requires a fresh
  `dist/Atlas` tree.
- `test_phase184b_beta_ship_blockers.py::test_installer_generated_version_matches_product`
  requires packaging-generated `generated_version.iss`.

The two packaging checks must run after the authorized RC build. They could not
run in Gate 4 because this task explicitly prohibited building the installer.
No pre-build release-critical assertion was skipped.

## Exact public release identity

Current Vercel production deployment:

- deployment: `dpl_9ji1orenMyZcWNeomoiQZ7eq5pBj`
- source commit: `12bed38574efd4066db930d134f1e1c1166d5205`
- source branch: `release/atlas-v1.0.6-analytics-rc`
- state: Ready

The live download page is internally inconsistent:

- visible version label: `v1.0.5`;
- visible filename: `Atlas_Setup.exe`;
- visible SHA-256:
  `2A1EAA9EEC99311E44496DA04157AD1DB1F60C4373ECD5FFB33D52127CDFFF8A`;
- verify link: GitHub release `v1.0.4`;
- `/download/atlas`: HTTP 302 to the `v1.0.4` `Atlas_Setup.exe`;
- hard-coded size label: 31.7 MB, which matches neither current public
  executable.

The dynamic redirect was a cache miss and still selected v1.0.4. This is source
configuration drift, not a stale CDN redirect.

What users download today is the v1.0.4 executable:

- source commit: `a4782f87e1e0f02129c0cecf8dd2d5711c998013`;
- size: 43,212,710 bytes;
- SHA-256:
  `2A1EAA9EEC99311E44496DA04157AD1DB1F60C4373ECD5FFB33D52127CDFFF8A`;
- file/product version: `1.0.4 (2026-07-16) a` / `1.0.4.0`;
- public release and local publication record agree.

The latest GitHub release executable is v1.0.5-hotfix1:

- public release tag: lightweight `v1.0.5` at
  `d72f6223a9e25b1898c4d0e6c1a0d0ebf9f2505f`;
- hotfix freeze tag: annotated `v1.0.5-hotfix1` at
  `459884c6c89d98eb2aaf7fb33b2815be206b552d`;
- asset size: 43,296,784 bytes;
- SHA-256:
  `B2531078FC814B9D2AA454FAFD31711AE353AAFCD336C6E39D21B4645A9573EF`;
- file/product version: `1.0.5 (2026-07-21) 4` / `1.0.5.0`;
- GitHub digest, downloaded executable, public checksum, public manifest, local
  frozen installer, and hotfix freeze record all agree.

The tracked v1.0.5 manifest on the v1.0.6 branch is the pre-hotfix record:

- desktop commit: `db887f626290d9909266e2f690c805acb7fe10fd`;
- size: 43,294,830 bytes;
- SHA-256:
  `D093D17ABEE5A6B2D8149EAB62D4041AD26BDA387122627B5E7FA76E3001DB53`.

On 2026-07-21 the pre-hotfix public asset was backed up, then the executable,
checksum files, release notes, and manifest under the existing public v1.0.5
release were replaced with the hotfix1 set. The original release tag and
existing freeze tags were explicitly left unmoved. The public manifest records
both the new hotfix identity and the old D093 rollback identity. This explains
the repository/public mismatch without treating the old manifest as current.

## GitHub release artifact inventory

All releases below were public and non-draft at verification time. `v1.0.0-rc`
was the only prerelease.

| Release | Asset | Bytes | GitHub SHA-256 digest | Downloads | Uploaded UTC |
|---|---|---:|---|---:|---|
| v1.0.0-rc | `Atlas_Setup.exe` | 42,098,655 | `2CB3B2AA694AD2A36C026DCD2CED701CAE099852CD66E11721E78E2988A7AD59` | 0 | 2026-07-08 21:30:57 |
| v1.0.0-rc | `Atlas_Setup.exe.sha256` | 81 | `E87C1C9607D174DCD6E75FF48AFF7FCE2CACC981288FEE8A7B82433EA7FA5406` | 0 | 2026-07-08 21:30:57 |
| v1.0.0-rc | `RELEASE_NOTES.md` | 445 | `C76A6169A2BCFB5F24574AAFC589DC9091E8568DCFF9EFB490840B14EB3D7DE8` | 0 | 2026-07-08 16:56:42 |
| v1.0.0 | `Atlas_Setup.exe` | 31,749,938 | `AD1687D5585EE36ABC3F8AE6802E046D1661DF2950982E58B18351C91B2FF82F` | 5 | 2026-07-15 04:17:48 |
| v1.0.0 | `Atlas_Setup.exe.sha256` | 64 | `A2BFB65C88A9E434BAC3787C8BD9944C9C48D73D9C4B659F3B42F7DABC4FCB65` | 0 | 2026-07-15 04:17:48 |
| v1.0.1 | `Atlas_Setup.exe` | 31,694,389 | `93AAC567999B0E3D0AAA30AA6E4FBFC9DCFF605DD35DC1D0E1523F4D066B5649` | 10 | 2026-07-15 06:27:44 |
| v1.0.1 | `Atlas_Setup.exe.sha256` | 64 | `A7F271E314CA35CAD6CA81539090BE6AE87E8FA084BB42CAD03A1D74816C926B` | 1 | 2026-07-15 06:27:44 |
| v1.0.2 | `Atlas_Setup.exe` | 43,207,799 | `1BDE84E27715D2F71406D0231175C65FB820601EC37EAD1B96CDF0ECF61FC465` | 7 | 2026-07-15 18:59:24 |
| v1.0.2 | `Atlas_Setup.exe.sha256` | 64 | `898D206509471D39672C672005A169D74B14DB59D17EF8104BA26438F6F98071` | 0 | 2026-07-15 18:59:24 |
| v1.0.3 | `Atlas_Setup.exe` | 43,212,711 | `93E1EB1F08B39BEB4CFE7A10529D522BFA973EBE124C6C4BAC1952BD13EB1888` | 7 | 2026-07-15 20:47:06 |
| v1.0.3 | `Atlas_Setup.exe.sha256` | 64 | `06E7F8C347CC8E91EEFFF5991D39F4B0BC313E5668D3D49A03F753CB3C419FA2` | 0 | 2026-07-15 20:47:05 |
| v1.0.4 | `Atlas_Setup.exe` | 43,212,710 | `2A1EAA9EEC99311E44496DA04157AD1DB1F60C4373ECD5FFB33D52127CDFFF8A` | 10 | 2026-07-16 13:57:09 |
| v1.0.4 | `Atlas_Setup.exe.sha256` | 64 | `EE2BF2A97A5F9C491CFB18578724E52728AF54820D3FBE00102612067E718460` | 0 | 2026-07-16 13:57:09 |
| v1.0.5 hotfix1 | `Atlas-Setup-1.0.5.exe` | 43,296,784 | `B2531078FC814B9D2AA454FAFD31711AE353AAFCD336C6E39D21B4645A9573EF` | 12 | 2026-07-21 13:31:34 |
| v1.0.5 hotfix1 | `Atlas-Setup-1.0.5.exe.sha256` | 89 | `A52D66BC4ACF552A7099F70EE34A7CE997A4FD0A0D85B81ACD68F4C81762E575` | 1 | 2026-07-21 13:31:34 |
| v1.0.5 hotfix1 | `checksums-v1.0.5.txt` | 88 | `F99787BC85E4C90153EA508E921444EE82A53EED99E5950B4AECBBDB6346EAC0` | 1 | 2026-07-21 13:31:34 |
| v1.0.5 hotfix1 | `release-manifest-v1.0.5.json` | 1,794 | `00136504EF749E9580B421EFC6B3EDAC11FEB149D317B7FDE745A7A726676FD1` | 0 | 2026-07-21 13:34:59 |

The asset digests above are hashes of each named asset. For checksum sidecars,
the digest is the hash of the sidecar file, not a second assertion about the
installer.

## Release/tag matrix

| Label | Tag / current commit | Desktop commit | Website commit | Main executable identity | Public status | Manifest status | Upgrade baseline |
|---|---|---|---|---|---|---|---|
| v1.0.0 RC | `v1.0.0-rc` / `30cba0fe` | `30cba0fe` | not recorded | 42,098,655 bytes / `2CB3…AD59` | Published prerelease | no current freeze used | No |
| v1.0.0 | `v1.0.0` / `47341149` | `47341149` | not recorded | 31,749,938 / `AD16…F82F` | Published | historical only | No |
| v1.0.1 | `v1.0.1` / `c50567e3` | `c50567e3` | not recorded | 31,694,389 / `93AA…5649` | Published | historical only | No |
| v1.0.2 | `v1.0.2` / `f3d864e9` | `f3d864e9` | not recorded | 43,207,799 / `1BDE…C465` | Published | historical only | No |
| v1.0.3 | `v1.0.3` / `d0b9bcbb` | `d0b9bcbb` | not recorded | 43,212,711 / `93E1…1888` | Published | historical only | No |
| v1.0.4 | `v1.0.4` / `a4782f87` | `a4782f87` | `a4a88d4d` publication redeploy | 43,212,710 / `2A1E…FFF8A` | Current website download | public/local publication record agrees | **Yes** |
| v1.0.5 original | `v1.0.5-final` / `db887f62` | `db887f62` | `002d4b09` | 43,294,830 / `D093…DB53` | Retired; local rollback copy only | tracked pre-hotfix manifest | No |
| v1.0.5 hotfix1 | release `v1.0.5` / `d72f6223`; freeze `v1.0.5-hotfix1` / `459884c6` | `459884c6` | `2d5141ed` | 43,296,784 / `B253…73EF` | Current GitHub release asset, not website download | public hotfix manifest agrees | No while website remains v1.0.4 |
| Current website | deployment source `12bed385` | n/a | `12bed385` | label v1.0.5; URL/hash v1.0.4 | Production Ready, internally inconsistent | source config points to v1.0.4 | Selects v1.0.4 |

Additional tags present: annotated `atlas-web-v1.0.5-final` at `002d4b09`
and local-backup tag `atlas-v1.0.0-rc-local-backup` at `1a0f0232`. No evidence
shows a release tag move. The v1.0.5 public **asset set** was deliberately
replaced; the tag was not.

## Recovery plan

1. Before final release, update the website's version, filename, size, SHA,
   verify link, and redirect as one reviewed configuration change. Do not leave
   a v1.0.5 label attached to a v1.0.4 binary.
2. Do not overwrite or retag any existing GitHub release. The public v1.0.5
   hotfix asset is internally consistent and needs no GitHub correction.
3. Preserve the tracked D093 manifest as historical pre-hotfix evidence. Add a
   clearly named current-public/hotfix1 manifest or documented successor; do
   not silently rewrite the historical record.
4. Until the website is intentionally corrected, use the exact public v1.0.4
   installer (43,212,710 bytes,
   `2A1EAA9EEC99311E44496DA04157AD1DB1F60C4373ECD5FFB33D52127CDFFF8A`)
   for the v1.0.6 upgrade test.

## Remaining release work

- Build the v1.0.6 RC only in the next authorized gate.
- Run the two packaging-generated checks.
- Run fresh-profile install, upgrade from the frozen v1.0.4 baseline,
  packet-capture, installed-app analytics, and final-installer verification.
- Correct the public website identity before publication.

These are post-build or pre-publication gates. They do not block creation of
the v1.0.6 RC for verification.
