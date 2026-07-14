# Atlas Final Product Readiness

Date: 2026-07-15

Candidate worktree: `C:\J.A.R.V.I.S\atlas-private-beta-final`

Candidate branch: `fix/atlas-private-beta-final`

Candidate code HEAD: `335dd758e4e044e681326dad9702bbb6a7e5447b`

Required baseline: `135d93d3488d4d6216018dcdeaa71ec64662d91e`

## Final verdict

**NOT_READY**

The source candidate contains the intended isolation, refresh, MCP-verification,
website persistence, analytics, and release-label fixes. The available focused
evidence is strong, but the release artifact and installed product have not been
rebuilt and verified from the current HEAD. The live website also still serves
the previous installer and its deployed analytics endpoint returns 404. These are
release-provenance and live-product blockers, not cosmetic gaps.

## Repository selection and provenance

The user-named `C:\J.A.R.V.I.S\local_jarvis` checkout is an older, dirty
`public-launch-cleanup` worktree at `ff41925c` and is not the continuation of the
Atlas desktop state around `135d93d3`. It was left untouched. The existing clean
lineage candidate `C:\J.A.R.V.I.S\atlas-private-beta-final` is a descendant of
`135d93d3` and contains the following candidate commits:

| Commit | Change |
|---|---|
| `819a4a2c` | Isolate tests and coordinate refresh state |
| `074b67e2` | Validate clean Atlas worktree lineage in installer tooling |
| `8fd0cb08` | Persist website analytics and enforce shared limits |
| `a471f433` | Align release labels and installer tooling |
| `778ebfdf` | Close desktop and verification-script isolation gaps |
| `335dd758` | Finalize private-beta acquisition flow |

No changes were made to the trading repository, paper loop, Alpaca, broker
state, or trading thresholds.

## Test isolation, timeout, and refresh work

The candidate now applies a mandatory isolated Atlas data root to pytest and to
release/benchmark scripts that can launch scan or analytics subprocesses.

- Each verification run creates a unique writable `ATLAS_DESKTOP_DATA` root.
- Child processes inherit `ATLAS_DESKTOP_DATA`, `JARVIS_DESKTOP_DATA`, test mode,
  and the protected canonical-root marker.
- Test mode refuses to resolve to the canonical user root.
- The accounts-service supervisor fails closed when test-mode isolation is
  missing and overrides inherited `ATLAS_ACCOUNTS_DB` values that point outside
  the isolated root.
- MCP smoke/install proof scripts isolate every child, cover all seven primary
  tools, reject secret leakage, and clean their temporary roots.
- Refresh/request coordination changes from `819a4a2c` remain in the candidate.

Isolation evidence collected in this pass:

| Check | Result |
|---|---|
| Focused desktop isolation/refresh suites | 125 passed, 0 failed |
| Verification-isolation tests | 30 passed, 0 failed |
| Direct hostile inherited-DB check | PASS; DB forced below isolated root |
| Modified Python source AST parse | PASS, 22 files |
| Canonical registry immutability check | PASS |
| Canonical registry SHA-256 | `C86ECBAFA4F7ECF5ECC4F5DBF500C86AE932D37EA66BDC914CCF7A5CA5291D2A` |

## Full Atlas regression suite

The latest complete run executed 1,491 tests:

- **1,469 passed**
- **19 skipped**
- **3 failed**
- 27 warnings
- duration: 24m44s

The three failures were investigated and fixed narrowly:

1. The accounts child preserved an ambient repository-local
   `ATLAS_ACCOUNTS_DB`; test mode now replaces it with a DB below the isolated
   root.
2. Public-copy validation found the internal signup endpoint name in setup
   documentation; the documentation now describes the user-facing Product
   updates form.
3. Recursive public-copy validation found the old `waitlist` component name;
   the component is now `updates-signup`.

Direct checks for all three fixes pass, and website lint/typecheck pass. A full
post-fix rerun could not be executed because the environment's privileged-action
quota was exhausted and the sandbox pytest temp root is ACL-inaccessible. The
last authoritative full-suite result is therefore still the pre-fix 3-failure
run. The full post-fix suite remains a mandatory release gate.

## MCP server and tools

The source MCP server completed a real stdio initialize/list/call proof:

- Protocol: `2024-11-05`
- Server: `atlas-local`
- Version: `0.1.0-beta`
- Advertised tools: 18
- Structured missing-argument error: PASS
- Secret-leak check: PASS

All seven primary product tools passed end-to-end:

