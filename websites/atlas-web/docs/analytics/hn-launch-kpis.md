# Show HN launch KPIs

Every number on `/admin/hn` is defined here. If a definition is not in this
file, the dashboard does not show it.

Two rules govern all of it:

1. **Website and desktop identities are not correlated.** A browser session and
   an Atlas installation are separate universes. Any ratio crossing that line is
   a ratio of two independent counters, not a per-user conversion, and is
   labelled `aggregate proxy` in the UI.
2. **Sample size travels with every statistic.** A median over three events is
   not a median. `N` is always shown.

## Units

| Unit | Identity | Source |
|---|---|---|
| session | `session_id` (sessionStorage, per browser tab) | website events |
| installation | `installation_id` (random UUID, per Windows user profile) | desktop events |
| event | one row | either |

"Installations", never "users". One person with two machines is two
installations; one machine used by two people is one.

## Acquisition

```
HN sessions        = distinct session_id where event ∈ {page_view, site_visit}
                     and metadata.acquisition_channel = 'hacker_news'
Total sessions     = distinct session_id where event ∈ {page_view, site_visit}
HN share           = HN sessions / Total sessions
Download CTA       = distinct session_id where event = download_clicked
Artifact redirects = count of installer_download_started        (SERVER-side)
Landing → CTA      = Download CTA / Total sessions
```

`acquisition_channel` is resolved once per session from `?ref=hn` or the
`news.ycombinator.com` referrer, then replayed on later events — by the time
the visitor clicks Download, the referrer is our own domain and the query
string is gone.

**Artifact redirects are not completed downloads.** The redirect is issued by
`/download/atlas`; whether GitHub finished the transfer is not observable from
here. The dashboard says "artifact redirects" for exactly that reason.

## Activation

```
First launch       = distinct installation_id where event = desktop_launched
Local mode         = distinct installation_id where event = onboarding_local_mode_selected
Repository selected= distinct installation_id where event = repository_selected
Scan started       = distinct installation_id where event = scan_started
Scan completed     = distinct installation_id where event ∈ {real_repo_scan_completed,
                                                             sample_scan_completed}
Scan success       = Scan completed / Scan started
```

```
Redirect → First launch  =  First launch / Artifact redirects        [AGGREGATE PROXY]
```

This one crosses the boundary. It is the ratio of two independent counters and
must never be read as "x% of downloaders launched the app".

## Integration and value

```
MCP configured   = distinct installation_id where event = mcp_configured
MCP initialized  = distinct installation_id where event = mcp_initialize_success
First value      = distinct installation_id where event = first_value_reached
Activation rate  = First value / First launch
MCP conversion   = MCP initialized / First launch
```

**First value** is the first successful, meaningful Atlas MCP tool execution
against a scanned repository. It is not MCP configuration, not `initialize`,
not `tools/list`, not opening the Graph, and not launching the app.
`atlas_health` and `atlas_repo_health` are excluded because they report on
Atlas rather than on the repository.

It is emitted **exactly once per installation**, gated by a marker file that
survives restarts, and fails closed: if the marker cannot be written, no event
is sent. So the count is installations that got value, never a stream.

## Time to value

Per installation, using the earliest timestamp of each event:

```
launch → scan complete = first(scan completed) − first(desktop_launched)
launch → first value   = first(first_value_reached) − first(desktop_launched)
```

Negative deltas are discarded (clock skew). Median = p50, plus p90. Both are
shown with `N`; below N=5 the UI says the sample is too small to read.

## Reliability

```
Scan failures    = count of scan_failed
Top error codes  = scan_failed grouped by metadata.error_code
                   ∈ {permission_denied, invalid_repository, parser_failure,
                      index_failure, cancelled, disk_failure, unknown_safe}
Tool calls       = count of atlas_tool_called
Tool failure rate= atlas_tool_called with outcome != success / Tool calls
Active versions  = distinct installation_id grouped by app_version
```

## Tool usage

Ranked by **unique installations first**, then total calls, so one enthusiastic
user cannot make a tool look popular. Both numbers are always shown.

```
per tool: unique installations, total calls, success rate
```

## Retention

```
Installations today   = distinct installation_id with desktop_launched today (UTC)
Returning             = installations with desktop_launched on more than one UTC day
D1                    = of installations first seen ≥1 day ago, those that
                        launched again on day+1
D7                    = of installations first seen ≥7 days ago, those that
                        launched again within 7 days
```

D1/D7 report `returned/cohort`, and show "no cohort yet" rather than 0% when
the cohort does not exist. On launch day both are empty; that is correct, not a
bug.

## Feedback

```
Opened    = count of feedback_opened
Submitted = count of feedback_submitted        (emitted only after HTTP success)
Categories= feedback_submitted grouped by metadata.category
```

Message text is never in analytics. Read it in `public.beta_feedback`.

If `opened > 0` and `submitted = 0`, the dashboard says so explicitly — that is
the signature of the `beta_feedback` migration not having been applied, which
would otherwise read as "nobody sent feedback".

## Launch health

Deliberately coarse. There is no baseline on launch day from which to derive
statistical thresholds, so these are availability statements plus one
obvious-failure check, and raw numbers always sit next to the colour.

| Level | Condition |
|---|---|
| RED | download route not serving the expected artifact, OR scan success < 50% with ≥10 starts, OR tool failure > 50% with ≥10 calls |
| AMBER | feedback endpoint unavailable, OR scan success < 80% with ≥10 starts, OR the row cap was reached |
| GREEN | none of the above |

Minimum sample sizes are there so a single early failure cannot paint the board
red during the first ten minutes.

## Known limits

- The dashboard reads at most 50,000 events per window and flags `truncated`
  when it hits the cap; counts then are a **lower bound**, and health drops to
  amber so the number is never read as complete.
- Internal events (`is_internal = true`) are excluded.
- Everything is UTC.
