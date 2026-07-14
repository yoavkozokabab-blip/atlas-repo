# Atlas product funnel and metric definitions

All reporting uses UTC and excludes `is_internal=true` by default. Production, Preview, development, test, and legacy `unknown` data are never mixed unless an authorized admin explicitly changes the filter. Counts are exact raw-event aggregates; unavailable steps are zero and visibly marked partial rather than estimated.

## Trustworthy funnel

1. Visit: `site_visit` / `page_view`
2. Product understanding: page views for `/features`, `/how-it-works`, or `/docs`
3. Download intent: `download_clicked`
4. Availability / delivery: `download_unavailable_seen` or `installer_download_started`
5. Installation: `desktop_installed`
6. First launch: `desktop_launched`
7. Repository selected: `repository_selected`
8. Scan completed: `scan_completed`
9. First question: `ask_completed`
10. Agent connected: `agent_connected`
11. Return usage: the same identity active on at least two UTC dates

The current release can truthfully measure website visit, route, suspended-download visibility, selected outbound clicks, and website auth attempts. It cannot yet measure a completed installer transfer, install, launch, scan, Ask, agent connection, contact submission, referrer, or plan conversion. Those metrics must remain partial until their authoritative source emits the canonical event.

## Admin metric source

The admin endpoint calls the server-only `public.atlas_analytics_summary` RPC created by migration `20260714211752_secure_auth_analytics_data.sql`. Browser roles have no execute privilege and no table access.

| Metric | Definition |
|---|---|
| Unique visitors | Distinct `coalesce(anonymous_id, user_id::text)` on `site_visit`/`page_view`; anonymous identity is preferred to preserve continuity across login |
| Sessions | Distinct non-null `session_id` |
| Page views | Total `page_view` events |
| Download attempts | Total `download_clicked` + `installer_download_started` events |
| Download unavailable | Total `download_unavailable_seen` events |
| Successful installs | Total truthful `desktop_installed` events |
| First launches | Total `desktop_launched` events |
| Signup success/failure | Totals of the exact canonical auth events |
| Active users | Distinct identified user/anonymous identities with any event |
| Returning users | Active identities present on at least two UTC dates in the range |
| Top routes | Total `page_view` grouped by sanitized route, top 10 |
| Download CTR | Download attempts / unique visitors |
| Signup conversion | Signup successes / unique visitors |
| Returning-user rate | Returning users / active users |

The authorized dashboard provides 1-, 7-, and 30-day ranges, environment and build filters, and an explicit internal-traffic toggle. The time range is `[now() - range, now()]` in UTC. Bots are not reliably identified yet; suspicious traffic must be marked internal at ingestion or excluded by a future reviewed rule.

## Reference queries for deeper conversion analysis

```sql
-- Base set for all metrics. Substitute reviewed parameters.
with filtered as (
  select *
  from public.analytics_events
  where created_at >= :since_utc
    and environment = :environment
    and not is_internal
)
select event_name, count(*) total_events,
       count(distinct coalesce(anonymous_id, user_id::text)) unique_actors
from filtered
group by event_name
order by event_name;
```

```sql
-- Daily and weekly active users. Missing identity rows are excluded.
with activity as (
  select created_at,
         coalesce(anonymous_id, user_id::text) identity
  from public.analytics_events
  where environment = 'production' and not is_internal
)
select date_trunc('day', created_at) bucket, count(distinct identity) dau
from activity where identity is not null group by 1 order by 1;

select date_trunc('week', created_at) bucket, count(distinct identity) wau
from activity where identity is not null group by 1 order by 1;
```

```sql
-- Actor-level sequential conversion. This is valid only after every named
-- event is emitted from an authoritative source.
with per_actor as (
  select coalesce(anonymous_id, user_id::text) identity,
    min(created_at) filter (where event_name='site_visit') visited_at,
    min(created_at) filter (where event_name='download_clicked') download_intent_at,
    min(created_at) filter (where event_name='desktop_installed') installed_at,
    min(created_at) filter (where event_name='scan_completed') scan_at,
    min(created_at) filter (where event_name='ask_completed') ask_at,
    min(created_at) filter (where event_name='agent_connected') agent_at
  from public.analytics_events
  where environment='production' and not is_internal
  group by 1
)
select
  count(*) filter (where visited_at is not null) visitors,
  count(*) filter (where download_intent_at >= visited_at) download_intent,
  count(*) filter (where installed_at >= download_intent_at) installed,
  count(*) filter (where scan_at >= installed_at) scanned,
  count(*) filter (where ask_at >= scan_at) asked,
  count(*) filter (where agent_at >= scan_at) connected_agent
from per_actor where identity is not null;
```

Plan/trial conversion is not reported: payments are currently stubbed and the live account schema does not match the Paddle fields expected by the server. Referring sources are also unavailable because no canonical referrer field is collected.
