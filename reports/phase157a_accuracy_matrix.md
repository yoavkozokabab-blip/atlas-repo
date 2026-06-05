# Phase 157A - Accuracy Matrix

This matrix records all 150 sampled outputs. Evidence lists matched reviewer-expected anchors, not a guarantee that the answer was complete.

| Workflow | Samples | CORRECT | MOSTLY_CORRECT | PARTIALLY_CORRECT | MISLEADING | WRONG | Actionable % | Usable with review % | Unsafe % | Trust score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| build | 50 | 0 | 0 | 46 | 4 | 0 | 0.0 | 92.0 | 8.0 | 42.2 |
| investigation | 50 | 0 | 0 | 44 | 6 | 0 | 0.0 | 88.0 | 12.0 | 40.8 |
| impact | 50 | 12 | 3 | 28 | 2 | 5 | 30.0 | 86.0 | 14.0 | 54.4 |
| ALL | 150 | 12 | 3 | 118 | 12 | 5 | 10.0 | 88.7 | 11.3 | 45.8 |

| Repo | Workflow | Samples | CORRECT | MOSTLY_CORRECT | PARTIALLY_CORRECT | MISLEADING | WRONG | Trust score |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| home_assistant | build | 7 | 0 | 0 | 5 | 2 | 0 | 35.0 |
| home_assistant | investigation | 7 | 0 | 0 | 3 | 4 | 0 | 25.0 |
| home_assistant | impact | 7 | 0 | 0 | 6 | 1 | 0 | 40.0 |
| django | build | 7 | 0 | 0 | 6 | 1 | 0 | 40.0 |
| django | investigation | 7 | 0 | 0 | 7 | 0 | 0 | 45.0 |
| django | impact | 7 | 0 | 0 | 6 | 1 | 0 | 40.0 |
| fastapi | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| fastapi | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| fastapi | impact | 6 | 4 | 1 | 1 | 0 | 0 | 87.5 |
| vscode | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| vscode | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| vscode | impact | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| airflow | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| airflow | investigation | 6 | 0 | 0 | 4 | 2 | 0 | 33.3 |
| airflow | impact | 6 | 4 | 1 | 1 | 0 | 0 | 87.5 |
| celery | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| celery | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| celery | impact | 6 | 2 | 1 | 3 | 0 | 0 | 69.2 |
| typeorm | build | 6 | 0 | 0 | 5 | 1 | 0 | 39.2 |
| typeorm | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| typeorm | impact | 6 | 2 | 0 | 4 | 0 | 0 | 63.3 |
| kubernetes | build | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| kubernetes | investigation | 6 | 0 | 0 | 6 | 0 | 0 | 45.0 |
| kubernetes | impact | 6 | 0 | 0 | 1 | 0 | 5 | 7.5 |

## Per-Sample Records

