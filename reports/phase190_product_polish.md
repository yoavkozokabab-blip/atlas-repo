# Phase 190 — Product Polish Pass

**Date:** 2026-06-08
**Goal:** Make Atlas feel like a polished commercial beta, not an internal tool.

This pass has two parts: (A) a focused overhaul of the beta application form (the
critical issue), and (B) a product-wide polish review.

---

## Part A — Beta application form overhaul (FIXED)

The create-account form worked but felt unfinished. All seven requested fixes
are implemented in `index.html`, `styles.css`, and `atlas_accounts.js`, plus a
small `accounts_service/schemas.py` addition.

| # | Requirement | Status | What changed |
|---|---|---|---|
| 1 | Always-visible submit CTA | ✅ | Form is a flex wizard with a **sticky footer** (`.auth-wizard-footer`) holding a full-width primary **Next / Submit application** button — never below the fold. |
| 2 | Conditional company fields | ✅ | `#acc-company-fields` (name + size) is hidden when *Working as developer = No*, *Usage = Personal projects*, or *Primary role = Student* (`_companyFieldsRelevant()`); hidden fields submit `company_size: "not_applicable"`. |
| 3 | Better repo-size choices | ✅ | Small (&lt;100 files) · Medium (100–1,000) · Large (1,000–10,000) · Very large (10,000+) · Not sure. |
| 4 | Sectioned onboarding | ✅ | 5 sections: **Account → Developer profile → Projects → Goals → Optional notes**. |
| 5 | Progress indicator | ✅ | "Step X of 5 · &lt;name&gt;" + animated progress bar (`#acc-progress-fill`). |
| 6 | Immediate validation | ✅ | Email format, password length, and password match validate **on input** (per-field error text), not just on submit. |
| 7 | Completion screen | ✅ | Dedicated **"Application submitted"** screen with the three next-steps; no technical messages. |

Backend: added `not_applicable` to the `CompanySize` literal so conditionally
hidden company fields validate.

### Screenshots (`reports/phase190_polish/`)

- `form_01_step1_account.png` — Step 1, progress bar, sticky **Next**.
- `form_02_step2_developer.png` — Developer profile.
- `form_03_step3_projects_company_shown.png` — Projects with company fields shown (work + full-stack).
- `form_04_step3_company_hidden_conditional.png` — Company fields **hidden** when role = Student (verified `display:none`).
- `form_05_step4_goals.png` — Goals.
- `form_06_step5_notes_submit.png` — Step 5 with sticky **Submit application**.
- `form_07_application_submitted.png` — Completion screen.
- `form_08_inline_validation.png` — Immediate validation (invalid email, short password, mismatch).

All Phase 188 + 189 tests still pass (29 passed).

---

## Part B — Product-wide polish review

Scope note: the signed-out / onboarding screens were reviewed **live** (Playwright
against the running app, screenshots above). The in-app workflow screens are
correctly gated behind an approved beta session (`requireAtlasAccess`), so they
were reviewed by **code/CSS inspection**; a full live capture needs a running
accounts service + an approved account. The access gate working as designed is
itself a positive finding (workflows never leak before sign-in).

### Findings by screen

| Screen | Review | Severity | Status |
|---|---|---|---|
| **Sign In** | Centered card, labelled inputs, `role="alert"` errors, aria-invalid, Enter submits. Clean. | — | OK |
| **Create Account** | Was the critical issue (CTA hidden, irrelevant fields, no progress/validation/completion). | Critical | **Fixed (Part A)** |
| **Pending Approval** | Plain-language state panel ("Beta access pending"), sign-out available. | — | OK |
| **Application Submitted** | New completion screen, clear next steps, no jargon. | — | **Added** |
| **Home** | Scan-focused; uses `emptyStateHtml`/`workflowEmptyHtml`; primary CTA consistent (`.btn primary`). | Low | OK |
| **Scan / Repository Understanding** | Skeleton loading (`scanSkeleton`), success metrics + risk + next steps; Phase 189 "Was this useful?" funnel. | Low | OK |
| **What Breaks / Change Plan / Debug** | Empty states + friendly error states (`workflowErrorHtml`), collapsible advanced sections, result feedback funnel. | Low | OK |
| **Admin** | Metrics dashboard renders; KPIs clear. | — | OK |
| **Admin — server analytics** | Raw JSON dump (`/api/analytics/summary`) is shown verbatim, including a local filesystem `path`. Operator-only, but a path in the UI is untidy. | Low | Remaining |
| **Admin — breakdown empty state** | Repeats terse "no data"; could read "No signups yet." | Low | Remaining |
| **Feedback** | Phase 189 funnel (Yes/No → category + comment), redacted; Report Issue path. | — | OK |
| **Support Bundle** | Generated locally, redacted, no source code (verified by Phase 143/186 tests). | — | OK |

### Cross-cutting review

- **Typography / spacing / color / contrast:** consistent design tokens
  (`--cyan`, `--violet`, `--muted`); the new wizard reuses them. Section titles,
  progress label, and field labels share one scale.
- **Button consistency:** primary actions use `.btn.primary.auth-btn-primary`;
  secondary use `.btn.ghost`. The wizard footer makes the primary action dominant.
- **Empty / loading states:** present across workflows (skeletons, empty panels,
  error panels). Admin breakdown empty copy is the weakest (Low).
- **Modal behavior:** unsigned-beta notice + about modal dismiss correctly.
- **Accessibility / keyboard:** labels for all inputs, `role="radiogroup"`,
  `role="alert"` on errors, `aria-invalid` toggling, `hidden` on inactive steps,
  Enter advances/submits the wizard, focus moves to the first field per step.
- **Error / confirmation messages:** friendly mapping (`LOGIN_ERROR_MAP`); the
  user-facing Python command (`python -m accounts_service.main`) was removed.

### Performance review

- **Polling:** account state polls every 60 s (`POLL_INTERVAL_MS`) — light.
- **Redundant API calls:** account state refresh is debounced to view changes and
  the poll; no duplicate scans observed (scans are user-initiated only).
- **DOM size:** workflow result panels can be large but hide detail behind
  `<details>` / "advanced-only" toggles, keeping the initial DOM small.
- **Startup:** auth screen renders immediately; the app shell boots lazily
  (`bootAtlasApp` runs once on first authenticated reveal).
- No unnecessary re-renders identified in the auth/onboarding path (imperative
  DOM updates, no framework re-render churn).

---

## Fixes applied in this pass

1. Beta application form: 7-point overhaul (sticky CTA, conditional fields,
   repo-size labels, 5 sections, progress, immediate validation, completion).
2. Backend: `CompanySize` gains `not_applicable`.
3. (Carried + verified) user-facing Python command removed from
   `accounts_routes.py`.

## Remaining issues

| Issue | Severity | Note |
|---|---|---|
| Admin server-analytics shows raw JSON incl. a local path | Low | Operator-only screen; tidy-up candidate. |
| Admin breakdown empty copy is terse ("no data") | Low | Cosmetic. |
| In-app workflow screens not captured live | Info | Require an approved beta session; reviewed via code. |
| No "forgot password" flow | Low | Acceptable for supervised beta. |

## Verdict

The critical "unfinished form" problem is resolved: the beta application is now a
guided, sectioned wizard with an always-visible CTA, progress, conditional
relevance, immediate validation, and a proper completion screen — it reads like a
commercial beta. Remaining items are low-severity polish, documented above.
