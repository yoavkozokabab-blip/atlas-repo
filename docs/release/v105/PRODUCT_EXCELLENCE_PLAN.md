# Atlas v1.0.5 — Product Excellence Plan

Date: 2026-07-17
Branch: `launch/claude-v105-completion`

## 0. Recovery snapshot (recorded before any edit)

| Item | Value |
| --- | --- |
| Current branch | `launch/claude-v105-completion` |
| HEAD at recovery | `d1e37bd8` — feat(analytics): authoritative desktop opt-out with Settings toggle |
| Prior green source commit | `420f744d` (ancestor of HEAD — included) |
| Analytics opt-out commit | `d1e37bd8` (is HEAD — included) |
| Worktree | clean except untracked `websites/atlas-web/test-results/` |
| Running suites/builds | none found at recovery |
| Latest installer | `installer/output/Atlas_Setup.exe`, built 2026-07-17 13:49, SHA-256 `b98ca5e5edbd…6cbc6` |
| Installer includes d1e37bd8? | **No** — installer predates 420f744d (17:38) and d1e37bd8 (18:21). Final rebuild required. |
| Installed process on older build | Yes — a v1.0.4 `Atlas.exe` from `atlas-v105-update\v104app` (update-test leftover) was running; terminated. |
| Other terminated processes | leftover `accounts_service.main` (test companion), stale `next start -p 3015` from `atlas-codex-core-analytics-v105` worktree |
| Preserved processes | unrelated algo-trading Python, Codex node runtime, `node ./mcp/server.mjs` (possibly a live agent connection) |
| Current public version | 1.0.4 |
| Current candidate version | 1.0.5 (`atlas_desktop/product_info.py: PRODUCT_VERSION = "1.0.5"`) |

## Finding ranking

### P0 — trust, data isolation, security, crash, unusable workflow
1. **Repository context isolation is unproven.** No behavior-level A/B fixture tests exist
   (`unique_a_symbol` fixtures absent). Prior sessions fixed pieces; nothing proves Ask/Impact/
   Debug/Plan/MCP can never serve results from repository B (or Demo) under repository A,
   nor that in-flight results are discarded on switch.
2. **Indexing performance.** Frozen-68% terminal-state bug fixed at source (420f744d), but a
   real-repository cold scan took ~65.9 s for 202 relevant files. Stage timing, traversal
   pruning, and warm/incremental paths need measurement and correction.
3. **Analytics opt-out authority.** d1e37bd8 landed; must audit every emit path (local JSONL,
   remote, low-level emitter), queue clearing, restart persistence, and pre-load emission.
4. **Free plan must not dead-end.** Licensing exists under `licensing/`, flag-gated. Verify
   `ATLAS_LICENSING_ENABLED` defaults off, no limit → disabled-payment dead end, Pro stays
   "Coming soon", checkout cannot transact.
5. **Latest installer is stale** — predates both P0 fix commits. One final rebuild at the end.

### P1 — activation, answer usefulness, speed, continuity
6. Ask answer anatomy and robustness (typos, vague wording, plain-language metrics,
   calibrated confidence, useful follow-ups) + ≥30-question benchmark.
7. Impact presentation: summary sentence, dependents/tests/risk sections, "Copy impact
   context for agent", distinct empty/error states.
8. Workflow handoffs (Ask ↔ Impact ↔ Debug ↔ Plan) carrying repository_id + scan revision.
9. Continuity: bounded recent history, "Continue where you left off", restart restoration.
10. Time to first value < 60 s from clean install; onboarding text reduction.
11. Website: simplify primary nav to Product / How it works / Integrations / Security /
    Download; homepage 5-second comprehension; no fabricated proof.
12. Error-state audit: what happened / was data lost / what next, for all major failures.
13. Performance beyond indexing: launch, navigation, cached answers, memory growth.

### P2 — visual polish, copy, convenience (only after P0/P1)
14. Desktop hierarchy/density audit at 1280×720 → 1920×1080, 125%/150% scaling.
15. Ask readability (answer column width, metadata weight, "Signal" label cleanup).

## Execution order
1. P0 items 1–4 with behavior tests → scoped commits.
2. P1 items 6–13 in impact order, time-boxed.
3. Source gate: full desktop + website + accounts suites.
4. One final build from the final source commit in a fresh detached worktree.
5. Installed acceptance + soak as feasible; honest final report.

Constraints honored: no publish/push/tag/production deploy, payments stay disabled,
public v1.0.4 downloads untouched, no engagement dark patterns.
