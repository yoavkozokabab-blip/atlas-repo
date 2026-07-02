# 13 — Atlas Retrieval Relevance Investigation (demo/external ranked over production)

**Date:** 2026-06-23. All numbers below are from the **real ranker** (`jarvis_desktop/context_pack.py :: build_context_pack_from_state`) run this session — exact scores, no speculation. Code refs are line numbers in `context_pack.py`.

## The exact scores (task: "remove beta approval completely", scan = `jarvis_desktop`)
| Rank | Score | Penalty(prod-aware) | role | file | why it scored |
|---:|---:|---:|---|---|---|
| 1 | **145.0** | −60 | production_code | `demo/sample_repo/beta.py` | path/name "beta" (+~50) **+ exact filename match (+54)** + symbol `run_beta` |
| 2 | **145.0** | −60 | production_code | `demo/small_repo/beta.py` | same as above |
| 3 | 121.0 | 0 | production_code | `accounts_routes.py` | matched symbols `_validate_beta_profile, accounts_admin_grant_beta, accounts_admin_revoke_beta` + "content mentions approval" |
| 4 | 114.0 | 0 | **unknown** | `static/beta.html` | path/name "beta" + exact filename match + "name related to beta-approval" |
| 5 | 109.0 | 0 | production_code | `accounts_client.py` | matched symbols `admin_grant_beta, admin_revoke_beta, export_beta_users_admin` + content |
| 6 | 105.0 | 0 | production_code | `api.py` | `beta_diagnostics, beta_system_health` + risk hub |

## Q1 — Why were demo repos ranked above production code? (exact, not speculative)
Two additive scoring rules in `context_pack.py` cause it:
1. **Flat +54 "exact filename match" (line 868–870):** when a file's stem equals a task term, it gets +54. `demo/sample_repo/beta.py` (stem `beta` == term `beta`) collects it. The real module `accounts_routes.py` does **not** — its name is descriptive, not the keyword, so it earns only symbol+content points.
2. **Symbol-name match rewards trivially-named symbols (line 840–848):** `def run_beta()` in the demo matches the term `beta` just like `accounts_admin_revoke_beta` does — the ranker can't tell a 2-line fixture from the real admin code.
3. **No ownership penalty for `demo/` (penalty block, line 985–1017):** demo files are classified `role="production_code"` (`_file_role`, line 480–490) and receive **zero** demotion.

Net: `145 (demo) > 121 (production)`. The inversion is driven by the production module having a **descriptive name** that misses the +54 windfall a lucky-named fixture collects. **Confirmation (controlled scan):** when the production target *is* named `approval.py`, it wins (248 vs 219 for vendored copies) — i.e., the bug bites only when production is descriptively named.

## Q2 — Why were external repos ranked above Atlas source? (controlled scan, real scores)
I couldn't reproduce this on the live monorepo (full scan **times out**), so I ran a controlled scan: task "fix the user approval logic", gold = `src/auth/approval.py`, noise = vendored + demo copies named `approval.py`:
```
CURRENT:  248 src/auth/approval.py      | 219 external_repos/otherlib/auth/approval.py
          219 external_repos/somelib/approval.py | 219 packaging/staging/_internal/approval.py
          213 demo/sample_repo/approval.py       | 121 src/auth/session.py   (a real but secondary prod file)
```
The two `external_repos/*/approval.py` files scored **219 each — above the legitimate secondary production file `src/auth/session.py` (121)**. They only lost to the primary because the primary *also* had the name. **`external_repos` is not in `_NOISE_PARTS`** (line 88) so vendored third-party code competes on equal footing with first-party code. With a descriptively-named primary (the real situation), external copies would lead.

## Q3 — Does Atlas understand repository ownership / project boundaries?
**Partially.** It DOES recognize:
- **Tests** (`_is_test_path`, line 431) → routed to "Related tests", −10 for non-test tasks.
- **Docs** (−16), **config**, **vendor/build/cache**: `_NOISE_PARTS` = `{.git,.hg,.svn,.venv,venv,env,node_modules,vendor,dist,build,.next,__pycache__,.tox,.mypy_cache}` → −42 (line 992).
- **Generated/lock**, **.github**, **migrations**, and a **generic-leaf penalty** (≥20 files sharing a stem, line 1003).

