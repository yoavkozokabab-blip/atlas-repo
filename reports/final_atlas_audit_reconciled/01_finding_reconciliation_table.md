# 01 — Finding Reconciliation Table

**Date:** 2026-06-20 · **Mode:** reconciliation (Codex audit = leads, current code = evidence).
**Sources reconciled:** `reports/final_atlas_audit/` (01–17, Codex, 2026-06-20), `ATLAS_1_0_ROADMAP.md`, `reports/phase186/*`. Note: `reports/phase185/` and `reports/final_atlas_audit/` were the requested paths — `phase185/` **does not exist**; `final_atlas_audit/` exists and was read in full.

Classification legend: **CONFIRMED** (reproduced now) · **FIXED** (was true earlier, resolved + verified now) · **STALE** (not reproducible / not a bug) · **UNVERIFIED** (needs runtime/clean-machine) · **OWNER_ONLY** (needs external accounts/hardware).

| # | Finding | Source | Evidence cited | Current code/test path | Verified now | Class |
|---|---|---|---|---|---|---|
| 1 | Website billing stubbed; no production Stripe | 08,14,17 | `_lib/billing.ts:24-56`, `_config.ts:9-11` | `app/_lib/billing.ts`, `app/_config.ts` | Yes — stub confirmed; **intended** for free beta | CONFIRMED (paid-launch blocker; **NOT** a free-beta blocker) |
| 2 | Installer unsigned → SmartScreen | 10,14,17 | no `SignTool` in `Atlas.iss` | `packaging/installer/Atlas.iss` | Yes — no SignTool | CONFIRMED → OWNER_ONLY (cert) |
| 3 | accounts_service rate limit in-process only | 07 | `accounts_service/rate_limit.py:1` | same | Yes | CONFIRMED (low impact: not the website-auth path; website limiter is Supabase-backed) |
| 4 | Two website + two installer surfaces (provenance) | 08,14,17 | `C:\Users\babi2\jarvis_landing`, `installer/jarvis.iss` | both legacy dirs exist | Yes | CONFIRMED (hygiene; canonical = `websites/jarvis-landing` + `packaging/installer`) |
| 5 | Dirty working tree (3,000+ lines) | 14,17 | `git status --short` | data/dist/staging churn | Yes | CONFIRMED (release hygiene; product source is committed) → OWNER decision (gitignore) |
| 6 | Quickstart ships source-mode steps (`cd path/to/local_jarvis`, "install Python") contradicting self-contained installer | 10 | `docs/ATLAS_QUICKSTART.md:7,15` | same | Yes | **FIXED this turn** (rewritten installed-first) |
| 7 | Website 404 on /privacy /terms /contact /download /pricing | older reports | — | `app/{privacy,terms,contact,download,pricing}/page.tsx` | Yes — all 5 exist | FIXED/STALE |
| 8 | Broken links / `href="#"` placeholders | older reports | — | `grep href="#" app/` = 0 | Yes — none | FIXED/STALE |
| 9 | MCP tool "schema drift" from `atlas_root_cause` (18th tool) | 03,11 | `test_mcp_server.py:57-73` | `test_mcp_server.py` uses `assert required.issubset(names)` | Yes — **5 passed**; subset check, 18th tool fine | STALE / NOT-A-BUG |
| 10 | pytest temp-permission failures | 11 (old reports) | old `context_pack_mvp_report.md` | current matrix | Yes — 112 passed, no perm failures | STALE |
| 11 | User-enumeration leak (accounts login) | prior phase | `auth.py:235-237` (old) | `accounts_service/routers/auth.py` generic msg | Yes — fixed earlier, 73 tests | FIXED |
| 12 | In-memory website rate-limit Map (serverless-useless) | prior phase | old `ratelimit.ts` | `app/_lib/ratelimit.ts` Supabase RPC + fallback | Yes | FIXED |
| 13 | Identity fragmentation (desktop local vs website) | prior phase | — | `accounts_client.py` website mode (frozen) | Yes — PYZ-proven in installer | FIXED |
| 14 | Stale installer (predates auth rewire) | prior phase | old build_info `ce5f73805` | `build_info.json` commit `f70a4975e` | Yes — rebuilt, rewire bundled (PYZ extract) | FIXED |
| 15 | Fake/misleading paid CTAs | prior phase | — | `PAID_PLANS_ENABLED` off; `/api/checkout`→403; account/billing "Free beta" | Yes (served HTML earlier) | FIXED |
| 16 | Staged internal phase-labeled files (e.g. `phase128_catalog.py`, quickstart) in installer payload | 10 | `packaging/installer/staging/_internal/...` | same | Yes | CONFIRMED (cosmetic; needs rebuild to drop; not a functional blocker) |
| 17 | Live production website NOT verified | 08,14,17 | no live run | — | Cannot (no deploy) | UNVERIFIED → OWNER_ONLY |
| 18 | Clean-machine install NOT verified | 10,14,17 | no install run | — | Cannot (no VM) | UNVERIFIED → OWNER_ONLY |
| 19 | Claude Desktop live MCP calls NOT verified | 03,14,17 | no client run | smoke 12/12 + 112 tests = **local dev proof only** | Cannot (no client/VM) | UNVERIFIED → OWNER_ONLY |
| 20 | Live security red-team NOT rerun on current build | 07,17 | source-only | strong source posture | Cannot (no live env) | UNVERIFIED → OWNER_ONLY |
| 21 | Benchmark partial / precision-limited; no live agent A/B | 12,17 | `benchmark_context_pack.py:780-782,853` | my `atlas_value_validation_benchmark.md` (honest) + A/B harness (unrun) | Yes — claims already narrow | CONFIRMED-honest (not overstated) |
| 22 | Full current test matrix NOT verified | 11,14,17 | no run in Codex audit | this reconciliation ran it | Yes — **112 passed** (see doc 05) | FIXED/verified now |

**Reconciliation summary:** the Codex audit is recent and honest; it is *not* full of stale findings. The big-picture blockers it names (unsigned installer, billing-stub-for-paid, unverified live/clean-machine/client) are CONFIRMED but are OWNER_ONLY or paid-launch-only. Two specific leads are STALE/not-bugs (MCP "drift", 404 pages). Numerous prior-phase issues are FIXED and verified. Only one code-fixable item existed (quickstart) — fixed this turn.