| ID | Repo | Workflow | Classification | Failure category | Prompt / target | Evidence matched | Flags | Why |
|---:|---|---|---|---|---|---|---|---|
| 1 | home_assistant | build | PARTIALLY_CORRECT | thin_grounding | add websocket audit logging | websocket_api, auth, http | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 2 | home_assistant | build | MISLEADING | irrelevant_target_pollution | add event bus tracing | helpers/event | unknown, typing., dataclasses | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 3 | home_assistant | build | MISLEADING | irrelevant_target_pollution | add recorder retention policy | recorder | unknown, typing., dataclasses | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 4 | home_assistant | build | PARTIALLY_CORRECT | thin_grounding | add config entry validation | entry, flow | unknown, typing., dataclasses | Some expected anchors matched, but output was thin or noisy. |
| 5 | home_assistant | build | PARTIALLY_CORRECT | thin_grounding | add service call rate limiting | auth, http | unknown, typing., dataclasses | Some expected anchors matched, but output was thin or noisy. |
| 6 | home_assistant | build | PARTIALLY_CORRECT | thin_grounding | add automation execution telemetry | automation, event, trace | unknown, typing., dataclasses | Some expected anchors matched, but output was thin or noisy. |
| 7 | home_assistant | build | PARTIALLY_CORRECT | thin_grounding | add entity state cache invalidation | entity, helpers, core.py | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 8 | home_assistant | investigation | MISLEADING | nonsensical_root_cause | why are duplicate events being fired | helpers/event, automation | unknown, typing., dataclasses | Investigation named low-value syntax/import tokens as likely root cause. |
| 9 | home_assistant | investigation | MISLEADING | nonsensical_root_cause | why do websocket clients disconnect after auth refresh | auth, http | unknown, typing. | Investigation named low-value syntax/import tokens as likely root cause. |
| 10 | home_assistant | investigation | MISLEADING | nonsensical_root_cause | why recorder writes stop after database reconnect | recorder, database | unknown, typing. | Investigation named low-value syntax/import tokens as likely root cause. |
| 11 | home_assistant | investigation | PARTIALLY_CORRECT | thin_grounding | why config entries are setup twice | config_entries, setup, entry, flow | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 12 | home_assistant | investigation | PARTIALLY_CORRECT | thin_grounding | why automations run twice after reload | automation, reload, trace | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 13 | home_assistant | investigation | MISLEADING | nonsensical_root_cause | why state changes are not observed by listeners | event, helpers | unknown, typing. | Investigation named low-value syntax/import tokens as likely root cause. |
| 14 | home_assistant | investigation | PARTIALLY_CORRECT | thin_grounding | why services sometimes execute without permissions | services, auth, permissions | unknown | Some expected anchors matched, but output was thin or noisy. |
| 15 | home_assistant | impact | MISLEADING | irrelevant_target_pollution | homeassistant/core.py | homeassistant | package.json, unknown | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 16 | home_assistant | impact | PARTIALLY_CORRECT | thin_grounding | homeassistant/components/websocket_api/connection.py | websocket_api, connection, auth, http | package.json | Some expected anchors matched, but output was thin or noisy. |
| 17 | home_assistant | impact | PARTIALLY_CORRECT | thin_grounding | homeassistant/config_entries.py | config_entries, flow, entry | package.json | Some expected anchors matched, but output was thin or noisy. |
| 18 | home_assistant | impact | PARTIALLY_CORRECT | thin_grounding | homeassistant/components/recorder/__init__.py | recorder, history, database, homeassistant | package.json, random, typing. | Some expected anchors matched, but output was thin or noisy. |
| 19 | home_assistant | impact | PARTIALLY_CORRECT | thin_grounding | homeassistant/helpers/event.py | helpers/event, event | package.json, random, typing. | Some expected anchors matched, but output was thin or noisy. |
| 20 | home_assistant | impact | PARTIALLY_CORRECT | thin_grounding | homeassistant/components/automation/__init__.py | automation, trace, event | package.json, random, typing. | Some expected anchors matched, but output was thin or noisy. |
| 21 | home_assistant | impact | PARTIALLY_CORRECT | thin_grounding | homeassistant/components/http/__init__.py | http, auth, request, server | package.json, random, typing. | Some expected anchors matched, but output was thin or noisy. |
| 22 | django | build | PARTIALLY_CORRECT | thin_grounding | add request rate limiting middleware | middleware, request, response | unknown | Some expected anchors matched, but output was thin or noisy. |
| 23 | django | build | PARTIALLY_CORRECT | thin_grounding | add auth session rotation | contrib/auth, sessions, middleware, login | unknown | Some expected anchors matched, but output was thin or noisy. |
| 24 | django | build | PARTIALLY_CORRECT | thin_grounding | add ORM query cache invalidation | db/models, query, cache | random, unknown | Some expected anchors matched, but output was thin or noisy. |
| 25 | django | build | PARTIALLY_CORRECT | thin_grounding | add async view tracing | middleware, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 26 | django | build | MISLEADING | irrelevant_target_pollution | add migration safety checker | migrations | unknown | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 27 | django | build | PARTIALLY_CORRECT | thin_grounding | add template rendering metrics | template, render, context | unknown | Some expected anchors matched, but output was thin or noisy. |
| 28 | django | build | PARTIALLY_CORRECT | thin_grounding | add admin permission audit log | contrib/admin, auth, permission, log | unknown | Some expected anchors matched, but output was thin or noisy. |
| 29 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why middleware runs twice for one request | middleware, handler, request, response | fallback, unknown | Some expected anchors matched, but output was thin or noisy. |
| 30 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why users stay logged in after session rotation | auth, middleware | unknown | Some expected anchors matched, but output was thin or noisy. |
| 31 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why queryset cache returns stale objects | queryset, db/models, cache | random, unknown, pathlib | Some expected anchors matched, but output was thin or noisy. |
| 32 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why async view exceptions are swallowed | exception, middleware | unknown | Some expected anchors matched, but output was thin or noisy. |
| 33 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why migrations run in the wrong order | migrations, graph | unknown | Some expected anchors matched, but output was thin or noisy. |
| 34 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why template context variables disappear | template, context | unknown | Some expected anchors matched, but output was thin or noisy. |
| 35 | django | investigation | PARTIALLY_CORRECT | thin_grounding | why admin permission checks are inconsistent | admin, auth, permission | unknown | Some expected anchors matched, but output was thin or noisy. |
| 36 | django | impact | MISLEADING | irrelevant_target_pollution | django/core/handlers/base.py | handlers | fallback | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 37 | django | impact | PARTIALLY_CORRECT | thin_grounding | django/contrib/auth/__init__.py | auth, user, session | fallback | Some expected anchors matched, but output was thin or noisy. |
| 38 | django | impact | PARTIALLY_CORRECT | thin_grounding | django/db/models/base.py | models, field, query, manager | fallback | Some expected anchors matched, but output was thin or noisy. |
| 39 | django | impact | PARTIALLY_CORRECT | thin_grounding | django/db/migrations/executor.py | migrations, executor | fallback | Some expected anchors matched, but output was thin or noisy. |
| 40 | django | impact | PARTIALLY_CORRECT | thin_grounding | django/template/base.py | template, render, context, loader | fallback | Some expected anchors matched, but output was thin or noisy. |
| 41 | django | impact | PARTIALLY_CORRECT | thin_grounding | django/contrib/admin/options.py | admin, auth | fallback | Some expected anchors matched, but output was thin or noisy. |
| 42 | django | impact | PARTIALLY_CORRECT | thin_grounding | django/urls/resolvers.py | urls, resolver, pattern | fallback | Some expected anchors matched, but output was thin or noisy. |
| 43 | fastapi | build | PARTIALLY_CORRECT | thin_grounding | add request rate limiting | middleware, routing, applications, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 44 | fastapi | build | PARTIALLY_CORRECT | thin_grounding | add distributed request tracing | middleware, applications, routing, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 45 | fastapi | build | PARTIALLY_CORRECT | thin_grounding | add websocket authentication checks | websocket, routing, security, dependencies | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 46 | fastapi | build | PARTIALLY_CORRECT | thin_grounding | add OpenAPI schema cache invalidation | openapi, applications, schema, utils | unknown | Some expected anchors matched, but output was thin or noisy. |
| 47 | fastapi | build | PARTIALLY_CORRECT | thin_grounding | add dependency injection validation | dependencies, utils, security, routing | unknown | Some expected anchors matched, but output was thin or noisy. |
| 48 | fastapi | build | PARTIALLY_CORRECT | thin_grounding | add background task metrics | background, routing, applications | unknown | Some expected anchors matched, but output was thin or noisy. |
| 49 | fastapi | investigation | PARTIALLY_CORRECT | thin_grounding | why middleware runs twice on one request | middleware, applications, routing, request | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 50 | fastapi | investigation | PARTIALLY_CORRECT | thin_grounding | why websocket auth fails after dependency override | websocket, dependencies, security, routing | unknown, typing. | Some expected anchors matched, but output was thin or noisy. |
| 51 | fastapi | investigation | PARTIALLY_CORRECT | thin_grounding | why OpenAPI schema is stale after route changes | openapi, schema, applications, routing | unknown | Some expected anchors matched, but output was thin or noisy. |
| 52 | fastapi | investigation | PARTIALLY_CORRECT | thin_grounding | why dependencies are executed in the wrong order | dependencies, utils, routing | unknown | Some expected anchors matched, but output was thin or noisy. |
| 53 | fastapi | investigation | PARTIALLY_CORRECT | thin_grounding | why exception handlers hide validation errors | exception, handlers, validation, applications | unknown | Some expected anchors matched, but output was thin or noisy. |
| 54 | fastapi | investigation | PARTIALLY_CORRECT | thin_grounding | why background tasks do not run after response | background, response, routing, tasks | unknown | Some expected anchors matched, but output was thin or noisy. |
| 55 | fastapi | impact | CORRECT | repo_grounded | fastapi/applications.py | applications, routing, middleware, openapi |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 56 | fastapi | impact | PARTIALLY_CORRECT | thin_grounding | fastapi/routing.py | routing, request |  | Some expected anchors matched, but output was thin or noisy. |
| 57 | fastapi | impact | CORRECT | repo_grounded | fastapi/dependencies/utils.py | dependencies, solve, security, routing |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 58 | fastapi | impact | MOSTLY_CORRECT | repo_grounded_with_limits | fastapi/openapi/utils.py | openapi, routing, models |  | Matched core expected anchors, but evidence was not complete enough for full trust. |
| 59 | fastapi | impact | CORRECT | repo_grounded | fastapi/middleware/asyncexitstack.py | middleware, asyncexitstack, exception, request |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 60 | fastapi | impact | CORRECT | repo_grounded | fastapi/security/oauth2.py | security, oauth2, dependencies, auth |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 61 | vscode | build | PARTIALLY_CORRECT | thin_grounding | add command palette telemetry | workbench, telemetry, contrib | unknown | Some expected anchors matched, but output was thin or noisy. |
| 62 | vscode | build | PARTIALLY_CORRECT | thin_grounding | add extension activation diagnostics | extension, activation, workbench | unknown | Some expected anchors matched, but output was thin or noisy. |
| 63 | vscode | build | PARTIALLY_CORRECT | thin_grounding | add workspace trust enforcement | workspace, trust, workbench | unknown | Some expected anchors matched, but output was thin or noisy. |
| 64 | vscode | build | PARTIALLY_CORRECT | thin_grounding | add editor save debounce | editor, save, workbench, files | unknown | Some expected anchors matched, but output was thin or noisy. |
| 65 | vscode | build | PARTIALLY_CORRECT | thin_grounding | add file watcher retry logging | files, watcher, platform, workspace | unknown | Some expected anchors matched, but output was thin or noisy. |
| 66 | vscode | build | PARTIALLY_CORRECT | thin_grounding | add terminal process tracing | terminal, process, workbench | unknown | Some expected anchors matched, but output was thin or noisy. |
| 67 | vscode | investigation | PARTIALLY_CORRECT | thin_grounding | why command palette commands disappear after reload | commands, registry, extension | unknown | Some expected anchors matched, but output was thin or noisy. |
| 68 | vscode | investigation | PARTIALLY_CORRECT | thin_grounding | why extension activation runs twice | extension, activation | unknown | Some expected anchors matched, but output was thin or noisy. |
| 69 | vscode | investigation | PARTIALLY_CORRECT | thin_grounding | why workspace trust disables expected features | workspace, trust, configuration, workbench | unknown | Some expected anchors matched, but output was thin or noisy. |
| 70 | vscode | investigation | PARTIALLY_CORRECT | thin_grounding | why editor saves trigger duplicate file events | editor, save, files | unknown | Some expected anchors matched, but output was thin or noisy. |
| 71 | vscode | investigation | PARTIALLY_CORRECT | thin_grounding | why file watcher misses changes in workspace folders | files, watcher, workspace, platform | unknown | Some expected anchors matched, but output was thin or noisy. |
| 72 | vscode | investigation | PARTIALLY_CORRECT | thin_grounding | why terminal process output arrives out of order | terminal, process, workbench | unknown | Some expected anchors matched, but output was thin or noisy. |
| 73 | vscode | impact | PARTIALLY_CORRECT | thin_grounding | src/vs/workbench/api/common/extHostExtensionService.ts | extension, extHost, workbench | package.json, eslint, fallback, random | Some expected anchors matched, but output was thin or noisy. |
| 74 | vscode | impact | PARTIALLY_CORRECT | thin_grounding | src/vs/workbench/services/editor/common/editorService.ts | editor, workbench, service, save | package.json, eslint, fallback, random | Some expected anchors matched, but output was thin or noisy. |
| 75 | vscode | impact | PARTIALLY_CORRECT | thin_grounding | src/vs/platform/files/common/files.ts | files, watcher, platform, resource | package.json, eslint, fallback, random | Some expected anchors matched, but output was thin or noisy. |
| 76 | vscode | impact | PARTIALLY_CORRECT | thin_grounding | src/vs/workbench/contrib/terminal/browser/terminalInstance.ts | terminal, process, pty, workbench | package.json, eslint, fallback, random | Some expected anchors matched, but output was thin or noisy. |
| 77 | vscode | impact | PARTIALLY_CORRECT | thin_grounding | src/vs/platform/commands/common/commands.ts | commands, registry, platform, handler | package.json, eslint, fallback, random | Some expected anchors matched, but output was thin or noisy. |
| 78 | vscode | impact | PARTIALLY_CORRECT | thin_grounding | src/vs/workbench/services/configuration/common/configuration.ts | configuration, workspace, workbench, service | package.json, eslint, fallback, random | Some expected anchors matched, but output was thin or noisy. |
| 79 | airflow | build | PARTIALLY_CORRECT | thin_grounding | add DAG parse cache diagnostics | dag, parse, airflow-core | unknown, __future__.annotations | Some expected anchors matched, but output was thin or noisy. |
| 80 | airflow | build | PARTIALLY_CORRECT | thin_grounding | add scheduler heartbeat metrics | scheduler, heartbeat, jobs, airflow-core | unknown, __future__.annotations | Some expected anchors matched, but output was thin or noisy. |
| 81 | airflow | build | PARTIALLY_CORRECT | thin_grounding | add task retry backoff policy | taskinstance, retry, executor, dag | unknown, __future__.annotations | Some expected anchors matched, but output was thin or noisy. |
| 82 | airflow | build | PARTIALLY_CORRECT | thin_grounding | add executor queue metrics | executor, queue, scheduler, task | unknown, __future__.annotations, typing. | Some expected anchors matched, but output was thin or noisy. |
| 83 | airflow | build | PARTIALLY_CORRECT | thin_grounding | add connection secret rotation audit | connection, airflow-core | unknown, __future__.annotations | Some expected anchors matched, but output was thin or noisy. |
| 84 | airflow | build | PARTIALLY_CORRECT | thin_grounding | add webserver RBAC audit logging | www, rbac, security | unknown, __future__.annotations, typing. | Some expected anchors matched, but output was thin or noisy. |
| 85 | airflow | investigation | MISLEADING | irrelevant_target_pollution | why DAG parsing is slow after deploy | dag | unknown, __future__.annotations | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 86 | airflow | investigation | PARTIALLY_CORRECT | thin_grounding | why scheduler heartbeat reports stale state | scheduler, heartbeat, job | unknown, __future__.annotations | Some expected anchors matched, but output was thin or noisy. |
| 87 | airflow | investigation | MISLEADING | nonsensical_root_cause | why task retries ignore backoff | taskinstance, backoff | unknown, __future__.annotations | Investigation named low-value syntax/import tokens as likely root cause. |
| 88 | airflow | investigation | PARTIALLY_CORRECT | thin_grounding | why executor queue is not draining | executor, queue, scheduler | unknown, __future__.annotations, typing. | Some expected anchors matched, but output was thin or noisy. |
| 89 | airflow | investigation | PARTIALLY_CORRECT | thin_grounding | why secrets are exposed in logs | secrets, mask, logging | eslint, unknown, __future__.annotations | Some expected anchors matched, but output was thin or noisy. |
| 90 | airflow | investigation | PARTIALLY_CORRECT | thin_grounding | why webserver permissions differ by user | auth, rbac, security | unknown | Some expected anchors matched, but output was thin or noisy. |
| 91 | airflow | impact | CORRECT | repo_grounded | airflow-core/src/airflow/jobs/scheduler_job_runner.py | scheduler, job, dag, task |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 92 | airflow | impact | CORRECT | repo_grounded | airflow-core/src/airflow/models/dag.py | dag, task, schedule, airflow |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 93 | airflow | impact | CORRECT | repo_grounded | airflow-core/src/airflow/models/taskinstance.py | taskinstance, retry, state, executor |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 94 | airflow | impact | MOSTLY_CORRECT | repo_grounded_with_limits | airflow-core/src/airflow/executors/base_executor.py | executor, task, state |  | Matched core expected anchors, but evidence was not complete enough for full trust. |
| 95 | airflow | impact | PARTIALLY_CORRECT | thin_grounding | airflow-core/src/airflow/www/app.py | app, auth |  | Some expected anchors matched, but output was thin or noisy. |
| 96 | airflow | impact | CORRECT | repo_grounded | airflow-core/src/airflow/secrets/base_secrets.py | secrets, connection, backend, config |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 97 | celery | build | PARTIALLY_CORRECT | thin_grounding | add task retry jitter | task, retry, celery/app, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 98 | celery | build | PARTIALLY_CORRECT | thin_grounding | add broker reconnect backoff | consumer, connection, broker, worker | unknown | Some expected anchors matched, but output was thin or noisy. |
| 99 | celery | build | PARTIALLY_CORRECT | thin_grounding | add worker heartbeat telemetry | worker, heartbeat | unknown | Some expected anchors matched, but output was thin or noisy. |
| 100 | celery | build | PARTIALLY_CORRECT | thin_grounding | add result backend TTL cleanup | backend, result, ttl | unknown | Some expected anchors matched, but output was thin or noisy. |
| 101 | celery | build | PARTIALLY_CORRECT | thin_grounding | add beat schedule validation | beat, schedule, scheduler, entry | unknown | Some expected anchors matched, but output was thin or noisy. |
| 102 | celery | build | PARTIALLY_CORRECT | thin_grounding | add chord failure handling | chord, canvas, backend | unknown | Some expected anchors matched, but output was thin or noisy. |
| 103 | celery | investigation | PARTIALLY_CORRECT | thin_grounding | why task retries happen immediately without jitter | task, retry, backoff, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 104 | celery | investigation | PARTIALLY_CORRECT | thin_grounding | why worker loses broker connection repeatedly | consumer, broker, connection, worker | unknown | Some expected anchors matched, but output was thin or noisy. |
| 105 | celery | investigation | PARTIALLY_CORRECT | thin_grounding | why heartbeat stops while worker is alive | worker, heartbeat, events, consumer | fallback, unknown | Some expected anchors matched, but output was thin or noisy. |
| 106 | celery | investigation | PARTIALLY_CORRECT | thin_grounding | why result backend grows without cleanup | backend, result, cleanup | fallback, unknown | Some expected anchors matched, but output was thin or noisy. |
| 107 | celery | investigation | PARTIALLY_CORRECT | thin_grounding | why beat schedule fires twice | beat, schedule, scheduler, entry | fallback, unknown | Some expected anchors matched, but output was thin or noisy. |
| 108 | celery | investigation | PARTIALLY_CORRECT | thin_grounding | why chord callback is never called after group failure | chord, backend, group | fallback, unknown | Some expected anchors matched, but output was thin or noisy. |
| 109 | celery | impact | CORRECT | repo_grounded | celery/app/task.py | task, retry, request, app |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 110 | celery | impact | MOSTLY_CORRECT | repo_grounded_with_limits | celery/worker/worker.py | worker, consumer, app |  | Matched core expected anchors, but evidence was not complete enough for full trust. |
| 111 | celery | impact | CORRECT | repo_grounded | celery/beat.py | beat, schedule, scheduler, entry |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 112 | celery | impact | PARTIALLY_CORRECT | thin_grounding | celery/backends/base.py | backend, result, state | fallback | Some expected anchors matched, but output was thin or noisy. |
| 113 | celery | impact | PARTIALLY_CORRECT | thin_grounding | celery/canvas.py | canvas, chord |  | Some expected anchors matched, but output was thin or noisy. |
| 114 | celery | impact | PARTIALLY_CORRECT | thin_grounding | celery/worker/consumer/consumer.py | consumer, worker |  | Some expected anchors matched, but output was thin or noisy. |
| 115 | typeorm | build | PARTIALLY_CORRECT | thin_grounding | add transaction retry support | queryrunner, transaction, driver, datasource | unknown | Some expected anchors matched, but output was thin or noisy. |
| 116 | typeorm | build | PARTIALLY_CORRECT | thin_grounding | add migration locking | migration, datasource, queryrunner | unknown | Some expected anchors matched, but output was thin or noisy. |
| 117 | typeorm | build | PARTIALLY_CORRECT | thin_grounding | add query builder cache metrics | cache, query | unknown | Some expected anchors matched, but output was thin or noisy. |
| 118 | typeorm | build | MISLEADING | irrelevant_target_pollution | add relation loading telemetry | relation | .prettierrc, prettier, unknown | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| 119 | typeorm | build | PARTIALLY_CORRECT | thin_grounding | add connection pool limits | driver, datasource, connection, pool | .prettierrc, prettier, unknown | Some expected anchors matched, but output was thin or noisy. |
| 120 | typeorm | build | PARTIALLY_CORRECT | thin_grounding | add schema sync guardrail | schema, schema-builder, migration, metadata | unknown | Some expected anchors matched, but output was thin or noisy. |
| 121 | typeorm | investigation | PARTIALLY_CORRECT | thin_grounding | why transaction rollback does not release connection | transaction, queryrunner, connection, driver | unknown | Some expected anchors matched, but output was thin or noisy. |
| 122 | typeorm | investigation | PARTIALLY_CORRECT | thin_grounding | why migrations run twice on startup | migration, datasource | unknown | Some expected anchors matched, but output was thin or noisy. |
| 123 | typeorm | investigation | PARTIALLY_CORRECT | thin_grounding | why query builder cache returns stale rows | querybuilder, cache, select, query | unknown | Some expected anchors matched, but output was thin or noisy. |
| 124 | typeorm | investigation | PARTIALLY_CORRECT | thin_grounding | why lazy relations trigger too many queries | relation, metadata | unknown | Some expected anchors matched, but output was thin or noisy. |
| 125 | typeorm | investigation | PARTIALLY_CORRECT | thin_grounding | why connection pool is exhausted under load | driver, pool, datasource, connection | unknown | Some expected anchors matched, but output was thin or noisy. |
| 126 | typeorm | investigation | PARTIALLY_CORRECT | thin_grounding | why schema sync drops columns unexpectedly | schema, builder, metadata | unknown | Some expected anchors matched, but output was thin or noisy. |
| 127 | typeorm | impact | PARTIALLY_CORRECT | thin_grounding | src/query-builder/QueryBuilder.ts | querybuilder, query, expressionmap, connection | fallback | Some expected anchors matched, but output was thin or noisy. |
| 128 | typeorm | impact | PARTIALLY_CORRECT | thin_grounding | src/data-source/DataSource.ts | datasource, connection, manager, driver | fallback | Some expected anchors matched, but output was thin or noisy. |
| 129 | typeorm | impact | PARTIALLY_CORRECT | thin_grounding | src/migration/MigrationExecutor.ts | migration, executor, datasource, queryrunner | fallback | Some expected anchors matched, but output was thin or noisy. |
| 130 | typeorm | impact | CORRECT | repo_grounded | src/metadata/RelationMetadata.ts | relation, metadata, entity, join |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 131 | typeorm | impact | CORRECT | repo_grounded | src/driver/Driver.ts | driver, connection, queryrunner, database |  | Matched multiple expected repo-specific anchors with no obvious hallucination marker. |
| 132 | typeorm | impact | PARTIALLY_CORRECT | thin_grounding | src/schema-builder/RdbmsSchemaBuilder.ts | schema, builder, metadata, migration | fallback | Some expected anchors matched, but output was thin or noisy. |
| 133 | kubernetes | build | PARTIALLY_CORRECT | thin_grounding | add admission webhook timeout metrics | admission, webhook | unknown | Some expected anchors matched, but output was thin or noisy. |
| 134 | kubernetes | build | PARTIALLY_CORRECT | thin_grounding | add API server audit logging | audit, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 135 | kubernetes | build | PARTIALLY_CORRECT | thin_grounding | add scheduler plugin latency metrics | scheduler, plugin, framework | unknown | Some expected anchors matched, but output was thin or noisy. |
| 136 | kubernetes | build | PARTIALLY_CORRECT | thin_grounding | add controller retry backoff telemetry | controller, retry | unknown | Some expected anchors matched, but output was thin or noisy. |
| 137 | kubernetes | build | PARTIALLY_CORRECT | thin_grounding | add kubelet pod lifecycle tracing | kubelet, pod, runtime | unknown | Some expected anchors matched, but output was thin or noisy. |
| 138 | kubernetes | build | PARTIALLY_CORRECT | thin_grounding | add CRD schema validation warnings | crd, validation, schema | unknown | Some expected anchors matched, but output was thin or noisy. |
| 139 | kubernetes | investigation | PARTIALLY_CORRECT | thin_grounding | why admission webhook latency spikes | admission, webhook | unknown | Some expected anchors matched, but output was thin or noisy. |
| 140 | kubernetes | investigation | PARTIALLY_CORRECT | thin_grounding | why audit events are missing for requests | audit, request | unknown | Some expected anchors matched, but output was thin or noisy. |
| 141 | kubernetes | investigation | PARTIALLY_CORRECT | thin_grounding | why scheduler plugin latency is high | scheduler, plugin | unknown | Some expected anchors matched, but output was thin or noisy. |
| 142 | kubernetes | investigation | PARTIALLY_CORRECT | thin_grounding | why deployment controller retries forever | deployment, controller | unknown | Some expected anchors matched, but output was thin or noisy. |
| 143 | kubernetes | investigation | PARTIALLY_CORRECT | thin_grounding | why kubelet restarts pods unexpectedly | kubelet, pod, runtime | unknown | Some expected anchors matched, but output was thin or noisy. |
| 144 | kubernetes | investigation | PARTIALLY_CORRECT | thin_grounding | why CRD validation rejects valid schema | validation, crd, schema | unknown | Some expected anchors matched, but output was thin or noisy. |
| 145 | kubernetes | impact | WRONG | target_resolution_failure | pkg/kubelet/kubelet.go | kubelet, runtime | target not found, no module node matched, unknown | Known existing target was not resolved. |
| 146 | kubernetes | impact | WRONG | target_resolution_failure | pkg/scheduler/scheduler.go | scheduler | target not found, no module node matched, unknown | Known existing target was not resolved. |
| 147 | kubernetes | impact | WRONG | target_resolution_failure | pkg/controller/deployment/deployment_controller.go | deployment, controller | target not found, no module node matched, unknown | Known existing target was not resolved. |
| 148 | kubernetes | impact | WRONG | target_resolution_failure | staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go | admission, webhook, dispatcher, validating | target not found, no module node matched, unknown | Known existing target was not resolved. |
| 149 | kubernetes | impact | WRONG | target_resolution_failure | staging/src/k8s.io/apiserver/pkg/audit/request.go | audit, request, apiserver | target not found, no module node matched, unknown | Known existing target was not resolved. |
| 150 | kubernetes | impact | PARTIALLY_CORRECT | thin_grounding | staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go | validation, crd | unknown | Some expected anchors matched, but output was thin or noisy. |