It does **NOT** recognize:
- **`demo/`, `sample_repo`, `external_repos/`, `staging/`, `packaging/`, `_internal/`, `.phase*_install_test/`** — none are penalized; demo fixtures are labeled `production_code`.
- There is **no concept of "this repo's own source root vs bundled third-party repos."** A vendored copy of Django/requests is treated as first-party production code.

## Q4 — Should external_repos / demo / staging / packaging / fixtures get penalties?
**Yes — and the benchmark proves it helps with zero regressions.** `external_repos` especially (it is literally other projects). Recommended generic penalties: `external_repos` → exclude (treat as vendored); `demo|sample_repo|examples|samples|fixtures|staging|packaging|_internal|.phase*` → demote (~60). These are project-agnostic (work on any user repo, not just Atlas).

## Q5 — Should production roots (websites/jarvis-landing, jarvis_desktop, accounts_service) get boosts?
**Prefer generic penalties over hardcoded boosts.** Atlas scans arbitrary user repos, so hardcoding Atlas's own paths wouldn't generalize and risks bias. Better: (a) the ownership penalties in Q4 (general), plus optionally (b) auto-detect the **primary source root** (largest owned package excluding vendored/examples/fixtures) and give a small boost. Hardcoding `jarvis_desktop`/`websites/jarvis-landing` would only help Atlas-on-Atlas and is not recommended for the shipped engine.

## Q6 — Benchmark: current vs production-aware ranking (20 maintenance tasks)
Harness: `scripts/bench_production_aware_ranking.py` (drives the real ranker; prod-aware = same candidate set, re-sorted with the Q4 ownership penalty — **pure post-processing, engine unchanged**). Scan = `jarvis_desktop`. Raw: `reports/final_launch_audit/ranking_benchmark_raw.json`.

| Metric | CURRENT | PROD-AWARE |
|---|---:|---:|
| Hit@1 | **55.0%** | **60.0%** |
| Hit@3 | 85.0% | 85.0% |
| Hit@5 | 100.0% | 100.0% |
| File recall@5 | 100.0% | 100.0% |
| Symbol recall | 100.0% | 100.0% (ranking-independent) |

- **No regressions** (Hit@3/5, recall identical → no production file was wrongly demoted).
- The gain is concentrated: of 20 tasks, only **"remove beta approval"** was contaminated within this scan (gold #3 → **#1** under prod-aware). The other 19 were already correct because their production files don't collide with a fixture's filename.
- **This understates the real impact.** This scan has no `external_repos/staging/dist` (they live at the monorepo root, which times out). In a full-monorepo scan, the 20 vendored repos contain many name-colliding files (`auth.py`, `approval.py`, `billing.py`, …) that would flood the top ranks (controlled scan above shows external files at 219 beating a real 121). The full-monorepo Hit@1 gain from ownership penalties would be **larger** than the +5 measured here.

## Precise root-cause statement
Atlas ranks `demo/*/beta.py` and vendored `external_repos/*/approval.py` above descriptively-named production modules because (1) a **flat +54 exact-filename bonus** rewards files whose name literally equals a task keyword — which trivially-named fixtures and vendored files collect but a descriptively-named production module (`accounts_routes.py`) does not — and (2) the penalty stage has **no entry for `demo`/`external_repos`/`staging`/`packaging`** and classifies them as `production_code`. The fix (ownership penalties) raised Hit@1 with zero regressions.

## Disposition (no engine change applied)
Per the standing rule "do not silently change retrieval/ranking unless a failing test proves a regression," I did **not** modify the ranker. The change is small and testable — add the Q4 directories to the penalty block (line 985–1017) and add a regression test asserting `accounts_routes.py` outranks `demo/*/beta.py` for the beta task. I can apply it with that test on request.
