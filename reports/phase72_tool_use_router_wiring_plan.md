# Phase 72 — Tool-Use Router Wiring Plan (PLAN ONLY — no code)
**Date:** 2026-05-29
**Goal:** Make the Phase 71 real tool-use foundation reachable through JARVIS's normal command pipeline **without exposing unsafe autonomy**. Bounded, read-only, human-approved, fully audited. No payments/orders/bookings/submits/logins/downloads/deletes/sends.

This document is a design specification. It implements nothing.

---

## 0. Constraints carried forward from Phase 71

- The `tooluse/` package already guarantees: dry-run planning, forbidden-action rejection (`scan_forbidden`), real-provider-required (no mock success), per-step verification, bounded recovery, and an injected `approver` gate (`deny_all` by default).
- Phase 72 adds **only** the wiring to invoke that loop from the router. It must not weaken any Phase 71 guarantee.

---

## 1. How Phase 71 becomes reachable from the router/intent system

### 1.1 The core tension
`brain/router.py` is **single-shot with one confirmation round-trip**: `route(text)` → `classify` → `validate_intent` → (optional) one `CONFIRMATION_REQUIRED` reply → on "yes" the same intent re-runs with `request.confirmed=True` → `registry.execute` → `_finalize` (logging/audit). The Phase 71 executor wants *per-step* approval. The router has a **single-slot** confirmation (`core/confirmation.py`).

### 1.2 Phase 72 approval model: **plan-level approval** (v1)
Reconcile the two by collapsing per-step approval into **one plan-level approval of a fully-previewed dry-run plan**:

1. User issues a tool-task command.
2. The action builds the Phase 71 dry-run `ActionPlan` (nothing executes) and stores it keyed by a confirmation id.
3. The router returns `CONFIRMATION_REQUIRED` whose body is the **complete plan preview** (every step, which are external, success criteria, and an explicit "this opens a real browser and visits external pages; read-only; no purchases" statement).
4. On `yes/confirm/כן`, the action re-runs (`confirmed=True`), loads the **exact previewed plan** (so "what you approved is what runs"), and executes it with an `approve_all` approver — i.e. the human approved the whole plan once.
5. On `no/cancel`, nothing executes.

This reuses the existing confirmation gate verbatim and stays safe because: the plan is fully shown before approval, only read-only step kinds can appear, and forbidden goals never produce a plan at all.

> **Tradeoff (documented, not hidden):** v1 is plan-level approval, not per-step interactive approval. True per-step confirmation requires a stateful multi-turn tool-use session the router does not natively support. That is **Phase 73+** (a `ToolUseSession` driving multi-turn confirmation). v1 is safe because the surface is read-only and the full plan is previewed and pinned before any execution.

### 1.3 New intents (three, all narrow)
Add to `core/types.py::Intent`:
- `PLAN_TOOL_TASK = "plan_tool_task"` — preview only, **zero** execution, **no** approval needed.
- `RUN_TOOL_TASK = "run_tool_task"` — execute the bounded read-only task, **CONFIRMATION_REQUIRED**.
- `SHOW_LAST_TOOL_RUN = "show_last_tool_run"` — read-only display of the last `TaskRun` + audit.

### 1.4 Agent ownership
Route all three to `AgentId.BROWSER` in `agents/intent_routing.py` (reuse; no new agent). `agents/runtime_wiring.py` already health-gates BROWSER. **Add** a Playwright-availability signal to the browser health check so that if Playwright/Chromium is unavailable the gate blocks `RUN_TOOL_TASK` early (consistent with no-mock-success; the executor would return `BLOCKED_UNAVAILABLE` anyway, this just surfaces it sooner). `PLAN_TOOL_TASK` and `SHOW_LAST_TOOL_RUN` are read-only diagnostics and must remain runnable even when the provider is unhealthy (they match the existing `_status`/diagnostic exemption pattern, or are simply not health-gated).

### 1.5 Pinned-plan store
Add a tiny in-process store (e.g. `tooluse/pending.py`) mapping `confirmation_id → ActionPlan` and `last_run → TaskRun`. Guarantees the executed plan equals the previewed plan and backs `SHOW_LAST_TOOL_RUN`. In-process only, not persisted, no secrets.

---

## 2. The first 3 allowed user commands (and ONLY these)

| # | Command (phrasings) | Intent | Behavior | Risk | Approval |
|---|---------------------|--------|----------|------|----------|
| 1 | "plan tool task `<goal>`" / "preview web task `<goal>`" | `PLAN_TOOL_TASK` | Build + show the dry-run plan. Executes nothing. | none | none |
| 2 | "run tool task `<goal>`" / "research `<goal>`" / "look up `<goal>` and summarize" | `RUN_TOOL_TASK` | Bounded read-only **search → open most relevant result → summarize**. | external (read-only) | **required (plan-level confirmation)** |
| 3 | "show last tool run" / "show last web task" | `SHOW_LAST_TOOL_RUN` | Display the last `TaskRun` (per-step status, verification, URLs, summary) from the pinned store. | none | none |