1. `atlas_scan_repo`
2. `atlas_get_codebase_map`
3. `atlas_build_context_pack`
4. `atlas_what_breaks`
5. `atlas_plan_change`
6. `atlas_find_file`
7. `atlas_repo_health`

The server also advertises the expected aliases and specialist tools, including
architecture, graph, impact analysis, root cause, repository summary, agent
exports, and health.

This proves the source server. Installed-executable MCP proof must be repeated
after an exact-HEAD installer build.

## Desktop installer and installed-app lifecycle

The installer currently present at
`packaging\installer\output\Atlas_Setup.exe` is **not** a release candidate:

| Property | Current on-disk artifact |
|---|---|
| Embedded build commit | `074b67e2` |
| Candidate source HEAD | `335dd758` |
| SHA-256 | `E659C3D7F4D29A6D589E139C360B72A403306BDA14CFB00A3D3863CD170946EA` |
| Size | 43,208,128 bytes |
| Version | 1.0.0 |

Because the embedded commit differs from current HEAD, no success claim can be
made for current-HEAD installer build, payload byte equality, self-test, clean
install, launch, scan, context pack, MCP setup, persistence, or uninstall.

The release gate requires a clean worktree at `335dd758` (or its report-only
successor), a fresh package and installer, byte-for-byte staged-payload proof,
and a full clean-installed lifecycle. The installed lifecycle must also prove
the Atlas handshake, safe fallback port selection, no Aurora requests, restored
state without a silent rescan, Fresh trust, zero changed files, and working
Home/Memory/Ask/Graph surfaces with no console or network errors.

## Website, signup, download, Supabase, and analytics

### Source candidate

The source candidate now has:

- durable waitlist/signup, desktop account, rate-limit, and analytics adapters;
- shared rate-limit persistence rather than process-local-only limits;
- server-only service-role access;
- RLS enabled with no public table policies;
- public/anonymous/authenticated function execution revoked and service-role
  execution granted;
- numeric migration order documented through `0003`;
- Product updates signup exposed from the roadmap;
- public MCP copy aligned to the seven primary tools;
- stale/internal phase labels removed from visible surfaces covered by the
  recursive copy tests.

Verification completed against the isolated local website backend:

| Flow | Result |
|---|---|
| New signup and persistence | PASS |
| Duplicate signup | PASS |
| Invalid signup | PASS (400) |
| Signup source persistence | PASS (`roadmap`) |
| Analytics accept/persist | PASS (202) |
| Invalid analytics | PASS (400) |
| Desktop account register/session restore | PASS |
| Authenticated download redirect/count | PASS |
| ESLint | PASS, zero warnings/errors |
| TypeScript `--noEmit` | PASS |

A production Next.js build passed before the last website edits. The exact final
website source at `335dd758` still needs a clean production build because the
post-edit build was blocked by the same process-spawn/privileged quota limit.

### Live deployment

Live checks show the deployed site is older than the source candidate:

- Production URL: `https://atlas-repo-chi.vercel.app`
- `/api/health`: 200; Supabase persistence reports healthy.
- Live `/api/analytics`: 404, so the analytics collector is not deployed.
- Live `/download/atlas`: redirects to the v1.0.0 GitHub release asset.
- Live installer SHA-256:
  `23E882490013F5745BB9156FBD6269B3646E470D0065E4705E6D41699AA08554`
- Live installer size: 31,642,721 bytes.
- The live asset traces to the older `5b83d57d` build, not current HEAD.

Migration `0003_analytics_and_rpc_security.sql` has not been proven applied to
the live Supabase project. No deployment, production-data mutation, or public
download replacement was performed in this pass.

## Mandatory remaining gates

1. Run the complete post-fix Atlas suite in an environment with a writable,
   isolated temp root; require zero failures.
2. Build the website production bundle from exact final source; require success.
3. Create a clean release worktree from the final code commit and prove it is
   clean before building.
4. Build the packaged desktop executable and installer from that exact commit.
5. Preserve installer self-test output and prove the staged payload byte-for-byte.
6. Perform clean install, fresh launch, repository scan/context pack, MCP setup,
   persistence/restart, and uninstall verification.
7. Repeat MCP stdio verification against the installed executable, including all
   seven primary tools.
8. Apply and verify the live Supabase analytics/RPC-security migration.
9. Deploy the final website, verify signup/session/analytics persistence, and
   confirm rate limits across instances.
10. Publish the exact verified installer, update the website download target,
    and verify public bytes, size, SHA-256, embedded commit, and download count.

Until all ten gates pass against one immutable commit and one immutable installer
artifact, Atlas is **NOT_READY** for private beta.
