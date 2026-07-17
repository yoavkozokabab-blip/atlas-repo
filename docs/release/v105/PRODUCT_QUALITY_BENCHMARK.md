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

## 8. Source gate results

(filled at gate completion)

## 9. Installed-candidate results

(filled after the final build and installed acceptance)