Notes:
- Command 2 is the ONLY one that executes anything external, and only the Phase 71 `build_search_open_summarize_plan` shape.
- Phrasings must be **distinct** from existing browser intents (`search_web_for`, `find_information_about`, `summarize_this_page`) to avoid hijacking them. Use the explicit `tool task` / `research` / `look up … and summarize` triggers; verify no overlap in `brain/intent_classifier.py` rules.

---

## 3. Commands that MUST stay blocked

The classifier/action layer must refuse (return `BLOCKED` with explanation, never execute):

1. **Any goal flagged by `scan_forbidden`** — buy, purchase, order, checkout, book, booking, reserve, submit, login/sign-in, download, delete, send, transfer, subscribe, add-to-cart, place/confirm order. (Planner already raises `ForbiddenGoalError`; the action maps it to `BLOCKED`.)
2. **Interactive/committing web actions** — fill, click-submit, type-into-form, accept-cookies-then-act, file upload. Phase 71 emits no such steps; Phase 72 must not add them. (`FILL`/`CLICK` are Phase 74, non-committing only, behind stricter gates.)
3. **Desktop/native-app tool use** via this path (Phase 72 is browser-only). Desktop provider is Phase 73.
4. **Autonomous multi-site chains / loops** — one goal → one bounded plan → stop. No "keep going until done" autonomy.
5. **Wake-word one-shot execution** — `RUN_TOOL_TASK` must NOT execute from a single wake-word utterance without the confirmation round-trip. No tray-menu entry for `RUN_TOOL_TASK`.
6. **Money/account/credential surfaces** — anything touching payment pages, auth forms, or stored credentials is forbidden regardless of phrasing.
7. **Provider downgrade** — if a real provider is unavailable, the run returns `BLOCKED_UNAVAILABLE`; it must never silently fall back to a mock or to the legacy mock-prone `browser/runtime.py`.

---

## 4. Approval UX

1. **Preview-first.** `RUN_TOOL_TASK` first returns `CONFIRMATION_REQUIRED` with the full dry-run plan via `ActionPlan.format()`, plus a fixed safety banner:
   > "This will open a REAL browser and visit external web pages. Read-only: it will not log in, submit forms, buy, book, order, or download. Reply yes/confirm to proceed, no/cancel to abort."
2. **Single confirmation** through the existing `core/confirmation.py` slot and `CONFIRM_PHRASES`/`CANCEL_PHRASES` (yes/confirm/כן · no/cancel/לא). Honors `CONFIRMATION_TIMEOUT_SECONDS`.
3. **Pinned plan.** The text shown is exactly what executes (loaded from the pending store by `confirmation_id`).
4. **Progress surfacing.** During execution, push non-blocking overlay notifications per step ("Web task 2/4: search", "3/4: opened example.com") and console lines. Reuse `ui/overlay_app.notify_*`. No blocking prompts mid-run (v1 = plan-level approval).
5. **Outcome.** Final reply is `TaskRun.format()` (per-step status + verification + the page summary). On `BLOCKED_UNAVAILABLE`/`FAILED`, state plainly that nothing was completed — never imply success.
6. **Voice mode.** Same confirmation gate applies; recommend `RUN_TOOL_TASK` be confirmed in text or via explicit spoken "confirm". Never auto-run from wake word.

---

## 5. Logging / audit requirements

