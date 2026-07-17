# Atlas route security inventory (v1.0.5 source audit)

This is a source inventory, not a claim about a deployed environment.  It is
anchored to the three executable registries: `websites/atlas-web/app/api`,
`atlas_desktop.server._route_handlers`/`ACCOUNTS_ROUTES`, and
`atlas_desktop.mcp_server.runtime.TOOLS`.  An unlisted method is rejected (405
or 404); no route is discovered from user input.

Legend: **session** means a server-authoritative, HttpOnly session (`sid` is
looked up and revocation/expiry is checked); **origin** means canonical browser
Origin/Referer validation; **local** means loopback peer + exact Host/port +
same loopback Origin when present + per-runtime HttpOnly token.  All JSON
responses use private/no-store response helpers where account data is involved.

## Website API routes

| Method and route | Auth / role / ownership | Origin and validation | Limits / sensitive output / negative proof |
| --- | --- | --- | --- |
| `POST /api/auth/register` | none; server creates only `user` or configured-admin role and `free` plan | origin; validated email/password only | rate limited; generic failures; hostile origin and malformed input rejected |
| `POST /api/auth/login` | none before credentials; session is issued only after server password check | origin | 8/15m/IP; no user enumeration; hostile origin rejected |
| `POST /api/auth/logout` | session; revokes its server record | origin | no token returned; stale/revoked session rejected |
| `GET /api/auth/session` | session | GET | no password/token; invalid/expired/revoked session is anonymous |
| `POST /api/auth/forgot` | none | origin | rate limited and generic response; no account existence disclosure |
| `POST /api/auth/desktop/login` | native credentials; returned bearer is a server session | native client API, no cookie trust | rate limited; no role/plan input accepted |
| `POST /api/auth/desktop/register` | none; server-owned role and plan | native client API | validated credentials; caller cannot supply entitlement |
| `GET /api/auth/desktop/me` | bearer session | GET | safe user and server entitlement only |
| `POST /api/auth/desktop/logout` | bearer session; revokes its `sid` | native client API | no secret response |
| `POST /api/account/delete` | session; operation is the current user only | origin and explicit confirmation | no caller `user_id`; revokes all sessions before deletion |
| `GET /api/entitlements` | session; current user only | GET | server-calculated `free`; no client plan field |
| `GET /api/usage` | session; current user only | GET | account-keyed usage only; no arbitrary identity |
| `POST /api/checkout` | session, current user | origin | disabled provider returns `BILLING_NOT_AVAILABLE`; no checkout URL |
| `POST /api/billing/cancel` | session, current user | origin | disabled provider; no caller subscription ownership override |
| `POST /api/billing/portal` | session, current user | origin | disabled provider; no portal URL |
| `POST /api/paddle/webhook` | provider signature only | server-to-server | raw body/signature; disabled billing ignores events fail-closed |
| `POST /api/analytics/events` | optional safe session attribution only | canonical browser origin | 60/min/IP, 32 KiB, 20 events, depth 8, exact website event envelope; unknown fields/cross-origin rejected |
| `POST /api/analytics/desktop-events` | optional bearer attribution; never trusts supplied user id | native-only (Origin/Referer rejected) | 30/min/IP, 32 KiB, 20 events, depth 8, exact desktop envelope |
| `GET /api/admin/actions` | session + `requireAdmin` | GET | no caller role accepted; non-admin/anonymous denied |
| `POST /api/admin/actions` | session + `requireAdmin` | origin | validated action input; admin ownership is server-side |
| `GET /api/admin/analytics` | session + `requireAdmin` | GET | aggregate server query only; non-admin denied |
| `GET /api/admin/users` | session + `requireAdmin` | GET | server-authorized user view; non-admin denied |
| `GET,POST /api/admin/waitlist` | session + `requireAdmin` | POST requires origin | admin-only mutation; no public ownership field |
| `POST /api/waitlist` | public submission | origin where browser metadata exists | validated bounded fields/rate limit; no account privilege |
| `GET /api/health` | none | GET | operational, non-secret health only |

## Desktop local API registry

Every member of `server.ROUTES` has the following non-optional outer contract:
`local` authentication, 64 KiB object-only request body, JSON-only POST body,
no credentialed wildcard CORS, only `GET`, `POST`, `OPTIONS`, and 404/405 for
unknown method/path.  This includes all paths from `_route_handlers` and
`ACCOUNTS_ROUTES`; `GET /api/runtime/handshake` is the sole token-free
discovery exception and is challenge-bound, GET-only, loopback/Host checked.
Thus no dynamically registered local route is unclassified.

