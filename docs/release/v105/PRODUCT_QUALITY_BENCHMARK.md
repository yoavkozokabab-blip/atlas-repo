# Atlas v1.0.5 — Product Quality Benchmark

Date: 2026-07-17 · Branch: `launch/claude-v105-completion`
All numbers below are measured, not asserted. Source machine: Windows 11,
the same machine that produced the prior v1.0.5 measurements.

## 1. Ask answer benchmark (63 questions)

Harness: `benchmarks/ask_quality_benchmark.py` · results:
`benchmarks/ask_quality_results.json`

Corpora: Atlas Demo — Medium, a real Python repository (4,823 .py files on
disk, 3.1 GB tree; identified only in aggregate), a generated JS/TS fixture,
and the two isolation fixtures (repo A / repo B). Includes typo, vague,
incomplete, and unsupported questions.

| Metric | Result |
| --- | --- |
| Total questions | 63 |
| Correct route/intent rate | 88.9% (the remainder are intentionally unsupported/vague questions) |
| Grounded-answer-or-recovery rate | 100% |
| Crash/empty failure rate | 0% |
| Cross-repository leakage | 0 |
| Unknown-mode dead ends | 0 (all offer interpretations or the repository overview) |
| Median response time | 12 ms |
| p95 response time | 790 ms |

Improvements measured against the pre-change engine (same harness):
grounded rate rose from 87.3% → 100%; typo'd questions ("What braeks if I
chnage…") now route correctly; "what changed since my last scan?" gets a
real freshness answer; "biggest blast radius" routes to risk ranking.

## 2. Repository-isolation matrix

Behavior tests: `atlas_desktop/tests/test_v105_repository_isolation.py` (8/8 pass).

| Contract | Result |
| --- | --- |
| Ask/Impact/Plan/Investigate on A never return B artifacts | PASS |
| Same, B → A | PASS |
| Every workflow response carries `context_binding` (repo_id, path, name, demo flag, scan id, scan signature) | PASS |
| Switch invalidates all derived state atomically | PASS |
| Prior-repository results detectably stale after switch (UI discards) | PASS |
| Demo → real clears demo results; real → demo clears real results | PASS |
| Mutated repository fails freshness (stale revisions rejected) | PASS |
| MCP runtime follows the authoritative selected repository | PASS |

In-flight isolation: workflows execute under the state lock server-side; the
UI captures the repository key at request time and discards any response
arriving after a switch (`workflowResponseIsStale`).

## 3. Indexing performance (real repository)

Repository: 4,823 .py files on disk, 3.1 GB tree, 7,248 indexed files,
234 modules, 404 edges. Measured via instrumented `scan_repository` calls.

| Scenario | Before | After | Target | Status |
| --- | --- | --- | --- | --- |
| Cold scan | 56.6 s | **7.9 s** | < 30 s | PASS |
| Unchanged warm scan | 15.5 s | **3.6 s** | < 5 s | PASS |
| One-file incremental | 17.1 s | **7.8 s** | < 8 s | PASS |
| Cancel acknowledgement | — | immediate (flag set without waiting on the scan lock; honored at stage boundaries) | < 1 s | PASS (ack) |

Root causes removed: up to 4 full content-hash signature walks per scan → 1;
a synchronous ~2 s HTTP connect to the accounts telemetry bridge inside the
scan (now a daemon thread); duplicate validate+estimate discovery walks → 1;
five agent-context walks per memory build → 1; millions of tiny JSON writes
→ single serialized write; redundant re-persist of unchanged snapshots
skipped. No traversal-safety, symlink, malicious-repository or isolation
rules were changed (suites re-run green).

Truthful progress: terminal error/interrupted/cancelled states from
420f744d verified by `test_v105_scan_interruption.py`; progress stages map
to real work and never freeze at a mid-stage percent.

## 4. Analytics opt-out verification

Suite: `test_v105_analytics_optout.py` (23 tests) + `test_remote_analytics.py`
+ `test_phase116f_analytics_isolation_hardening.py` + `test_phase186_privacy.py`
— 45 tests pass.

| Contract | Result |
| --- | --- |
| Enabled → event written | PASS |
| Disabled → no local JSONL, no remote enqueue | PASS |
| Disable clears queued unsent events (outbox deleted) | PASS |
| Disabled state survives restart | PASS |
| Direct low-level emitter call blocked | PASS |
| Offline queue bounded (100 events / 256 KB) | PASS |
| Invalid/private payload rejected (allowlist + secret scrub) | PASS |
| Accounts telemetry mirror honors opt-out (fixed this pass) | PASS |
| Corrupt preference file fails closed (fixed this pass) | PASS |
| Product fully usable with analytics unavailable | PASS |

## 5. Free-plan launch behavior

`ATLAS_LICENSING_ENABLED`, `ATLAS_USAGE_ENFORCEMENT`, and
`ATLAS_BILLING_UI_ENABLED` all default off. Desktop feature gates return
None when disabled (licensing suite 8/8). Non-free plans render "Coming
soon". Website checkout is hard-gated by `PAID_PLANS_ENABLED = false`
(returns 503; no transaction path). Paddle stays sandbox/unconfigured.

## 6. Workflow success / regression status (source)

- Impact/quality suites: 58 pass (incl. export regression, first-user UX).
- Ask suites: 89 pass, 6 skipped (documented opt-in slow tests requiring an
  external Home Assistant checkout and `ATLAS_RUN_HA=1`).
