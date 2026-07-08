# Launch tracking — Atlas funnel analytics (RC)

Minimal, privacy-safe event trail for launch readiness: **site → download → desktop → login → /me → context → agent injection → usage**.

## Storage

| Environment | Backend |
|-------------|---------|
| Production website | Supabase `public.analytics_events` + `public.analytics_identities` |
| Dev (no Supabase) | `.data/analytics_events.jsonl` + `.data/analytics_identities.json` |
| Desktop (local) | `{desktop_data}/analytics.jsonl` (unchanged) |
| Desktop (cloud funnel) | Forwards selected events to `POST /api/events` on the website |

### Tables

**`analytics_events`** (migration `0003_analytics_events.sql`):

- `id`, `created_at`, `user_id`, `anonymous_id`, `event_name`, `source`, `app_version`, `platform`, `metadata`

**`analytics_identities`** (migration `0004_analytics_identities.sql`):

- Identity: `identity_key`, `user_id`, `anonymous_id`, `installation_id`, `first_seen`, `last_seen`, `days_active`, `sessions_count`
- TTFV milestones: `installed_at`, `opened_at`, `login_success_at`, `repo_connected_at`, `first_context_at`
- Agent milestones: `cursor_connected_at`, `claude_connected_at`, `codex_connected_at`
- Usage counters: `cursor_used_count`, `claude_used_count`, `codex_used_count`, `tool_calls_count`, `context_injections_count`, `repositories_count`
- Computed TTFV (seconds): `install_to_open_sec`, `open_to_login_sec`, `login_to_repo_sec`, `repo_to_first_context_sec`, `total_ttfv_sec`, `ttfv_computed_at`

TTFV is computed **server-side** when events arrive (`updateIdentityFromEvent` in `analytics-identity.ts`).

Existing user fields **remain**: `users.downloads`, `users.last_login_at`.

## Events

### Website

| Event | When |
|-------|------|
| `site_visit` | First page load (client) |
| `download_clicked` | User clicks download button |
| `desktop_installed` | Installer download completes (server) |
| `github_clicked` | Click on `a[data-analytics-event="github_clicked"]` |
| `waitlist_joined` | Waitlist API success |
| `signup_started` / `signup_success` / `signup_failed` | Registration funnel |

### Website API (desktop auth)

| Event | When |
|-------|------|
| `api_desktop_login_*` | Desktop login API |
| `api_me_success` / `api_me_failed` | Bearer `/me` |

### Desktop (cloud-forwarded)

| Event | When |
|-------|------|
| `desktop_opened` | App server starts (`app_started` mapped) |
| `desktop_login_*` | Login funnel |
| `desktop_me_*` | License `/me` check |
| `repo_connected` | Scan complete (`scan_completed` mapped) |
| `first_context_generated` | Context export (`export_created` mapped) |
| `agent_context_injected` | MCP connect (legacy, still emitted) |
| `cursor_connected` / `claude_connected` / `codex_connected` | Agent MCP config written |
| `cursor_used` / `claude_used` / `codex_used` | Context copied/exported for agent |
| `atlas_session_started` | First MCP usage or session |
| `atlas_first_tool_call` | First MCP tool call in session |
| `atlas_tool_call` | Each MCP tool call |
| `atlas_context_served` | Context pack served via MCP or export |
| `atlas_context_used` | Context consumed by an agent |
| `atlas_session_finished` | Session end (optional; duration in `metadata.session_sec`) |

## Time to first value (TTFV)

Funnel milestones (earliest timestamp wins per identity):

```
install (download_clicked | desktop_installed)
  → desktop_opened
  → login_success (desktop_login_success | api_desktop_login_success | signup_success)
  → repo_connected
  → first_context_generated
```

Computed fields on `analytics_identities`:

- `install_to_open`, `open_to_login`, `login_to_repo`, `repo_to_first_context`, `total_ttfv_sec`

## Retention

Stored per identity: `first_seen`, `last_seen`, `days_active`, `sessions_count`.

Dashboard computes Day 1 / 7 / 30 retention when enough cohort data exists.

## Internal dashboard

Admin-only: **`/admin/analytics`** (API: `GET /api/admin/analytics/dashboard`)

Shows funnel, conversion rates, average TTFV, agent usage, drop-off point, active/returning users.

## Safe metadata

Allowed keys include: `reason`, `error_code`, `page`, `path`, `target`, `agent`, `duplicate`, `mode`, `ok`, `first`, `http_status`, `packet`, `platform_hint`, `signed_in`, `installation_id`, `tool`, `session_sec`, `source_kind`.

## Do NOT log

Source code, repo paths, prompts, tokens, passwords, email addresses.

## Commands

```powershell
cd c:\J.A.R.V.I.S\local_jarvis
node scripts/analytics-rc-smoke.mjs
py -3 -m pytest jarvis_desktop/tests/test_cloud_analytics.py jarvis_desktop/tests/test_usage_analytics.py jarvis_desktop/tests/test_analytics_ttfv.py -v
node scripts/analytics-summary.mjs --probe
```

Apply migration `0004_analytics_identities.sql` in Supabase before production.

## Env vars

| Variable | Where |
|----------|-------|
| `SUPABASE_URL` | Website + summary script |
| `SUPABASE_SERVICE_ROLE_KEY` | Website + summary script |
| `ATLAS_WEB_URL` | Desktop cloud forward |
| `ATLAS_CLOUD_ANALYTICS` | Desktop (`1` default) |
| `ADMIN_EMAILS` | Website admin dashboard access |
