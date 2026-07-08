# Launch smoke test — analytics funnel (RC)

Verify the full funnel emits rows in `public.analytics_events` and rollups in `public.analytics_identities`.

## Prerequisites

- Supabase migrations `0003_analytics_events.sql` and **`0004_analytics_identities.sql`**
- Website deployed with `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
- Desktop build with `ATLAS_WEB_URL` pointing at production

## Smoke test flow

1. **Incognito website visit** → `site_visit`
2. **Download** → `download_clicked` + `desktop_installed` + `users.downloads++`
3. **Install / open desktop** → `desktop_opened`
4. **Desktop login** → `desktop_login_started`, `desktop_login_success`, `api_desktop_login_*`
5. **Verify /me** → `desktop_me_success`, `api_me_success`
6. **Scan repo** → `repo_connected` (with `metadata.first=true` on first scan)
7. **Export context** → `first_context_generated`, `cursor_used` / `claude_used` / `codex_used`
8. **Connect agent** → `cursor_connected` (or claude/codex) + `agent_context_injected`
9. **MCP tool call** (optional) → `atlas_session_started`, `atlas_first_tool_call`, `atlas_tool_call`

## Verify

```powershell
cd c:\J.A.R.V.I.S\local_jarvis
node scripts/analytics-rc-smoke.mjs
node scripts/analytics-summary.mjs
```

Admin dashboard (signed in as admin): open **`/admin/analytics`**.

SQL:

```sql
select event_name, count(*) from public.analytics_events group by 1 order by 2 desc;
select identity_key, total_ttfv_sec, first_seen, last_seen, days_active, sessions_count
  from public.analytics_identities order by last_seen desc limit 20;
```

## Pass criteria

- Each funnel step produces at least one event within 5 minutes
- `analytics_identities` row exists with milestones populated after context export
- `total_ttfv_sec` computed when install + first_context milestones exist
- No sensitive metadata (passwords, tokens, repo paths, source code)
- Existing events (`agent_context_injected`, etc.) still fire unchanged