| Registry members | Route-specific authorization / ownership | Input and negative tests |
| --- | --- | --- |
| `/api/health`; `/api/demo/packs`; `/api/repositories/current/*`; `/api/repositories/recent`; `/api/history*`; `/api/analytics/summary`; `/api/analytics/preferences`; `/api/system/{diagnostics,startup-status,self-test,identity}`; `/api/product/*`; `/api/plans`; `/api/pricing`; `/api/billing/{config,plans,usage}`; `/api/integrations/*/status`; `/api/mcp/connections`; `/api/operations/*` | current local Atlas runtime only; repository reads operate on the selected persisted scan, never an arbitrary browser path | loopback token, hostile Origin, malformed JSON, Host/DNS-rebinding and wrong-method tests |
| `/api/repositories/{select,validate,estimate,scan,resume}`; `/api/repositories/current/{cancel-scan,build-full-graph,refresh-changed-files}`; `/api/repositories/diagnostics/scan`; `/api/system/{clear-cache,rebuild-index,support-bundle}` | current local runtime; repository path is validated by Atlas before scanning | body cap/object only, malicious path/unknown method rejected; scanner must not execute repository code |
| `/api/{impact,bug-investigation,context/export,copilot/ask}`; `/api/planning/{change,investigate,impact}`; `/api/integrations/{export,cursor/write-rule,cursor/write-config,claude/write-config,codex/write-config,claude-code/write-managed-block,mcp/test,mcp/diagnostics}` | current local runtime; protected workflow endpoints also receive account-gate decision from local account state | exact local origin/token required; config-write endpoints require explicit confirm; wrong token and hostile origin rejected |
| `/api/{feedback,feedback/result}`; `/api/operations/crash`; `/api/analytics/event`; `/api/analytics/preferences`; `/api/usage/event` | current local runtime; analytics applies local opt-out and allowlist | bounded body and local-token protection; failures never block workflow |
| `/api/system/browse-folder`; `/api/demo/{load,export-bundle}` | current local runtime only | local client/Host checks; desktop picker is not exposed to LAN clients |
| `/api/accounts/{state,register,login,logout,guest/start,guest/clear,profile,license,devices,devices/remove,service-status,validate-invite,acquisition/event}` | local account client; user identity originates from account service, never body `user_id` | local token/origin/body cap; account service errors are normalized |
| `/api/accounts/admin/{users,applications/pending,notifications,dashboard,audit-log,launch-readiness,feedback,invites,export/beta-users,interview-summary}` and POST admin approve/reject/grant-beta/revoke-beta/force-logout/update/feedback/update/invites | remote account service must authorize administrator; `user_id` is a target, not caller identity | local boundary plus account-service authorization; non-admin result is normalized/denied |

## MCP JSON-RPC methods

MCP accepts only JSON-RPC 2.0 `initialize`, `notifications/initialized`,
`notifications/cancelled`, `shutdown`, `notifications/exit`, `tools/list`, and
`tools/call`.  Requests are object-only, depth ≤16 and ≤64 KiB; tool
arguments must be objects; protocol errors are JSON-RPC errors; responses are
bounded to 512 KiB and stdout contains protocol messages only.

| Tool members of `TOOLS` | Authorization / ownership | Input / output policy |
| --- | --- | --- |
| `atlas_scan_repo` | local MCP process; repository path must be local/allowed | schema rejects undeclared top-level args; scanner boundary; compact sanitized result |
| `atlas_get_codebase_map`, `atlas_repo_summary`, `atlas_get_architecture`, `atlas_get_dependency_graph`, `atlas_find_file`, `atlas_repo_health` | current selected scan only; supplied repo path must match it | capped limits; no source bodies/secrets |
| `atlas_find_relevant_files`, `atlas_build_context_pack`, `atlas_what_breaks`, `atlas_get_impact_analysis`, `atlas_plan_change`, `atlas_get_change_plan`, `atlas_root_cause` | current selected scan only | declared schemas, bounded lists, sanitized compact evidence |
| `atlas_export_for_claude`, `atlas_export_for_cursor`, `atlas_export_for_codex`, `atlas_health` | current selected scan only | no write/config/process launch; secret/path sanitization and response size cap |

## Proof mapping and known environment boundary

- Website source proofs: `qa/analytics-auth.spec.ts` covers browser origin
  rejection, envelope/depth limits, sensitive redaction, server-owned session
  evidence, disabled billing and free-plan limits.
- Desktop source proofs: `atlas_desktop/tests/test_desktop_transport_boundary.py`
  covers exact loopback Host/Origin/runtime-token behavior;
  `atlas_desktop/tests/test_mcp_security_v105.py` covers malformed, oversized,
  nested and bounded-output JSON-RPC cases.
- Database-backed RLS, session rows, rate-limit storage and analytics retention
  require a sandbox database before they can be marked environment-verified.
