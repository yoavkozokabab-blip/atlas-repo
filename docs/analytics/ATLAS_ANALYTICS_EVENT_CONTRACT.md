# Atlas Analytics Event Contract (v1)

Frontend event contract for Codex to implement. This document defines names,
triggers, and allowed payloads. The frontend emits these events (or tags DOM
nodes with `data-evt` attributes); the storage pipeline, ingestion API, and
dashboards are owned by Codex and are out of scope here.

## Global rules

**Forbidden in every event payload, with no exceptions:**

- source code, diffs, or file contents
- prompts, questions, answers, or generated plans
- repository names or repository paths
- file names or module names
- account tokens, session tokens, API keys, secrets
- email addresses (allowed only inside dedicated auth events as a hashed ID)
- MCP request/response contents
- free-text typed by the user

**Allowed property primitives:** counts, durations (ms), booleans, enum
strings defined in this document, coarse buckets (e.g. `repo_size_bucket:
"lt100" | "100to1k" | "gt1k"`), app version, OS major version, anonymous
installation id.

**Active time** means foreground + interaction time (input events, visibility
`visible`, focus). Wall-clock elapsed time must never be reported as engaged
time. Engagement heartbeats pause when the window blurs or the tab hides.

Every event carries the implicit envelope: `event`, `ts` (UTC ISO),
`installation_id` (desktop) or `session_id` (web), `app_version` /
`site_build`, and `surface`.

Event **type** legend: `intent` (user started something), `completion`
(something finished successfully), `failure` (something finished
unsuccessfully). Failures are never folded into completion counts.

## Website events (surface: `web`)

| Event | Trigger | Allowed properties | Type |
|---|---|---|---|
| `website_session_started` | First page of a browser session | `referrer_domain` (registrable domain only), `utm_source/medium/campaign`, `viewport_bucket` | intent |
| `website_page_viewed` | Route mount | `page` (route id enum, e.g. `home`, `pricing`, `download`, `hn`) | intent |
| `website_page_engaged` | ≥10 s active time OR ≥50 % scroll | `page`, `active_ms`, `max_scroll_pct` | completion |
| `website_page_exited` | Route unmount / pagehide | `page`, `active_ms` | completion |
| `website_cta_clicked` | Any `data-evt` CTA click | `cta` (enum: `download_click`, `pro_cta_click`, `hn_cta`, `docs_cta`, …), `page` | intent |
| `website_download_clicked` | Download button click | `page`, `os` (`windows` only today) | intent |
| `website_github_clicked` | GitHub link click | `page` | intent |
| `website_demo_started` | Interactive demo start | `page` | intent |
| `website_demo_completed` | Demo reaches final step | `page`, `steps_completed`, `active_ms` | completion |
| `website_contact_clicked` | Contact/mailto click | `page` | intent |

## Desktop events (surface: `desktop`)

| Event | Trigger | Allowed properties | Type |
|---|---|---|---|
| `app_first_run` | First successful launch on an installation | `app_version`, `os_major` | completion |
| `app_session_started` | Process start with UI | `app_version` | intent |
| `app_session_ended` | Graceful shutdown | `active_ms`, `screens_visited_count` | completion |
| `app_screen_viewed` | Screen becomes active | `screen` (enum: `home`, `memory`, `files`, `graph`, `ask`, `impact`, `debug`, `plan`, `agents`, `diagnostics`, `settings`) | intent |
| `app_screen_engaged` | ≥10 s active time on a screen | `screen`, `active_ms` | completion |
| `guest_mode_started` | "Continue without an account" | — | intent |
| `account_signup_started` | Signup form opened | — | intent |
| `account_signup_completed` | Account created | `hashed_account_id` | completion |
| `account_login_completed` | Login success | `hashed_account_id` | completion |
| `repository_scan_started` | Scan begins (user action) | `repo_size_bucket`, `is_demo` | intent |
| `repository_scan_completed` | Scan succeeds | `duration_ms`, `module_count_bucket`, `is_demo` | completion |
| `repository_scan_failed` | Scan fails | `error_code` (enum, no messages), `is_demo` | failure |
| `demo_loaded` | Demo pack loaded | `pack` (`small`/`medium`/`large`) | completion |
| `impact_started` | Analyze impact clicked with a target | `is_demo` | intent |
| `impact_completed` | Visible impact result rendered | `duration_ms`, `dependents_bucket` (`0`, `1to5`, `gt5`), `risk_level` | completion |
| `impact_failed` | Error or target-not-found state rendered | `reason` (`target_not_found` / `error`) | failure |
| `ask_started` | Ask submitted | `is_demo` | intent |
| `ask_completed` | Visible answer rendered | `duration_ms`, `evidence_count_bucket` | completion |
| `debug_started` | Investigation submitted | `is_demo` | intent |
| `debug_completed` | Visible hypotheses rendered | `duration_ms`, `hypothesis_count` | completion |
| `plan_started` | Plan requested | `is_demo` | intent |
| `plan_completed` | Visible plan rendered | `duration_ms`, `files_count_bucket` | completion |
| `mcp_configuration_installed` | Config written for a client | `client` (`claude`/`cursor`/`codex`) | completion |
| `mcp_client_connected` | Verified MCP handshake | `client` | completion |
| `mcp_client_disconnected` | Handshake lost after being connected | `client` | failure |

## Implementation notes for Codex

- Workflow `*_completed` events fire only when the **visible result** renders,
  not when the API returns — an invisible success is a `*_failed` with
  `reason: "render_error"` and should page someone.
- `data-evt` attributes already exist on website CTAs; keep names in the
  `website_cta_clicked.cta` enum in sync with them.
- Do not add new properties without extending this contract first.
