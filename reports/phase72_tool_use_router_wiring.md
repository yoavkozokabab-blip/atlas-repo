# Phase 72 — Tool-Use Router Wiring (completion report)
**Date:** 2026-05-29
**Branch:** `phase72-tool-use-router-wiring` (from `phase71-tool-use`)
**Goal:** Make the Phase 71 tool-use foundation reachable through the normal JARVIS command pipeline, safely — bounded, read-only, human-approved, fully audited, no mock success.

Implements `reports/phase72_tool_use_router_wiring_plan.md`.

---

## Hard constraints — how each is met

| # | Constraint | Implementation |
|---|------------|----------------|
| 1 | Only the 3 approved commands | `plan tool task <goal>`, `run tool task <goal>` / `research <goal>` / `look up <goal> and summarize`, `show last tool run` — matched by anchored regex in `brain/intent_classifier.py::match_tool_use_command`, run first in `classify()`/`classify_rules()`. No other tool-use command exists. |
| 2 | No desktop control | Only the browser provider is used; no `computer_control`/desktop paths. |
| 3 | No payments/orders/bookings/logins/submits/downloads/deletes/sends | Planner raises `ForbiddenGoalError` (`scan_forbidden`) → action returns `BLOCKED` + audits, before any provider is built. |
| 4 | No mock provider success | Execution uses `PlaywrightBrowserProvider` (no mock branch). Unavailable provider → `RunStatus.BLOCKED_UNAVAILABLE` → action returns `ActionStatus.BLOCKED`, never SUCCESS. |
| 5 | No wake-word one-shot execution | `run_tool_task` is two-phase: first call only returns `CONFIRMATION_REQUIRED`; execution needs an explicit "yes". Not added to any auto/voice fast-lane. |
| 6 | No tray exposure | No entry added to `ui/tray_app.py` `TRAY_MENU_COMMANDS`. |
| 7 | No autonomous loops | One goal → one bounded 4-step plan → stop. |
| 8 | Don't modify `browser/runtime.py` / `phase62_browser_actions.py` | Untouched (verified — not in the diff). The new route uses the isolated Phase 71 `tooluse/` provider. |
| 9 | Pinned-plan approval (previewed == executed) | First call builds the plan and **pins it by confirmation id** (`tooluse/pending.py`); "yes" loads that exact plan via `request.confirmation_id` and executes it. Test `test_approved_pinned_plan_is_what_runs` asserts the executed step sequence equals the pinned plan's. |
| 10 | Audit to `data/tool_use_audit.jsonl` | `tooluse/audit.py` (RotatingJSONLWriter) writes one record per run with per-step status/verification/url/screenshot + `plan_hash`; blocked attempts recorded too. |

---

## Design decision (deliberate deviation from the plan's mechanism)

The plan suggested adding `RUN_TOOL_TASK` to `CONFIRMATION_REQUIRED_INTENTS`. That router gate fires **before** the action and emits a generic message — it cannot show the plan, and it would build the plan *after* approval, breaking "previewed == executed". Instead the **action manages its own confirmation**: it builds + pins the plan, then returns `CONFIRMATION_REQUIRED` whose body is the full `ActionPlan.format()` preview. On "yes", the router's existing confirm flow (`_handle_confirmation_yes`) re-dispatches `run_tool_task` with `confirmed=True` and the same `confirmation_id`, and the action executes the pinned plan. This satisfies hard-constraint #9 exactly. `RUN_TOOL_TASK` is therefore intentionally **not** in `CONFIRMATION_REQUIRED_INTENTS`.

Also deviated (for safety, no regressions): browser-agent `health_check` was **not** modified to require Playwright (it would risk gating existing browser intents). The executor's `BLOCKED_UNAVAILABLE` already guarantees no-mock-success; `run_tool_task` routes to `AgentId.BROWSER` (health-gated by the existing browser check), while `plan_tool_task`/`show_last_tool_run` route to `AgentId.EXECUTIVE` so the read-only commands are never gated.

---

## Execution flow (real)

