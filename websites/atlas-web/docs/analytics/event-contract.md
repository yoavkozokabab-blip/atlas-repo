# Atlas analytics event contract

Status: canonical contract, version 1. Times are recorded by Postgres in UTC. The server is the authority for `environment`, `app_version`, `build_commit`, `user_id`, and `created_at`.

## Privacy and identity rules

- Website events use a random, stable browser `anonymous_id` and a per-tab `session_id`. After login, the server associates new events with the authenticated `user_id`; the browser may never submit a `user_id`.
- Desktop events must use a random installation identifier and a per-process session identifier. They must not reuse a repository identifier as an identity.
- Allowed metadata keys are `agent`, `href_kind`, `http_status`, `outcome`, `plan`, `reason_code`, `status`, and `surface`. Unknown keys are discarded by the server.
- Email addresses, names, IP addresses, source code, repository names, full or relative local paths, raw prompts, cookies, authorization headers, tokens, and secrets are forbidden.
- Production, Preview, development, and test events are separate values of `environment`. Preview, localhost, tests, bots, and known QA sessions are marked `is_internal=true` and excluded from default metrics.
- Raw events are retained only as long as needed to validate aggregate product metrics. Review at 90 days and aggregate or expire them under an approved retention policy. Account deletion must not silently break historical aggregates.

Every accepted event includes: UUID `id`, server `created_at`, exact `event_name`, `source`, optional server-derived `user_id`, optional anonymous/session identifiers, `environment`, route, application version, build commit, platform, contract version, SHA-256 `deduplication_key`, internal flag, and allowlisted metadata.

## Website and server events

| Event | Source | Exact trigger | Required properties | Optional properties | Deduplication | PII | Retention |
|---|---|---|---|---|---|---|---|
| `site_visit` | website | First mounted Atlas page in a browser session | none | none | anonymous ID + session ID | forbidden | 90 days |
| `page_view` | website | One completed route transition | route | none | session ID + route | forbidden | 90 days |
| `download_clicked` | website | A user activates a real `/download` link | route, `surface` | none | unique click UUID | forbidden | 90 days |
| `download_unavailable_seen` | website | A rendered page contains the verified download-suspended state | route | none | session ID + route | forbidden | 90 days |
| `github_clicked` | website | A user activates an external GitHub link | route, `href_kind=github` | none | unique click UUID | forbidden | 90 days |
| `docs_clicked` | website | A user activates an Atlas docs link | route, `href_kind=docs` | none | unique click UUID | forbidden | 90 days |
| `pricing_viewed` | website | `/pricing` route is viewed | route | none | session ID + route | forbidden | 90 days |
| `signup_started` | website | Valid form submission begins | route | none | unique attempt UUID | forbidden | 90 days |
| `signup_success` | website | Server returns a completed account creation | route | `http_status` | attempt UUID | forbidden | 90 days |
| `signup_failed` | website | Account creation returns a handled failure | route, `reason_code` | `http_status` | attempt UUID | forbidden | 30 days |
| `login_started` | website | Sign-in form submission begins | route | none | unique attempt UUID | forbidden | 30 days |
| `login_success` | website | Server returns a valid session | route | `http_status` | attempt UUID | forbidden | 30 days |
| `login_failed` | website | Sign-in returns a handled failure | route, `reason_code` | `http_status` | attempt UUID | forbidden | 30 days |
| `contact_submitted` | server | A server-backed contact form accepts a message | `outcome` | `reason_code` | submission UUID | forbidden in analytics; contact data belongs in a separate restricted table | 30 days |
| `installer_download_started` | server | The installer route starts a verified asset response | version/build | none | request/asset UUID | forbidden | 90 days |
| `installer_download_completed` | server | A trusted delivery provider confirms a full asset transfer | version/build | `http_status` | delivery UUID | forbidden | 90 days |

`contact_submitted` is not emitted because the current contact page is `mailto:` only. `installer_download_started` and `installer_download_completed` are not emitted while downloads are suspended. A browser click is not evidence of a completed download.

## Desktop events

| Event | Exact trigger | Required properties | Optional properties | Deduplication | PII / repository data | Retention |
|---|---|---|---|---|---|---|
| `guest_mode_started` | User chooses local guest mode | app version, build | none | installation + version | forbidden | 90 days |
| `desktop_installed` | Verified installed app performs its first post-install launch | installer version, build | `status` | installation + version | forbidden | 180 days |
| `desktop_launched` | Fresh Atlas process reaches runtime ready | app version, build | `status` | installation + process session | forbidden | 90 days |
| `repository_selected` | User confirms a repository | none | none | session + selection UUID | repository name/path forbidden | 30 days |
| `scan_started` | Runtime accepts a real scan request | none | none | runtime scan ID | repository name/path/code forbidden | 30 days |
| `scan_completed` | That scan reaches a terminal success state | `outcome` | none | runtime scan ID | repository name/path/code forbidden | 90 days |
| `agent_connected` | A real agent connection is verified | `agent`, `status` | none | installation + agent + connection generation | credentials/config paths forbidden | 90 days |
| `ask_submitted` | Runtime accepts an Ask request | none | none | request UUID | raw prompt/code forbidden | 30 days |
| `ask_completed` | Ask request reaches a successful terminal state | `outcome` | none | request UUID | response/code forbidden | 90 days |

The desktop currently does not implement this canonical emitter. Desktop and installation metrics therefore remain unavailable, not inferred from account or page events.

## Delivery and failure behavior

Website delivery uses `sendBeacon` with a non-blocking `fetch(..., keepalive=true)` fallback. Client session storage prevents Strict Mode and route-rerender duplicates, and a unique database index on the server-hashed deduplication key makes retries idempotent. Analytics failures return an accepted-but-not-recorded response and never block rendering, auth, download state, or desktop workflows.
