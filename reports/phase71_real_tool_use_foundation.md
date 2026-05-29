# Phase 71 — Real Tool-Use Foundation
**Date:** 2026-05-29
**Goal:** A production-grade foundation for universal tool use — *not a demo* — with a real observe→plan→act→verify loop, human approval before every external action, post-action verification, failure recovery, and **no mock success**.
**Scope this phase:** bounded, read-only browser tasks. **No** payments, orders, bookings, submits, logins, downloads, deletes, sends, or any irreversible action.

---

## 1. Audit of existing observe → plan → act → verify components

| Stage | What existed | Verdict |
|-------|--------------|---------|
| Observe | `browser/runtime.py::_extract_page_understanding()` — real DOM extraction (title/url/headings/links/buttons/text/screenshot) via Playwright | Real, reusable concept |
| Plan | `browser/task_planner.py::plan_browser_task()` | **Static template** — same 5 steps regardless of goal; not a dry-run of discrete, approvable steps |
| Act | `browser/runtime.py` (`open_browser`, `navigate_to_url`, `search_web`, `open_best_result`) with `_truth_success()` checks | Real Playwright path, but interleaved with a **mock fallback** |
| Verify | `_truth_success()`, host/title checks in `navigate_to_url` | Real primitives, but per-function, not a uniform contract |
| Approve | `core/confirmation.py` + `CONFIRMATION_REQUIRED_INTENTS` (router) | Works; not wired per-step for tool use |
| Recover | `recover_browser_session()`, `recover_navigation()` | Real, but not verification-driven |

### Critical defect found (and avoided this phase)
`actions/phase62_browser_actions.py:27,83` return `result_success(...)` when `provider == "mock"` even though `state.last_action_success` is `False`. **This is a "mock counted as success" path.** Phase 71's new layer is built so this is structurally impossible (see §3). The legacy leak is pre-existing and tracked separately (prior audit B11 / Sprint 6 browser work); it was **not** modified here to avoid scope creep.

### What was missing for safe tool use
1. A uniform **observe→plan→act→verify** orchestration loop.
2. A **dry-run plan** of discrete steps, each with explicit risk + approval flag + success criteria.
3. **First-class per-action verification** (expected vs observed).
4. **Verification-driven recovery** (not just blind navigation retry).
5. A **defense-in-depth forbidden-action guard** (payments/orders/etc.).
6. A provider boundary with **no mock branch** so success cannot be faked.

---

## 2. Environment check
- `playwright` installed: **yes**
- Chromium launch (headless): **works**
- Therefore the success criterion is demonstrated against a **real** browser, not a stub.

---

## 3. Architecture (new package `tooluse/`)

Self-contained. Owns its **own isolated Playwright session** — it never touches the legacy `browser/runtime.py` global state, so it cannot inherit the mock fallbacks there. There is literally no mock branch in the provider: if a real browser can't be obtained, the run reports `BLOCKED_UNAVAILABLE`, never success.

```
tooluse/
  contracts.py   data model: StepKind, RiskLevel, PlanStep, ActionPlan,
                 Observation, VerificationResult, StepResult, TaskRun;
                 FORBIDDEN_KEYWORDS + scan_forbidden + ForbiddenGoalError
  planner.py     build_search_open_summarize_plan(goal) -> ActionPlan (DRY RUN;
                 rejects forbidden goals before any plan exists)
  provider.py    ToolProvider protocol + PlaywrightBrowserProvider
                 (isolated session, structured DOM observation, no mock branch)
  verifier.py    verify_step(step, before, after) -> VerificationResult;
                 build_summary(observation)  (deterministic, no invention)
  recovery.py    plan_recovery(...) -> RecoveryDecision (reobserve / retry /
                 next-candidate / restart-session; bounded)
  executor.py    ToolUseExecutor.run(plan): enforces the safety contract
```

### The loop (`ToolUseExecutor.run`)
For each step in the dry-run plan:
1. **Forbidden guard** — `RiskLevel.IRREVERSIBLE` ⇒ abort `FORBIDDEN` (the planner already refuses to emit these; the executor refuses again).
2. **Approval gate** — external step ⇒ call injected `approver(step)`; denial ⇒ abort `APPROVAL_DENIED`. Read-only summary needs no approval.
3. **Real-provider required** — external step ⇒ `provider.is_real()` must be True, else `BLOCKED_UNAVAILABLE` (no mock success).
4. **Act → observe → verify** — execute via provider, observe the UI again, `verify_step` checks observed state against the step's success criteria.
5. **Recover (bounded)** — on verification failure, `plan_recovery` chooses a safe, non-escalating action; retry up to `max_recovery` (default 2). If still failing ⇒ step `FAILED`, run aborts.
6. Session is always closed in `_finish` (no leaked browsers).

A run reaches `RunStatus.SUCCESS` **only** when every step executed on a real provider and passed verification.