```
user: "research python 3.13 release notes"
  -> classify -> RUN_TOOL_TASK (goal captured)
  -> RunToolTaskAction.execute(confirmed=False)
       build dry-run plan (forbidden-goal check) -> pin by cid
       return CONFIRMATION_REQUIRED (full plan preview + safety banner)
user: "yes"
  -> router._handle_confirmation_yes -> re-dispatch run_tool_task confirmed=True, confirmation_id=cid
  -> RunToolTaskAction.execute(confirmed=True)
       load pinned plan by cid
       ToolUseExecutor(real provider, approve_all).run(plan)   # observe->act->verify->recover
       audit run -> set_last_run -> return TaskRun.format()
```

---

## Files changed

**Modified (existing):**
- `core/types.py` — added `Intent.PLAN_TOOL_TASK`, `RUN_TOOL_TASK`, `SHOW_LAST_TOOL_RUN`.
- `config.py` — added the 3 to `ALLOWED_INTENTS` and `IMPLEMENTED_INTENTS`.
- `brain/intent_classifier.py` — added `match_tool_use_command` (anchored, param-capturing) + called first in `classify()` and `classify_rules()`.
- `actions/registry.py` — registered the 3 new actions.
- `agents/intent_routing.py` — routed `run_tool_task`→BROWSER, `plan_tool_task`/`show_last_tool_run`→EXECUTIVE.

**Added (new):**
- `actions/tool_use_actions.py` — `PlanToolTaskAction`, `RunToolTaskAction`, `ShowLastToolRunAction` + provider-factory injection seam.
- `tooluse/pending.py` — pinned-plan + last-run store (in-process).
- `tooluse/audit.py` — `data/tool_use_audit.jsonl` writer.
- `tests/test_phase72_router_wiring.py` — 12 tests.
- `scripts/smoke_phase72_router_tool_use.py` — no-network / real / forbidden router smoke.
- `reports/phase72_tool_use_router_wiring.md` — this report.

**Not touched (as required):** `browser/runtime.py`, `actions/phase62_browser_actions.py`, `ui/tray_app.py`, and the Phase 71 `tooluse/{contracts,planner,provider,verifier,recovery,executor}.py`.

---

## Tests

`py -m pytest tests/test_phase72_router_wiring.py -v` → **12 passed**. Covering every required case:
- intent classification (3 commands + goal capture + non-hijack)
- preview-only command does not execute (provider never constructed)
- run requires confirmation (CONFIRMATION_REQUIRED, plan pinned, not executed)
- forbidden goals block before execution (+ blocked record audited) — parametrized buy/book/login
- mock/unavailable provider cannot report success (BLOCKED, not SUCCESS)
- approved pinned plan is exactly what runs (executed steps == pinned steps)
- audit log includes per-step verification/status (+ plan_hash provenance)
- show last tool run is read-only (no provider built)

Deterministic (injected fake provider, no network).

## Smoke

- `py scripts/smoke_phase72_router_tool_use.py --no-network` → **SMOKE PASS** (CI-safe; full router path with fake provider).
- `py scripts/smoke_phase72_router_tool_use.py --real --query "wikipedia python programming language"` → **SMOKE PASS** (real headless: searched → opened discuss.python.org → summarized 2913 chars, all through CommandRouter + confirmation).
- Forbidden-goal block is asserted inside both modes ("book a hotel" → BLOCKED).

Honesty note (same as Phase 71): the `--real` smoke depends on a live search engine and can transiently report `FAILED` (e.g. `net::ERR_ABORTED` navigating a result, or a single thin result set). That is reported truthfully and exits non-zero — it is never counted as success. The `--no-network` mode is the deterministic gate.

---

## Definition of done — status
1. 3 commands reachable through the router — ✅
2. `run_tool_task` cannot execute without confirming a previewed, pinned, read-only plan — ✅
3. Forbidden goals blocked at action time + audited — ✅
4. No mock-success path; unavailable provider → BLOCKED — ✅
5. Runs and blocked attempts recorded in `tool_use_audit.jsonl` — ✅
6. Deterministic unit tests pass; real router smoke succeeds and reports honestly on transient failure — ✅
7. No new autonomy: no per-utterance auto-run, no tray entry, no loops, no committing actions — ✅
