# Atlas analytics metric definitions

All reporting uses UTC and excludes `is_internal=true` by default. Production,
preview, development, test, and legacy `unknown` data are never mixed unless an
authorized admin explicitly changes the filter. Counts are exact raw-event
aggregates; unavailable steps are zero and visibly marked partial rather than
estimated.

## Analytics-only release funnel

1. Visit: `site_visit` / `page_view`
2. Download intent: `download_clicked`
3. Installer response started: `installer_download_started`
4. Desktop launch: `desktop_launched`
5. Sample scan: `sample_scan_completed`
6. Real repository scan: `real_repo_scan_completed`
7. Graph usage: `graph_opened`
8. Impact usage: `impact_completed`
9. MCP connection: `mcp_connected`
10. Return usage: the same anonymous/installation identity active on at least two UTC dates

The website does not claim a completed installation from a click. If the asset
is hosted on GitHub Releases, GitHub's asset count is the source for raw file
downloads; Atlas measures the click/start request and actual execution through
`desktop_launched`. Accounts, Ask, heartbeat, UI-render, and repository-identity
events are disabled and are not reported.

## Admin metric source

The admin endpoint calls the server-only `public.atlas_analytics_summary` RPC
created by the reviewed base analytics migration. Browser roles have no execute
privilege and no table access.

| Metric | Definition |
|---|---|
| Unique visitors | Distinct anonymous identity on website `site_visit`/`page_view` events |
| Sessions | Distinct non-null `session_id` |
| Page views | Total `page_view` events |
| Download attempts | Total `download_clicked` + `installer_download_started` events |
| First launches | Total `desktop_launched` events |
| Scans completed | `sample_scan_completed` + `real_repo_scan_completed` events |
| Graph opened | Total `graph_opened` events |
| Impact completed | Total `impact_completed` events |
| MCP connected | Total `mcp_connected` events |
| Active users | Distinct anonymous/installation identities with any event |
| Returning users | Active identities present on at least two UTC dates in the range |
| Top routes | Total `page_view` grouped by sanitized route |
| Download CTR | Download attempts / unique visitors |
| Returning-user rate | Returning users / active users |

The dashboard provides 1-, 7-, and 30-day ranges, environment and build filters,
and an explicit internal-traffic toggle. Missing authoritative events remain
zero; they are never inferred from account or page activity.

## Reference query

```sql
with filtered as (
  select *
  from public.analytics_events
  where created_at >= :since_utc
    and environment = :environment
    and not is_internal
)
select event_name, count(*) total_events,
       count(distinct coalesce(installation_id, anonymous_id, user_id::text)) unique_actors
from filtered
group by event_name
order by event_name;
```