1. **Command-level (existing path).** `RUN_TOOL_TASK` flows through `router._finalize` → `command_history.jsonl` (rotating) + `diagnostics.command_audit`. Ensure the new `agent_id` metadata (from `agents/runtime_wiring`) is present. (Also fixes the open caveat that `agent_id` isn't yet in the structured log line.)
2. **Dedicated tool-use audit.** New append-only `data/tool_use_audit.jsonl` via `core/rotating_jsonl.RotatingJSONLWriter` (e.g. 5 MB × 5). One record per run:
   - `ts`, `goal`, `intent`, `confirmation_id`, `approved` (bool + phrase), `provider_real` (bool),
   - `steps`: list of `{kind, status, verification_ok, verification_reason, recovery_attempts, url, screenshot_path}`,
   - `final_status`, `summary_excerpt`, `duration_ms`.
3. **Blocked/forbidden attempts are audited too** (goal + reason), so refusals are observable.
4. **No secrets.** Read-only flow has no credentials; assert no form values/cookies are logged. Respect existing `command_audit` redaction.
5. **Pinned-store provenance.** Record that the executed plan hash equals the previewed plan hash (proves "approved == executed").

---

## 6. Test plan and smoke plan

### 6.1 Unit tests — `tests/test_phase72_router_wiring.py` (no network; inject a fake provider)
- **Classification:** each of the 3 allowed phrasings classifies to the correct intent; existing browser intents are NOT hijacked.
- **Dry-run safety:** `PLAN_TOOL_TASK` returns a plan and constructs **no** provider / executes nothing.
- **Confirmation gating:** `RUN_TOOL_TASK` is in `CONFIRMATION_REQUIRED_INTENTS`; first call → `CONFIRMATION_REQUIRED` with plan preview; on confirm → executes with injected **fake** provider → SUCCESS; on cancel → no execution.
- **Pinned plan:** the executed plan equals the previewed plan (hash match).
- **Forbidden goals:** "book a hotel", "buy …", "log in …", "order groceries" → `BLOCKED`, never executed, audited.
- **No mock success:** fake provider with `is_real()=False` → `BLOCKED_UNAVAILABLE`, status not success.
- **Audit:** a `tool_use_audit.jsonl` record is written with per-step detail on run; blocked attempts are recorded.
- **Startup invariants:** new intents are in `IMPLEMENTED_INTENTS ⊆ ALLOWED_INTENTS`; `validate_intent_coverage` finds handlers for all three.
- **Agent routing:** all three → `AgentId.BROWSER`; `agent_id` metadata attached to results.
- **Provider injection seam:** the action accepts an injected provider/approver for tests (default = real provider + confirmation-derived approver in production).

### 6.2 Smoke — `scripts/smoke_phase72_router_tool_use.py` (end-to-end through `CommandRouter`)
- Drive real text through the router (not the executor directly):
  1. `route("research python 3.13 release notes")` → expect `CONFIRMATION_REQUIRED` + plan preview.
  2. `route("yes")` → real headless run → expect `SUCCESS` with a real summary (no mock).
  3. `route("book a hotel in paris")` → expect `BLOCKED` (forbidden), nothing executed.
  4. `route("show last tool run")` → expect the prior run's structured result.
- Honest exit codes: live-search transient failure reports `FAILED`/blocked, never a faked pass (same contract as Phase 71 smoke). A `--no-network` mode uses the fake provider to validate the router path deterministically in CI.

---

## 7. Files that would likely change (impact map)

**Modify (existing):**
- `core/types.py` — add `PLAN_TOOL_TASK`, `RUN_TOOL_TASK`, `SHOW_LAST_TOOL_RUN` to `Intent`.
- `config.py` — add the three to `IMPLEMENTED_INTENTS` and `ALLOWED_INTENTS`; add `RUN_TOOL_TASK` to `CONFIRMATION_REQUIRED_INTENTS` (around `config.py:1404`).
- `brain/intent_classifier.py` (and whatever phrase/rules tables it consults) — add narrow triggers for the 3 commands; verify no collision with `search_web_for`/`find_information_about`/`summarize_this_page`.
- `actions/registry.py` — register the 3 new action handlers in `_register_defaults`.
- `agents/intent_routing.py` — map the 3 new intents to `AgentId.BROWSER`.
- `agents/registry.py` — extend the BROWSER `health_check` to also report Playwright availability (so `RUN_TOOL_TASK` is gated when no real provider exists). Keep `PLAN_TOOL_TASK`/`SHOW_LAST_TOOL_RUN` non-gated/diagnostic.
- `brain/router.py` — only if needed: ensure `agent_id` lands in the structured log entry (closes the prior caveat). No structural change expected.

**Add (new):**
- `actions/tool_use_actions.py` — `PlanToolTaskAction`, `RunToolTaskAction`, `ShowLastToolRunAction` (thin wrappers over `tooluse.*`, with provider/approver injection seam + goal extraction + forbidden→BLOCKED mapping).
- `tooluse/pending.py` — in-process pinned-plan + last-run store.
- `tooluse/audit.py` — `tool_use_audit.jsonl` writer (reuses `core/rotating_jsonl.RotatingJSONLWriter`).
- `tests/test_phase72_router_wiring.py` — unit tests (§6.1).
- `scripts/smoke_phase72_router_tool_use.py` — end-to-end router smoke (§6.2).
- `reports/phase72_tool_use_router_wiring.md` — completion report (written after implementation).

**Reuse unchanged:** `tooluse/{contracts,planner,provider,verifier,recovery,executor}.py`, `core/confirmation.py`, `core/rotating_jsonl.py`.

**Explicitly NOT touched:** legacy `browser/runtime.py` and `actions/phase62_browser_actions.py` (their mock-success leak is separate; Phase 72 must not route through them).

---

## 8. Acceptance criteria for Phase 72 (definition of done)
1. The 3 allowed commands are reachable through the normal router pipeline.
2. `RUN_TOOL_TASK` cannot execute without an explicit confirmation of a fully-previewed, read-only, pinned plan.
3. Forbidden goals are blocked at classification/action time and audited.
4. No mock-success path exists on the new route; unavailable provider → `BLOCKED_UNAVAILABLE`.
5. Every run (and every blocked attempt) is recorded in `tool_use_audit.jsonl`.
6. Unit tests pass deterministically (fake provider); the router smoke succeeds against a real browser and reports honestly on transient live-search failure.
7. No new autonomy: no per-utterance auto-run, no tray entry, no multi-site loops, no committing actions.

*End of plan — no code written.*
