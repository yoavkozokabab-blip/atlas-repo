-- READ-ONLY dry run. This script does not update or delete data.
-- Review counts and sampled IDs before drafting any separate cleanup migration.

select environment, is_internal, event_name, count(*) as rows,
       min(created_at) as first_at, max(created_at) as last_at
from public.analytics_events
group by environment, is_internal, event_name
order by environment, is_internal, rows desc;

select id, created_at, event_name, source, environment, route, build_commit
from public.analytics_events
where is_internal
   or environment in ('preview', 'development', 'test', 'unknown')
order by created_at desc
limit 200;

-- Legacy rows predate the canonical environment/internal columns. After the
-- migration they default to environment='unknown', not production. Do not
-- relabel or delete them without a reviewed evidence-based mapping.
