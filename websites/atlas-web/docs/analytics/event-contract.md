# Atlas analytics event contract

Status: canonical analytics-only release contract, version 1. Times are recorded by Postgres in UTC. The server is the authority for `environment`, `app_version`, `build_commit`, `user_id`, and `created_at`.

## Privacy and identity rules

- Website events use a random, stable browser `anonymous_id` and a per-tab `session_id`. The browser may never submit a `user_id`.
- Desktop events require a random canonical UUID installation identifier and a per-process session identifier. Malformed, empty, padded, or non-UUID installation identifiers are rejected rather than coerced or replaced. They never reuse a repository identifier as an identity.
- Allowed metadata keys are `agent`, `href_kind`, `http_status`, `outcome`, `plan`, `reason_code`, `status`, `surface`, coarse duration fields, and coarse campaign/device fields. Values must be one-level JSON strings, finite numbers, or booleans; nested objects, arrays, and `null` are rejected. Unknown primitive keys are discarded by the server.
- Email addresses, names, IP addresses, source code, repository names, full or relative local paths, raw prompts, cookies, authorization headers, tokens, and secrets are forbidden.
- Production, preview, development, and test events are separate `environment` values. Preview, localhost, tests, bots, and known QA sessions are `is_internal=true` and excluded from default metrics.
- Raw events are retained only as long as needed to validate aggregate product metrics. Review at 90 days and aggregate or expire them under an approved retention policy.

Every accepted event includes: UUID `id`, server `created_at`, exact `event_name`, `source`, optional server-derived `user_id`, optional anonymous/session identifiers, `environment`, route, application version, build commit, platform, contract version, SHA-256 `deduplication_key`, internal flag, and allowlisted metadata.

## Website events

The analytics-only release has exactly four browser events. The endpoint rejects all other event names, including account, Ask, health-check, heartbeat, and UI-render events.

| Event | Source | Exact trigger | Required properties | Optional properties | Deduplication | PII | Retention |
|---|---|---|---|---|---|---|---|
| `site_visit` | website | First mounted Atlas page in a browser session | none | campaign fields | anonymous ID + session ID | forbidden | 90 days |
| `page_view` | website | One completed route transition | route | campaign fields | session ID + route | forbidden | 90 days |
| `download_clicked` | website | A user activates a real `/download` link | route, `surface` | campaign fields | unique click UUID | forbidden | 90 days |
| `installer_download_started` | server | The installer route starts a verified asset response | route | none | request/asset UUID | forbidden | 90 days |

Website click events alone are not evidence of a completed installer download. Completion must be proven by the served executable matching the verified release SHA256 or by a trusted delivery-provider signal. If the installer is hosted by GitHub Releases, GitHub's asset count is the source for raw file downloads; Atlas records only the click/start request and later `desktop_launched` events.

## Desktop events

The desktop sender is limited to these eight events. Accounts and Ask remain disabled in this release, so no account or Ask event is valid.

| Event | Exact trigger | Required properties | Optional properties | Deduplication | PII / repository data | Retention |
|---|---|---|---|---|---|---|
| `desktop_launched` | Fresh Atlas process reaches runtime ready | app version, build | coarse status/duration | installation + process session | forbidden | 90 days |
| `sample_scan_completed` | Bundled sample scan reaches a terminal state | `outcome` | coarse duration | runtime scan ID | forbidden | 90 days |
| `real_repo_scan_completed` | A real repository scan reaches a terminal state | `outcome` | coarse duration | runtime scan ID | forbidden | 90 days |
| `scan_failed` | A scan reaches a handled failure state | `reason_code` | coarse duration | runtime scan ID | forbidden | 30 days |
| `graph_opened` | Graph view is opened | none | coarse duration | session + view UUID | forbidden | 90 days |
| `impact_completed` | Impact analysis reaches a terminal state | `outcome` | coarse duration | runtime analysis ID | forbidden | 90 days |
| `mcp_connected` | MCP connection is verified | `agent`, `status` | none | installation + connection generation | forbidden | 90 days |
| `onboarding_local_mode_selected` | User chooses Continue without an account | `surface` | none | installation | forbidden | 90 days |
| `repository_selected` | A repository is chosen for scanning | `surface`, `repo_size_bucket` | none | installation | forbidden - never the name or path | 90 days |
| `scan_started` | A scan begins | `repo_size_bucket`, `workflow` | none | installation | forbidden | 90 days |
| `mcp_configured` | MCP config written for an agent | `agent`, `outcome` | none | installation + agent | forbidden | 90 days |
| `mcp_initialize_success` | An agent completed MCP initialize | `agent`, `outcome` | none | installation + agent | forbidden | 90 days |
| `atlas_tool_called` | An Atlas MCP tool executed | `tool_name`, `agent`, `outcome`, `duration_elapsed_ms` | none | installation + tool | forbidden - never arguments or responses | 90 days |
| `first_value_reached` | First successful meaningful tool execution, once per installation | `tool_name`, `agent` | none | installation (exactly once) | forbidden | 90 days |
| `feedback_opened` | Feedback form opened | `surface` | none | installation | forbidden | 90 days |
| `feedback_submitted` | Feedback delivered to the server | `category`, `outcome` | none | installation | forbidden - never the message text | 90 days |
| `analytics_opted_out` | User confirms analytics opt-out | none | none | installation + opt-out transition | forbidden | 90 days |

## Delivery and failure behavior

Website delivery uses a non-blocking `fetch(..., keepalive=true)` fallback. Client session storage prevents Strict Mode and route-rerender duplicates, and a unique database index on the server-hashed deduplication key makes retries idempotent. Analytics failures never block rendering, auth, download state, or desktop workflows. Invalid payloads receive a controlled `4xx`; transient storage failures are handled as best-effort delivery failures.