### "No mock success" — how it's guaranteed
- `PlaywrightBrowserProvider` has no mock code path. `is_real()` returns False if Playwright/Chromium is unavailable.
- The executor blocks external steps on a non-real provider (`BLOCKED_UNAVAILABLE`).
- `verify_step` returns False for any external step whose observation has `real=False`.
- Three independent layers must all agree on "real" before success is possible.

### Structured UI element detection
`Observation` is a structured snapshot: `url`, `title`, `headings`, `links` (text+href, with DuckDuckGo redirect decoding), `buttons`, `visible_text`, `screenshot_path`. DOM-based (precise for web), not OCR.

### Human approval seam
`approver: Callable[[PlanStep], bool]`. Default is `deny_all` (safe). Helpers: `approve_all` (explicit operator opt-in), `console_approver` (prints preview). CLI/voice wiring through `core.confirmation` is a later phase — the **enforced gate** exists now.

---

## 4. Verification performed

**Unit tests — `tests/test_phase71_tool_use.py`: 18 passed.** Cover (with a scripted fake provider, deterministic):
- Plan is dry-run; expected shape; external steps require approval, read-only summary does not.
- Forbidden goals rejected (buy/book/order/submit/login/download/delete/send).
- Planner never emits irreversible steps.
- `deny_all` blocks the first external step; nothing past it runs.
- Every external step is presented for approval.
- **Unreal provider ⇒ `BLOCKED_UNAVAILABLE`, never success.**
- Full happy path ⇒ all steps verified SUCCESS; session closed.
- `open_result` recovers via next-candidate after a failed first navigation.
- Verifier rejects "still on search engine" and "no real provider"; accepts genuine navigation.

**Smoke — `scripts/smoke_phase71_tool_use.py`:**
- Without `--approve`: prints the dry-run plan, approval gate **denies**, run = `APPROVAL_DENIED` ⇒ `SMOKE PASS` (gate enforced, nothing executed).
- With `--approve` (real headless Chromium, query "python 3.13 release notes"):
  ```
  [success] open_session  verify=ok(real provider connected: playwright)
  [success] search        verify=ok(3 organic result link(s) on results page)
  [success] open_result   verify=ok(navigated to github.com title=...)
  [success] summarize     verify=ok(3357 chars of visible text available)
  status: success
  ```
  Real browser, real navigation, real page text summarized. **Success criterion met.**

Note on search source: DuckDuckGo (html/lite) and Bing/Google bot-block or error headless requests — observed live during this work and handled honestly (the loop reported failure, never faked success). The provider uses **Marginalia** (`search.marginalia.nu`), an independent, headless-tolerant engine, as the reliable result source.

---

## 5. Files added
- `tooluse/__init__.py`, `contracts.py`, `planner.py`, `provider.py`, `verifier.py`, `recovery.py`, `executor.py`
- `tests/test_phase71_tool_use.py`
- `scripts/smoke_phase71_tool_use.py`
- `reports/phase71_real_tool_use_foundation.md` (this file)

No existing modules were modified. The layer is reachable programmatically and via the smoke; it is **not** yet wired to a router intent (deliberate — kept off the live command surface until later phases harden it).

---

## 6. Roadmap toward full universal tool use

Each phase builds on a *real* foundation and adds exactly one capability dimension. No phase ships autonomous money/account actions until the safety + reliability bar is met.

- **Phase 72 — Perception breadth.** Add a desktop provider (reuse `vision/screen_understanding` + `computer_control`) behind the same `ToolProvider` protocol, so the loop drives native apps, not just the browser. Same approval/verify/recover contract.
- **Phase 73 — Adaptive planning.** Replace the fixed search→open→summarize plan with an LLM-proposed plan that is **validated against the contract** (forbidden-action scan, per-step risk tagging, dry-run preview) before any execution. Plans remain human-approved.
- **Phase 74 — Interactive elements (still reversible).** Add `FILL` / `CLICK` step kinds for **non-committing** UI (search boxes, filters, expanders) with stricter verification (element existed, value set, expected DOM delta). Submits/logins remain forbidden.
- **Phase 75 — Workflow learning.** Persist verified step sequences per goal-type to `memory` so repeated tasks replay a known-good plan (with re-verification each run). This is "learn workflows" — grounded in verified history, not speculation.
- **Phase 76 — Router/voice integration.** Wire a single `run_tool_task` intent through `CommandRouter` with per-step confirmation via `core.confirmation`, surfaced in the overlay. End users can now invoke bounded tool use by voice/text.
- **Phase 77 — Gated commitment actions.** Only after 72–76 are at the 90% bar: introduce `SUBMIT`-class actions behind **double confirmation + dry-run preview + post-action verification + reversibility check**. Payments/orders/bookings require an explicit allowlist and per-action human confirmation — never autonomous.

Each phase ends with: real verification, failure-injection tests, and a no-mock-success audit.