- Home/persistence suites: 42 pass.
- Full desktop, accounts, and website gates: see section 8 (run at gate).

## 7. Workflow handoffs and continuity

- Ask → Run Impact / Debug this subsystem / Create change plan.
- Impact → Create change plan (primary) / Copy impact context for agent /
  Investigate highest-risk dependency / Show on map.
- Investigate → per-hypothesis file → Impact.
- Plan → per-step impact (`runBuildImpact`) / copy plan for agent.
- Home recent activity items reopen their workflow view (bounded history,
  100 items per repository, repo-scoped display).
- Copied impact context includes repository display name, pseudonymous
  repo id, and scan revision — never filesystem paths or analytics ids.

## 8. Source gate results (final source commit `d72f6223`)

| Gate | Result |
| --- | --- |
| Desktop + licensing suites | **1,589 passed, 0 failed**, 21 skips (all documented environmental/opt-in: HA checkout, external benchmark repos, junction capability, demo-pack presence) |
| Accounts service suite | **93 passed, 0 failed** |
| Python compileall (atlas_desktop, accounts_service, licensing) | clean |
| JavaScript syntax (all `atlas_desktop/static/*.js`) | clean |
| Website `npm ci` | deterministic, 320 packages |
| `npm audit --omit=dev` | **0 vulnerabilities** |
| TypeScript (`tsc --noEmit`) | clean |
| `next lint` | 0 warnings/errors |
| Production build | clean |
| Full-site QA (21 routes × 2 viewports: console, overflow, links, axe WCAG-AA, screenshots) | **0 failures** |
| Security headers (CSP, HSTS, XFO deny, nosniff, referrer, permissions) | present and correct |
| Analytics contract Playwright spec | **16/16 passed** |
| No weakened security assertions; no tests changed to match broken behavior | confirmed (one label test updated to match *improved* error copy; one QA classifier updated to distinguish deliberate rate-limiting) |

## 9. Installed-candidate results (installer SHA-256 `63980A6A…9EF2B0`)

Acceptance driver: `scripts/v105_installed_acceptance.ps1` → 
`docs/release/v105/INSTALLED_ACCEPTANCE_REPORT.json` — **24/24 PASS**.

| Check | Result |
| --- | --- |
| Clean silent install (isolated dir + data root) | PASS |
| Cold launch → healthy authenticated API | PASS (0.7 s) |
| Version/commit | 1.0.5 @ d72f6223 |
| Guest mode ("Continue without an account") | PASS |
| Demo loads as "Atlas Demo — Medium" (identity consistent across surfaces) | PASS |
| Ask grounded (12 cited files, context binding demo=true) | PASS |
| Impact (8 direct dependents, risk + confidence shown) | PASS (0.2 s) |
| Time to first value (launch → first Impact result) | **0.9 s** (target < 60 s) |
| Debug (high confidence), Plan (ok) | PASS |
| Analytics opt-out set + survives restart | PASS |
| No checkout surface (checkout_enabled=false, payments_active=false) | PASS |
| Restart restores repository | PASS |
| Two-install isolation (distinct instance ids, runtime tokens, independent preferences, no cross-repo visibility) | PASS |
| Update over real v1.0.4 install → 1.0.5, user data dir retained | PASS |
| Installed MCP stdio proof (initialize, 18 tools, scan/map/impact/plan/find/health on demo repo — the exact transport Cursor uses) | **PASS (10/10)** |
| Installer content audit (no secrets/fixtures/logs/private paths) | PASS |
| Installed screenshots (Home, Ask, Impact success + distinct not-found, Debug, Plan, Agents truthfully "Not connected", Settings analytics toggle; footer "Atlas 1.0.5") | captured, verified to show the intended screens |

### 20-minute soak (`docs/release/v105/SOAK_REPORT.json`)

Against the exact final installed candidate, API-driven at ~13 req/s:

| Metric | Result |
| --- | --- |
| Workflow cycles | **15,422** (requirement: ≥ 100) |
| Repository switches (medium ↔ small demo) | 3,085 — zero identity mix-ups |
| Ask requests | 15,422 succeeded, **0 failures** |
| Impact requests | 2,570 succeeded; 2,570 correct "target not in this repository" results while the small pack was active (harness reused a medium-pack path — correct product behavior, not errors) |
| Cancel-scan exercises | 1,542, no wedged state |
| Analytics toggle round-trips | 1,542 |
| RSS | 35.5 MB → 46.7 MB (peak ~49.6, plateaued — no runaway growth) |
| Handles | 183 → 202 (stable) |
| Crashes / hangs / dead API windows | none |

Honest caveat: the harness's one mid-soak restart never triggered (a
condition bug in the soak script itself, `now > now` never true). Restart
recovery is separately proven by the acceptance run
(restart_restores_repository, opt_out_survives_restart) and by the
interruption test suite.

### Honestly not proven in this pass
- **Live Cursor UI session** (card flip to "Connected" from a real Cursor
  process): not re-executed. The installed exe's MCP stdio transport — what
  Cursor actually spawns — passed 10/10; the Agents screen truthfully shows
  "Not connected" with no client running.
- Manual visual audit at 125%/150% display scaling and the full 16-shot
  desktop matrix (P2): deferred post-launch; automated axe/responsive checks
  on the website are green.
- Claude Code / Codex live proofs: not executed (not claimed).
