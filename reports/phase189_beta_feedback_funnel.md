# Phase 189 — Beta Result Feedback Funnel

**Date:** 2026-06-07
**Base:** `8441798c8b3e3e22148622faa44f198313b4c408` (phase188: add beta profile onboarding)
**Mode:** Small focused code changes. No Stripe/Billing/Teams/Enterprise/SSO/Cloud/Marketing.

## Goal

Collect high-signal feedback from beta users right after they use an Atlas
result, with the least possible friction, and surface it to the operator —
without ever storing source code or repository contents.

## What shipped

A lightweight "Was this useful?" funnel that appears after each generated result:

1. **Question:** "Was this useful?" with **Yes** / **No** buttons.
2. After a click, an optional detail box appears:
   - **Category** dropdown (optional): Accurate, Missing context, Too generic,
     Wrong repo area, Hard to understand, Saved time, Other.
   - **Comment** textarea (optional): placeholder "What worked or what was missing?".
   - **Send feedback** button.

The funnel is wired into all five key result screens:

| Screen | Internal key | Backend `workflow` |
|---|---|---|
| Repository Understanding (scan) | `understanding` | `understanding` |
| What Breaks (impact) | `impact` | `what_breaks` |
| Change Plan (build) | `build` | `change_plan` |
| Debug (investigate) | `investigate` | `debug` |
| Claude/Cursor/Codex export | `export` | `export` |

The pre-existing 👍/👎 `workflowFeedbackHtml` widget (localStorage-only, already
wired into build/investigate/impact) was upgraded in place into this backend
funnel, and extended to the scan and export screens.

## Backend

- **New endpoint:** `POST /api/feedback/result` → `api.submit_result_feedback`.
- **Reuses existing infrastructure:**
  - Redaction: `jarvis_desktop/install_support.py:_redact_support_text` (paths,
    API keys, Bearer/JWT, `sk-…`, `ghp_…`).
  - Storage: the same feedback JSONL store used by `submit_feedback`
    (`{desktop_data_dir}/feedback/feedback.jsonl`), read by the operations inbox.
- **Stored fields (only):** `feedback_id`, `kind="result_feedback"`, `product`,
  `workflow`, `useful` (bool), `category`, `comment` (redacted), `message`
  (mirror of redacted comment for inbox compatibility), `user_id` + `email`
  (only when authenticated, via local cache — no network call), `repo_metadata`
  (safe counts only: file_count, module_count, subsystem_count,
  dependency_edges, graph_quality), `version`, `build_commit`,
  `installation_id`, `timestamp`.
- **Never stored:** source code, repository files, repository paths, raw prompts,
  exports, tokens, or hashes.
- **Validation:** unknown workflow → rejected; missing/invalid `useful` →
  rejected; unknown category → coerced to `other`; comment capped at 2000 chars
  then redacted.
- **Identity:** added `accounts_client.cached_identity()` — reads only the signed
  local state file and returns `{authenticated, user_id, email}`; never triggers
  a license refresh or network call, and never returns tokens/hashes.

### Feedback storage location

```
{desktop_data_dir}/feedback/feedback.jsonl
```

`desktop_data_dir` resolves via `ATLAS_DESKTOP_DATA` / `JARVIS_DESKTOP_DATA`,
else `~/.jarvis_desktop`, else `%LOCALAPPDATA%/Atlas/desktop_data`. Result rows
are tagged `kind="result_feedback"` and coexist with existing general feedback.

## Admin / operator view

- **New endpoint:** `GET /api/operations/result-feedback` →
  `api.operations_result_feedback_inbox` (gated by `ATLAS_ADMIN=1`, matching the
  existing feedback inbox gate).
- **New operations functions:** `operations.result_feedback_inbox` +
  `_minimize_result_feedback_item` + `list_result_feedback`.
- **Admin UI:** a "Result feedback" table was added to `admin.html` showing
  workflow, useful (Yes/No), category, **redacted** comment, user email (if
  available), and timestamp, plus a header summary (`N total · X yes / Y no`).
- The minimizer **re-redacts** the comment at read time (defense in depth) and
  exposes no tokens, hashes, paths, or source.

## Privacy verification

| Check | Result |
|---|---|
| API keys redacted (`sk-ant-…`, `sk-…`, `api_key=…`) | PASS |
| JWTs redacted (`eyJ…` and `JWT …`) | PASS |
| Bearer / GitHub tokens redacted (`Bearer …`, `ghp_…`) | PASS |
| Filesystem paths redacted (`C:\…`, `/home|/Users|/var/…`) | PASS |
| No source code stored (field allow-list enforced) | PASS |
| No password/token/session hashes exposed in API or admin UI | PASS |
| Unauthenticated submission stores empty user_id/email | PASS |
| Repo metadata limited to safe counts (no paths) | PASS |

Redaction is applied at write time (`submit_result_feedback`) and again at read
time in the admin minimizer.

## Screenshots

Captured from the live app (`reports/phase189_feedback_ux/`):

- `01_funnel_collapsed.png` — "Was this useful? Yes / No" after a result.
- `02_funnel_expanded.png` — after choosing Yes: category dropdown, comment box,
  Send feedback.
- `03_admin_result_feedback.png` — operator inbox with real submitted rows
  (3 total · 2 yes / 1 no), redacted comments, no hash columns.

> A real CSS bug was found and fixed during screenshot review: revealing the
> detail box with an inline `display:block` clobbered the `display:flex` column
> layout, so the category/comment/Send controls overlapped. Fixed to reveal with
> `display:flex`.

## Tests

`jarvis_desktop/tests/test_phase189_beta_feedback_funnel.py` — **17 tests, all pass**:

- useful=true / useful=false submissions stored
- optional comment accepted empty
- all five result workflows accepted; unknown workflow rejected
- missing `useful` rejected; invalid category coerced to `other`
- secrets redacted from comment (API key, JWT, `sk-`, `ghp_`, Windows path)
- source code never stored (field allow-list + repo_metadata key allow-list)
- unauthenticated submission is safe (empty user_id/email)
- authenticated identity attached (monkeypatched cache)
- admin inbox requires `ATLAS_ADMIN`
- admin inbox lists feedback without secrets (redacted comment, no hashes)
- admin inbox returns only `result_feedback` rows (not general feedback)
- frontend funnel present in `atlas_beta.js` (Yes/No, category, comment, endpoint)
- frontend slots present in `index.html`; admin section present in `admin.html`

### Regression

Existing feedback/privacy/operations suites: **99 passed, 1 failed**. The single
failure — `test_phase143_installer_and_support.py::test_clear_cache_and_rebuild`
— is pre-existing and unrelated (reproduces on clean baseline with Phase 189
changes stashed; demo mode has no on-disk repo path to rescan). The
privacy-relevant `test_support_bundle_no_source_code` passes.

## Verdict

First 3–5 supervised beta users: **GO**. The funnel is low-friction, reuses the
existing redaction + storage + operations inbox, stores only safe fields, and
gives the operator a clear yes/no + category + comment view per workflow.
