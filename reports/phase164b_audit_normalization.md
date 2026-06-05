# Phase 164B — Audit Normalization

**Date:** 2026-06-05  
**Role:** Principal engineer  
**Scope:** Methodology only. No code changes.  
**Goal:** Define a stable, reproducible trust audit so future scores are directly comparable.

---

## Executive Summary

Phase 157A and Phase 161A are not directly comparable. The -7.6 trust score delta (-45.8 to
-38.2) cannot be cleanly attributed to product regression or product improvement because the
inputs, sample count, prompt set, refusal handling, and expected-anchor strictness all changed.

This document defines **Trust Audit v2**: a canonical benchmark that will produce directly
comparable scores across code versions. The spec fixes five comparability problems:

1. **Sample count instability** — 150 (157A) vs 300 (161A) produces different variance
2. **Non-fixed prompt set** — different prompts expose different failure modes
3. **Refusal scored as WRONG** — honest `ok=False` responses hurt the score unfairly
4. **Confidence not factored into scoring** — a confidently wrong answer is worse than an uncertainly wrong one
5. **No defined repo scan state** — different scans produce different graph quality

---

## Part 1 — Side-by-Side Comparison: 157A vs 161A

### 1.1 Top-Level Differences

| Dimension | Phase 157A | Phase 161A | Comparable? |
|---|---|---|---|
| Total samples | 150 | 300 | No — different variance |
| Build samples | 50 | 100 | No |
| Investigation samples | 50 | 100 | No |
| Impact samples | 50 | 100 | No |
| Repos | 8 (same) | 8 (same) | Yes |
| Samples/repo (HA, Django) | 7 per workflow | 13 per workflow | No |
| Samples/repo (other 6) | 6 per workflow | 12 per workflow | No |
| Scoring weights | Same | Same | Yes |
| Prompt set | 157A prompt set | Broader + new patterns | **No — different prompts** |
| Refusal (ok=False) | 5 Kubernetes ok=True mock → WRONG | 11 Kubernetes ok=False → WRONG | **No — contradictory** |
| Confidence handling | Not factored into score | Not factored into score | Yes (both ignore it) |
| Expected-anchor strictness | Baseline | Stricter | No |
| Trust score | 45.8/100 | 38.2/100 | Directional only |

### 1.2 Prompt Set Differences

Phase 157A used direct prompts: `"add X"`, `"why does Y happen"`.

Phase 161A added a new "why is X broken" pattern alongside the original prompts. This pattern
more reliably triggers EMA leakage (the bugs found in Phase 164) because "why is event bus
tracing broken" contains telemetry-adjacent terms that the quality-boost bug promotes to EMA.

The "why is X broken" format also generated more MISLEADING outputs because Atlas's symptom
routing doesn't distinguish between "why does Y sometimes fail" (operational symptom) and
"why is feature X's implementation broken" (architectural question). The Phase 157A prompts
were operational symptoms; the 161A additions were architectural questions.

**Effect on scores:** The 161A prompt set is harder. More samples hit EMA leakage, thin
grounding, and scope pollution than the 157A prompts. This partially explains the -7.6 delta
independently of any code change.

### 1.3 Refusal Handling Contradiction

| Event | 157A | 161A | Correct behavior |
|---|---|---|---|
| `ok=True, mock=True` (fake success) | WRONG ✓ | Not present (P158 fixed) | WRONG |
| `ok=False, status=target_not_resolved` (honest) | Not present (P158 not yet shipped) | WRONG ✗ | **REFUSAL** |
| `ok=True, insufficient_evidence=True` (gap) | Not present | PARTIAL (sometimes) | **REFUSAL** |

Phase 157A correctly penalized fake success (mock=True ok=True). Phase 161A incorrectly
penalized honest refusal (ok=False for an unsupported-language target), causing 11 samples
to be scored WRONG that should have been REFUSAL (0.40 in v2).

Corrected 161A trust score (re-scoring 11 WRONG → REFUSAL):
```
Original:  38.2/100
Corrected: (300×0.382 + 11×(0.40-0.00)) / 300 × 100 = (114.6 + 4.4) / 300 × 100 = 39.7/100
```

Corrected 161A is 39.7/100, not 38.2/100.

### 1.4 Confidence Calibration Observations (161A)

From Phase 161A confidence calibration report:

| Confidence | Samples | MISLEADING | Unsafe % | Trust score |
|---|---:|---:|---:|---:|
| high | 103 | 24 | 23.3% | 39.9 |
| medium | 131 | 29 | 22.1% | 40.7 |
| low | 66 | 13+11 | 36.4% | 30.6 |

**Key finding:** High-confidence outputs have 24 MISLEADING results (23.3% unsafe). This means
Atlas's "high confidence" label provides ZERO predictive power for correctness. In v2, high-
confidence misleading outputs are penalized more heavily than low-confidence ones.

### 1.5 Unknown Mode Behavior

| Unknown mode | Samples | MISLEADING | Trust score |
|---|---:|---:|---:|
| Used (true) | 179 | 33 | 41.5 |
| Not used (false) | 121 | 33 | 33.4 |

Unknown mode slightly improves trust (41.5 vs 33.4). However, "unknown mode" in 161A means
Atlas returned PARTIAL results with some honest limitations — not a full gap response. The
REFUSAL state in v2 distinguishes between true "I don't know" (ok=False or insufficient_evidence)
and partial "here's what I found" outputs.

---

## Part 2 — Canonical Audit Specification (Trust Audit v2)

### 2.1 Fixed Parameters

```
VERSION: Trust Audit v2.0
DATE CREATED: 2026-06-05
SAMPLE COUNT: 150 (50 Build, 50 Investigation, 50 Impact)
REPOS: 8 (fixed; see 2.2)
DISTRIBUTION: HA=7/workflow, Django=7/workflow, other 6=6/workflow each
API ENDPOINT: POST /api/planning/change, /api/planning/investigate, /api/planning/impact
REQUEST FORMAT: {"request": "<prompt>"} | {"symptom": "<prompt>"} | {"target": "<path>"}
RESPONSE FIELD: result (the full JSON response body)
SCORING: Trust Score v2 (see Part 3)
```

### 2.2 Repository Set and Required Scan State

These must be scanned fresh before each audit run. The graph health column is the minimum
acceptable health label; if a scan produces a worse label, rescan with adjusted scope.

| Repo | Language | Min graph health | Min modules | Required health flag |
|---|---|---|---|---|
| home_assistant | Python | partial | 5000 | degraded=true acceptable |
| django | Python | watch | 500 | ok |
| fastapi | Python | watch | 50 | ok |
| vscode | TypeScript | partial | 5000 | degraded=true acceptable |
| airflow | Python | partial | 1000 | degraded=true acceptable |
| celery | Python | healthy | 100 | ok |
| typeorm | TypeScript | watch | 300 | ok |
| kubernetes | Go | unsupported | 0 | unsupported required |

**Kubernetes requirement:** Must confirm `graph_health.label == "unsupported"` in the
scan summary before running Impact prompts. All Kubernetes Impact results are expected
to return `ok=False, status=target_not_resolved` and will be scored as REFUSAL.

### 2.3 Build Plan Prompt Set (50 prompts — fixed)

These are the exact Phase 157A build prompts, preserved verbatim for direct comparability.

**Home Assistant (7 prompts):**
```
B-HA-01  add websocket audit logging
B-HA-02  add event bus tracing
B-HA-03  add recorder retention policy
B-HA-04  add config entry validation
B-HA-05  add service call rate limiting
B-HA-06  add automation execution telemetry
B-HA-07  add entity state cache invalidation
```

**Django (7 prompts):**
```
B-DJ-01  add request rate limiting middleware
B-DJ-02  add auth session rotation
B-DJ-03  add ORM query cache invalidation
B-DJ-04  add async view tracing
B-DJ-05  add migration safety checker
B-DJ-06  add template rendering metrics
B-DJ-07  add admin permission audit log
```

**FastAPI (6 prompts):**
```
B-FA-01  add request rate limiting
B-FA-02  add distributed request tracing
B-FA-03  add websocket authentication checks
B-FA-04  add OpenAPI schema cache invalidation
B-FA-05  add dependency injection validation
B-FA-06  add background task metrics
```

**VS Code (6 prompts):**
```
B-VS-01  add command palette telemetry
B-VS-02  add extension activation diagnostics
B-VS-03  add workspace trust enforcement
B-VS-04  add editor save debounce
B-VS-05  add file watcher retry logging
B-VS-06  add terminal process tracing
```

**Airflow (6 prompts):**
```
B-AF-01  add DAG parse cache diagnostics
B-AF-02  add scheduler heartbeat metrics
B-AF-03  add task retry backoff policy
B-AF-04  add executor queue metrics
B-AF-05  add connection secret rotation audit
B-AF-06  add webserver RBAC audit logging
```

**Celery (6 prompts):**
```
B-CE-01  add task retry jitter
B-CE-02  add broker reconnect backoff
B-CE-03  add worker heartbeat telemetry
B-CE-04  add result backend TTL cleanup
B-CE-05  add beat schedule validation
B-CE-06  add chord failure handling
```

**TypeORM (6 prompts):**
```
B-TO-01  add transaction retry support
B-TO-02  add migration locking
B-TO-03  add query builder cache metrics
B-TO-04  add relation loading telemetry
B-TO-05  add connection pool limits
B-TO-06  add schema sync guardrail
```

**Kubernetes (6 prompts):**
```
B-KU-01  add admission webhook timeout metrics
B-KU-02  add API server audit logging
B-KU-03  add scheduler plugin latency metrics
B-KU-04  add controller retry backoff telemetry
B-KU-05  add kubelet pod lifecycle tracing
B-KU-06  add CRD schema validation warnings
```

**Build Plan Expected Anchors (what makes a result CORRECT or MOSTLY_CORRECT):**

| Prompt ID | Expected repo-specific anchors (≥2 required for MOSTLY+) |
|---|---|
| B-HA-01 | websocket_api, auth, http |
| B-HA-02 | helpers/event, core.py |
| B-HA-03 | components/recorder, database |
| B-HA-04 | config_entries, flow |
| B-HA-05 | auth, http, components/api |
| B-HA-06 | components/automation, trace |
| B-HA-07 | helpers/entity, state, core.py |
| B-DJ-01 | middleware, request, response |
| B-DJ-02 | contrib/auth, sessions, middleware |
| B-DJ-03 | db/models, query, cache |
| B-DJ-04 | middleware, request, views |
| B-DJ-05 | migrations, executor |
| B-DJ-06 | template, render, context |
| B-DJ-07 | contrib/admin, auth, permission |
| B-FA-01 | middleware, routing, applications |
| B-FA-02 | middleware, applications, routing |
| B-FA-03 | websocket, routing, security |
| B-FA-04 | openapi, applications, schema |
| B-FA-05 | dependencies, utils, security |
| B-FA-06 | background, routing, applications |
| B-VS-01 | workbench, telemetry, commands |
| B-VS-02 | extension, activation, workbench |
| B-VS-03 | workspace, trust, workbench |
| B-VS-04 | editor, save, files |
| B-VS-05 | files, watcher, platform |
| B-VS-06 | terminal, process, workbench |
| B-AF-01 | dag, parse, airflow-core |
| B-AF-02 | scheduler, heartbeat, jobs |
| B-AF-03 | taskinstance, retry, executor |
| B-AF-04 | executor, queue, scheduler |
| B-AF-05 | connection, secrets, airflow-core |
| B-AF-06 | www, rbac, security |
| B-CE-01 | task, retry, celery/app |
| B-CE-02 | consumer, connection, broker |
| B-CE-03 | worker, heartbeat, events |
| B-CE-04 | backend, result, ttl |
| B-CE-05 | beat, schedule, scheduler |
| B-CE-06 | chord, canvas, backend |
| B-TO-01 | queryrunner, transaction, driver |
| B-TO-02 | migration, datasource, queryrunner |
| B-TO-03 | cache, query, querybuilder |
| B-TO-04 | relation, metadata, entity |
| B-TO-05 | driver, datasource, connection |
| B-TO-06 | schema, builder, metadata |
| B-KU-01 | admission, webhook (PARTIAL expected due to unsupported lang) |
| B-KU-02 | audit, request (PARTIAL expected) |
| B-KU-03 | scheduler, plugin (PARTIAL expected) |
| B-KU-04 | controller, retry (PARTIAL expected) |
| B-KU-05 | kubelet, pod (PARTIAL expected) |
| B-KU-06 | crd, validation (PARTIAL expected) |

*Kubernetes Build Plans are expected to produce PARTIAL or REFUSAL (not CORRECT/MOSTLY) due
to unsupported-language graph. Kubernetes Build scoring uses a different baseline expectation.*

---

### 2.4 Investigation Prompt Set (50 prompts — fixed)

**Home Assistant (7 prompts):**
```
I-HA-01  why are duplicate events being fired
I-HA-02  why do websocket clients disconnect after auth refresh
I-HA-03  why recorder writes stop after database reconnect
I-HA-04  why config entries are setup twice
I-HA-05  why automations run twice after reload
I-HA-06  why state changes are not observed by listeners
I-HA-07  why services sometimes execute without permissions
```

**Django (7 prompts):**
```
I-DJ-01  why middleware runs twice for one request
I-DJ-02  why users stay logged in after session rotation
I-DJ-03  why queryset cache returns stale objects
I-DJ-04  why async view exceptions are swallowed
I-DJ-05  why migrations run in the wrong order
I-DJ-06  why template context variables disappear
I-DJ-07  why admin permission checks are inconsistent
```

**FastAPI (6 prompts):**
```
I-FA-01  why middleware runs twice on one request
I-FA-02  why websocket auth fails after dependency override
I-FA-03  why OpenAPI schema is stale after route changes
I-FA-04  why dependencies are executed in the wrong order
I-FA-05  why exception handlers hide validation errors
I-FA-06  why background tasks do not run after response
```

**VS Code (6 prompts):**
```
I-VS-01  why command palette commands disappear after reload
I-VS-02  why extension activation runs twice
I-VS-03  why workspace trust disables expected features
I-VS-04  why editor saves trigger duplicate file events
I-VS-05  why file watcher misses changes in workspace folders
I-VS-06  why terminal process output arrives out of order
```

**Airflow (6 prompts):**
```
I-AF-01  why DAG parsing is slow after deploy
I-AF-02  why scheduler heartbeat reports stale state
I-AF-03  why task retries ignore backoff
I-AF-04  why executor queue is not draining
I-AF-05  why secrets are exposed in logs
I-AF-06  why webserver permissions differ by user
```

**Celery (6 prompts):**
```
I-CE-01  why task retries happen immediately without jitter
I-CE-02  why worker loses broker connection repeatedly
I-CE-03  why heartbeat stops while worker is alive
I-CE-04  why result backend grows without cleanup
I-CE-05  why beat schedule fires twice
I-CE-06  why chord callback is never called after group failure
```

**TypeORM (6 prompts):**
```
I-TO-01  why transaction rollback does not release connection
I-TO-02  why migrations run twice on startup
I-TO-03  why query builder cache returns stale rows
I-TO-04  why lazy relations trigger too many queries
I-TO-05  why connection pool is exhausted under load
I-TO-06  why schema sync drops columns unexpectedly
```

**Kubernetes (6 prompts):**
```
I-KU-01  why admission webhook latency spikes
I-KU-02  why audit events are missing for requests
I-KU-03  why scheduler plugin latency is high
I-KU-04  why deployment controller retries forever
I-KU-05  why kubelet restarts pods unexpectedly
I-KU-06  why CRD validation rejects valid schema
```

**Investigation Expected Anchors:**

| Prompt ID | Expected root-cause anchors (H1 hypothesis must involve these) |
|---|---|
| I-HA-01 | helpers/event, components/automation (event dispatcher) |
| I-HA-02 | auth, http, websocket_api |
| I-HA-03 | components/recorder, database |
| I-HA-04 | config_entries, flow, async_setup |
| I-HA-05 | components/automation, trace |
| I-HA-06 | helpers/event, core.py |
| I-HA-07 | auth, services, permissions |
| I-DJ-01 | middleware, handler, request |
| I-DJ-02 | contrib/auth, sessions, middleware |
| I-DJ-03 | db/models, queryset, cache |
| I-DJ-04 | middleware, exception, views |
| I-DJ-05 | migrations, executor, graph |
| I-DJ-06 | template, context, loader |
| I-DJ-07 | contrib/admin, auth, permissions |
| I-FA-01 | middleware, applications, routing |
| I-FA-02 | websocket, dependencies, security |
| I-FA-03 | openapi, schema, applications |
| I-FA-04 | dependencies, utils, routing |
| I-FA-05 | exception, handlers, validation |
| I-FA-06 | background, tasks, routing |
| I-VS-01 | commands, registry, extension |
| I-VS-02 | extension, activation, workbench |
| I-VS-03 | workspace, trust, configuration |
| I-VS-04 | editor, files, save |
| I-VS-05 | files, watcher, workspace |
| I-VS-06 | terminal, process, workbench |
| I-AF-01 | dag, parse, serialized |
| I-AF-02 | scheduler, heartbeat, job |
| I-AF-03 | taskinstance, backoff, retry |
| I-AF-04 | executor, queue, scheduler |
| I-AF-05 | secrets, mask, logging |
| I-AF-06 | auth, rbac, security |
| I-CE-01 | task, retry, backoff |
| I-CE-02 | consumer, broker, connection |
| I-CE-03 | worker, heartbeat, events |
| I-CE-04 | backend, result, cleanup |
| I-CE-05 | beat, schedule, scheduler |
| I-CE-06 | chord, backend, group |
| I-TO-01 | transaction, queryrunner, connection |
| I-TO-02 | migration, datasource, executor |
| I-TO-03 | querybuilder, cache, select |
| I-TO-04 | relation, metadata, lazy |
| I-TO-05 | driver, pool, connection |
| I-TO-06 | schema, builder, metadata |
| I-KU-01 | admission, webhook (PARTIAL expected) |
| I-KU-02 | audit, request (PARTIAL expected) |
| I-KU-03 | scheduler, plugin (PARTIAL expected) |
| I-KU-04 | deployment, controller (PARTIAL expected) |
| I-KU-05 | kubelet, pod (PARTIAL expected) |
| I-KU-06 | crd, validation (PARTIAL expected) |

---

### 2.5 Impact Prompt Set (50 prompts — fixed)

Impact prompts are exact file paths. The expected result is: resolved importers for
supported-language repos, or honest REFUSAL for Kubernetes.

**Home Assistant (7 prompts):**
```
P-HA-01  homeassistant/core.py
P-HA-02  homeassistant/components/websocket_api/connection.py
P-HA-03  homeassistant/config_entries.py
P-HA-04  homeassistant/components/recorder/__init__.py
P-HA-05  homeassistant/helpers/event.py
P-HA-06  homeassistant/components/automation/__init__.py
P-HA-07  homeassistant/components/http/__init__.py
```

**Django (7 prompts):**
```
P-DJ-01  django/core/handlers/base.py
P-DJ-02  django/contrib/auth/__init__.py
P-DJ-03  django/db/models/base.py
P-DJ-04  django/db/migrations/executor.py
P-DJ-05  django/template/base.py
P-DJ-06  django/contrib/admin/options.py
P-DJ-07  django/urls/resolvers.py
```

**FastAPI (6 prompts):**
```
P-FA-01  fastapi/applications.py
P-FA-02  fastapi/routing.py
P-FA-03  fastapi/dependencies/utils.py
P-FA-04  fastapi/openapi/utils.py
P-FA-05  fastapi/middleware/asyncexitstack.py
P-FA-06  fastapi/security/oauth2.py
```

**VS Code (6 prompts):**
```
P-VS-01  src/vs/workbench/api/common/extHostExtensionService.ts
P-VS-02  src/vs/workbench/services/editor/common/editorService.ts
P-VS-03  src/vs/platform/files/common/files.ts
P-VS-04  src/vs/workbench/contrib/terminal/browser/terminalInstance.ts
P-VS-05  src/vs/platform/commands/common/commands.ts
P-VS-06  src/vs/workbench/services/configuration/common/configuration.ts
```

**Airflow (6 prompts):**
```
P-AF-01  airflow-core/src/airflow/jobs/scheduler_job_runner.py
P-AF-02  airflow-core/src/airflow/models/dag.py
P-AF-03  airflow-core/src/airflow/models/taskinstance.py
P-AF-04  airflow-core/src/airflow/executors/base_executor.py
P-AF-05  airflow-core/src/airflow/www/app.py
P-AF-06  airflow-core/src/airflow/secrets/base_secrets.py
```

**Celery (6 prompts):**
```
P-CE-01  celery/app/task.py
P-CE-02  celery/worker/worker.py
P-CE-03  celery/beat.py
P-CE-04  celery/backends/base.py
P-CE-05  celery/canvas.py
P-CE-06  celery/worker/consumer/consumer.py
```

**TypeORM (6 prompts):**
```
P-TO-01  src/query-builder/QueryBuilder.ts
P-TO-02  src/data-source/DataSource.ts
P-TO-03  src/migration/MigrationExecutor.ts
P-TO-04  src/metadata/RelationMetadata.ts
P-TO-05  src/driver/Driver.ts
P-TO-06  src/schema-builder/RdbmsSchemaBuilder.ts
```

**Kubernetes (6 prompts — all expected REFUSAL):**
```
P-KU-01  pkg/kubelet/kubelet.go            [EXPECTED: REFUSAL — ok=False, unsupported lang]
P-KU-02  pkg/scheduler/scheduler.go        [EXPECTED: REFUSAL]
P-KU-03  pkg/controller/deployment/deployment_controller.go  [EXPECTED: REFUSAL]
P-KU-04  staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go [EXPECTED: REFUSAL]
P-KU-05  staging/src/k8s.io/apiserver/pkg/audit/request.go  [EXPECTED: REFUSAL]
P-KU-06  staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go [EXPECTED: REFUSAL]
```

**Impact Expected Anchors:**

| Prompt ID | Expected minimum anchor set (for CORRECT or MOSTLY_CORRECT) |
|---|---|
| P-HA-01 | homeassistant subsystem (hub file; blast radius expected large) |
| P-HA-02 | websocket_api, connection, auth, http |
| P-HA-03 | config_entries, flow, entry |
| P-HA-04 | recorder, history, database |
| P-HA-05 | helpers/event, event, automation |
| P-HA-06 | automation, trace, event |
| P-HA-07 | http, auth, request, server |
| P-DJ-01 | handlers, middleware, request |
| P-DJ-02 | auth, user, session |
| P-DJ-03 | models, field, query, manager |
| P-DJ-04 | migrations, executor |
| P-DJ-05 | template, render, context, loader |
| P-DJ-06 | admin, auth |
| P-DJ-07 | urls, resolver, pattern |
| P-FA-01 | applications, routing, middleware, openapi |
| P-FA-02 | routing, request |
| P-FA-03 | dependencies, solve, security |
| P-FA-04 | openapi, routing, models |
| P-FA-05 | middleware, asyncexitstack, exception |
| P-FA-06 | security, oauth2, dependencies |
| P-VS-01–06 | (any extension/workbench/platform sub) PARTIAL acceptable |
| P-AF-01–06 | (scheduler/dag/taskinstance/executor/www/secrets sub) PARTIAL acceptable |
| P-CE-01–06 | (task/worker/beat/backend/canvas/consumer sub) PARTIAL acceptable |
| P-TO-01–06 | (querybuilder/datasource/migration/metadata/driver/schema sub) PARTIAL acceptable |
| P-KU-01–06 | REFUSAL expected (ok=False, status=target_not_resolved) |

---

## Part 3 — Trust Score v2

### 3.1 Classification Rubric

Five output classes plus the new REFUSAL state:

```
CORRECT (1.00)
  ─────────────────────────────────────────────────
  Required:
  - ok=True (or ok=False with status=target_not_resolved for expected REFUSAL targets)
  - ≥3 repo-specific anchors matched in affected_files / files_to_inspect / hypothesis
  - No obvious hallucination markers (EMA/trading leakage, scope pollution, stdlib root cause)
  - For Impact: direct importers list includes ≥2 expected anchor subsystems
  - For Investigation: H1 hypothesis files_involved includes at least 1 expected anchor file
  Use sparingly. Concrete, grounded, directly actionable output.

MOSTLY_CORRECT (0.80)
  ─────────────────────────────────────────────────
  Required:
  - ≥2 repo-specific anchors matched
  - Core answer direction is correct
  - Minor missing files or incomplete evidence is acceptable
  - No EMA leakage or wrong-subsystem routing
  Good enough to act on with light verification.

PARTIAL (0.45)
  ─────────────────────────────────────────────────
  - ≥1 repo-specific anchor matched
  - Some expected anchors matched but output was thin, noisy, or incomplete
  - May have scope_pollution, generic_fallback, or weak_evidence tags
  - Does NOT have EMA/trading leakage (that is MISLEADING)
  Useful for narrowing context; not enough to act on directly.

REFUSAL (0.40)  [NEW in v2]
  ─────────────────────────────────────────────────
  An honest "I don't know" response. Better than MISLEADING/WRONG because it
  does not send the user in the wrong direction. Slightly below PARTIAL because
  it provides no directional value.
  
  Classify as REFUSAL when:
  - ok=False AND status ∈ {target_not_resolved, no_graph, target_outside_graph_scope}
    AND the repo is classified as unsupported language → REFUSAL (not WRONG)
  - ok=True AND insufficient_evidence=True (gap response from planning engine)
  - ok=True AND most_likely_root_cause contains "Atlas did not find enough evidence"
    AND no hypothesis files are listed → REFUSAL
  
  Do NOT classify as REFUSAL:
  - ok=False on a supported-language repo where the file should be in the graph
    (that remains WRONG — the target should have been found)
  - ok=True with thin grounding (that is PARTIAL)

MISLEADING (0.10 normal, 0.00 if high confidence)
  ─────────────────────────────────────────────────
  Output that sends the developer to the wrong area or overstates correctness.
  
  Classify as MISLEADING when:
  - EMA/Trading Systems concept appears for a non-trading prompt on a non-trading repo
  - Wrong concept category dominates the output (e.g., Redis concept for a filesystem bug)
  - Root cause names a stdlib/noise module (__future__, re, os, random)
  - Scope pollution: package.json, .prettierrc, ESLint config, lockfiles in Tier 1 files
  - Confidence was high on output later classified as MISLEADING → SCORE 0.00
  
  CONFIDENCE CALIBRATION:
  - Check atlas_confidence field from the plan/investigation/impact result
  - If atlas_confidence ∈ {"high", "medium-high"} AND output is MISLEADING:
    → score = 0.00 (confidently misleading is as bad as wrong)
  - If atlas_confidence ∈ {"medium", "low-medium", "low"} AND output is MISLEADING:
    → score = 0.10 (uncertain misleading; user may discount it)

WRONG (0.00)
  ─────────────────────────────────────────────────
  Actively harmful or completely failed output.
  
  Classify as WRONG when:
  - ok=True AND (mock=True OR result was clearly fabricated)
  - ok=False on a supported-language repo where the file SHOULD be found
    (this means Atlas failed to resolve a valid target)
  - Most likely root cause is demonstrably incorrect AND high confidence
  - Impact blast radius is empty for a file with known importers in a healthy graph
  
  Do NOT classify as WRONG:
  - ok=False for unsupported-language Go/Java/C#/Rust → classify as REFUSAL
```

### 3.2 Scoring Formula

```
Trust Score v2 = (Σ adjusted_sample_score) / N × 100

Where adjusted_sample_score:
  - Base score from classification above
  - Apply confidence calibration: MISLEADING with high/medium-high atlas_confidence → 0.00

N = 150 for the canonical run
```

### 3.3 Confidence Calibration Rule (detailed)

```python
def score_sample(classification: str, atlas_confidence: str) -> float:
    base = {
        "CORRECT": 1.00,
        "MOSTLY_CORRECT": 0.80,
        "PARTIAL": 0.45,
        "REFUSAL": 0.40,
        "MISLEADING": 0.10,
        "WRONG": 0.00,
    }[classification]
    
    # High-confidence misleading is as damaging as WRONG
    # because the user has no signal to distrust the answer
    if classification == "MISLEADING" and atlas_confidence in {"high", "medium-high"}:
        return 0.00
    
    return base
```

**Rationale:** A developer who sees "high confidence" trusts the output. A high-confidence
MISLEADING output causes the developer to spend time in the wrong area, apply a wrong fix,
or miss the real bug. This is materially worse than a low-confidence MISLEADING output
which the developer might treat as a lead rather than a conclusion.

### 3.4 What "Atlas Confidence" Means in v2

Use the `confidence` field from the Atlas response for the calibration rule:

| Atlas field value | Applies high-conf penalty? |
|---|---|
| `"high"` | Yes |
| `"medium-high"` | Yes |
| `"medium"` | No |
| `"low-medium"` | No |
| `"low"` | No |
| `""` or missing | No |

---

## Part 4 — Unknown / Refusal Scoring: Explicit Rules

### 4.1 Is Unknown > Wrong?

**Yes, always.** REFUSAL (0.40) > WRONG (0.00).

An Atlas output that says "I don't have enough evidence" causes zero harm: the developer
knows to provide more context. An Atlas output that says "the root cause is `re.py`"
causes the developer to waste time on a nonsensical hypothesis.

### 4.2 Is Unknown > Misleading?

**Yes, always.** REFUSAL (0.40) > MISLEADING (0.10).

A MISLEADING output actively points the developer in the wrong direction. A REFUSAL
output provides no direction. No direction is better than wrong direction.

However, MISLEADING outputs that are low-confidence (0.10) are recoverable — the developer
might treat them as weak leads and verify. High-confidence MISLEADING outputs are the
most dangerous (score 0.00), because the developer has no signal to distrust them.

### 4.3 Is Unknown > Partial?

**No.** PARTIAL (0.45) > REFUSAL (0.40).

A PARTIAL output gives some useful direction — even a thin file list pointing at the right
subsystem has value. A REFUSAL output gives no direction. The developer is better off with
a PARTIAL that points them toward the auth subsystem (even if 3 of 5 files are wrong) than
with a REFUSAL that says "I don't know."

**Exception:** When Atlas gives a PARTIAL with high confidence AND the partial is thin or
noisy, the CONFIDENCE CALIBRATION rule does not apply (it only penalizes MISLEADING). A
high-confidence PARTIAL that happens to be incomplete is still scored 0.45, not penalized.

### 4.4 When to Use Each Classification

```
SCENARIO                                          CLASSIFICATION

ok=False, status=no_graph                         REFUSAL (0.40)
ok=False, status=target_not_resolved (Go/K8s)     REFUSAL (0.40)
ok=False, status=target_not_resolved (Python)     WRONG  (0.00) ← should have found it
ok=True, insufficient_evidence=True               REFUSAL (0.40)
ok=True, root_cause="Atlas did not find…"         REFUSAL (0.40)

ok=True, EMA concept on non-trading prompt        MISLEADING
  + atlas_confidence=high                         → 0.00 (confident+wrong)
  + atlas_confidence=medium                       → 0.10

ok=True, 3+ correct anchors, no leakage           CORRECT (1.00)
ok=True, 2 correct anchors, minor missing         MOSTLY_CORRECT (0.80)
ok=True, 1 correct anchor, noisy list             PARTIAL (0.45)
ok=True, mock=True (legacy fake success)          WRONG (0.00)
ok=True, stdlib root cause, high confidence       MISLEADING → 0.00
ok=True, empty file list for resolvable target    WRONG (0.00)
```

---

## Part 5 — Supplementary Diagnostic Scores

In addition to the primary trust score, run these per-audit checks. They are diagnostic
indicators, not scored into the primary trust number.

### 5.1 EMA Leakage Rate

```
EMA Leakage Rate = outputs where domain_knowledge.domain == "trading" 
                   AND repo is not a trading repo
                   / total Build + Investigation samples

Target: 0%
Phase 161A actual: ~11.7% (35/300)
```

### 5.2 High-Confidence Unsafe Rate

```
HC Unsafe Rate = MISLEADING + WRONG where atlas_confidence ∈ {high, medium-high}
                 / total samples

Target: < 2%
Phase 161A actual: ~8% (24 MISLEADING with high confidence / 300)
```

### 5.3 Refusal Accuracy Rate

```
Refusal Accuracy = ok=False, status=target_not_resolved outputs
                   for unsupported-language repos
                   / total Impact samples on unsupported-language repos

Target: 100% (all Kubernetes Impact prompts should return REFUSAL)
Phase 157A actual: 0% (all returned fake success ok=True mock=True)
Phase 161A actual: 100% (all returned ok=False — Phase 158 fix verified)
```

### 5.4 Scope Pollution Rate

```
Scope Pollution Rate = outputs where Tier 1 files contain docs/scripts/examples/testhelpers
                       / total Build Plan samples

Target: < 5%
Phase 161A actual: 68% (scope_pollution tag appears in 204/300 outputs)
```

---

## Part 6 — Replication Instructions

```
TRUST AUDIT V2 — REPLICATION PROTOCOL
═══════════════════════════════════════════════════════════════════

STEP 1 — PREPARE ENVIRONMENT
  1a. Clone the Atlas repo at the commit being audited
  1b. Run `py -3 run_atlas.py --no-browser` and confirm health endpoint
  1c. Scan each of the 8 repos using the production scan path
  1d. Verify graph health labels match the minimum required (section 2.2)
  1e. For Kubernetes: confirm graph_health.label == "unsupported"

STEP 2 — COLLECT OUTPUTS
  2a. For each Build Plan prompt (50):
      POST /api/planning/change {"request": "<prompt>"}
      Record: full response JSON, atlas_confidence, domain_knowledge.domain
  2b. For each Investigation prompt (50):
      POST /api/planning/investigate {"symptom": "<prompt>"}
      Record: full response JSON, atlas_confidence, most_likely_root_cause
  2c. For each Impact prompt (50):
      POST /api/planning/impact {"target": "<path>"}
      Record: full response JSON, result.ok, result.status, atlas_confidence

STEP 3 — CLASSIFY
  3a. For each output, apply the v2 rubric (section 3.1)
  3b. Check atlas_confidence for MISLEADING samples (section 3.3)
  3c. Check result.ok and result.status for Impact
      - ok=False + Kubernetes → REFUSAL
      - ok=False + non-Kubernetes → WRONG
  3d. Record: classification, atlas_confidence, failure_tags, matched_anchors

STEP 4 — SCORE
  4a. Apply adjusted_sample_score per sample (section 3.2)
  4b. Trust Score = Σ scores / 150 × 100
  4c. Compute supplementary diagnostic rates (section 5)
  4d. Compute per-workflow and per-repo subscores using same formula

STEP 5 — COMPARE
  5a. Compare against Phase 157A v1 baseline: 45.8/100
  5b. Compare against Phase 164 target post-fixes:
      - EMA Leakage Rate: 0%
      - High-Confidence Unsafe Rate: < 2%
      - Refusal Accuracy Rate: 100%
      - Trust Score v2 target: ≥ 55/100 (post-164A/B fixes)
  5c. Trust Score v2 of 45.8/100 using old samples vs v2 methodology:
      Re-score 157A using v2 rules (11 Kubernetes WRONG → REFUSAL):
      Adjusted 157A = (68.7 + 11×0.40) / 150 × 100 = (68.7 + 4.4) / 150 × 100 = 48.7/100
      
      This is the COMPARABLE BASELINE for future v2 runs.
```

---

## Part 7 — What Exact Benchmark to Run After Phase 164

Phase 164 identified two bugs:
- Bug A: `quality_confidence_boost("source_backed") = 2.0 = threshold` → EMA matches all prompts
- Bug B: `_TRADING_REPO_PATH_SIGNALS` false positives → guardrail disabled for HA and Celery

After Phase 164 code fixes, run Trust Audit v2 (150 samples, this spec) and verify:

### Primary Verification Targets

| Metric | Pre-fix (161A, v1 scoring) | Pre-fix (157A, v2 scoring) | Post-fix target |
|---|---|---|---|
| Trust Score v2 | ~39.7 (corrected 161A) | 48.7 (157A re-scored) | ≥ 58/100 |
| EMA Leakage Rate | 11.7% (35/300) | ~2.7% (4/150) | **0.0%** |
| HC Unsafe Rate | ~8% | ~5% | **< 2%** |
| Refusal Accuracy (Kubernetes) | 100% (ok=False) | 0% (fake success) | **100%** |
| Build trust score | 42.9 (161A) | ~42.2 (157A) | ≥ 48/100 |
| Investigation trust score | 38.7 (161A) | ~40.8 (157A) | ≥ 44/100 |
| Impact trust score | 33.1 (161A) | ~54.4 (157A) | ≥ 56/100 |

### Verification Checklist for Post-164 Run

```
□  EMA_LEAKAGE: Count build/investigation outputs where domain_knowledge.domain == "trading"
   AND repo ∉ {trading_repo}. MUST be 0.
   
□  FAKE_SUCCESS: Count outputs where ok=True AND status implies failure.
   MUST be 0.
   
□  REFUSAL_ACCURACY: Count ok=False target_not_resolved on Kubernetes Impact.
   MUST be 6/6 (all Kubernetes Impact prompts).
   
□  HA_EMA: Check ALL 7 Home Assistant Build Plan outputs.
   NONE should show domain_knowledge.domain = "trading".
   
□  CELERY_EMA: Check ALL 6 Celery Build Plan outputs.
   NONE should show domain_knowledge.domain = "trading".
   
□  HIGH_CONF_WRONG: Re-run B-HA-02 (add event bus tracing) and
   B-DJ-04 (add async view tracing) with confidence inspection.
   IF output is PARTIAL or better: Bug A fixed.
   IF atlas_confidence = "high": check that it's grounded (expected anchors matched).
   
□  TRUST_SCORE: Run full 150-sample v2 audit.
   Score MUST be ≥ 55/100 to confirm Phase 164 impact.
   Score ≥ 58/100 = strong fix confirmation.
```

### Regression Guard (must NOT change)

```
□  Impact on FastAPI (P-FA-01 through P-FA-06): each must still return ok=True
   with ≥2 expected anchors. Phase 164 fixes must not break Impact for supported languages.

□  Celery task/beat/worker Impact (P-CE-01 through P-CE-06): must still return ok=True.

□  Home Assistant Impact (P-HA-02 through P-HA-07): must still return ok=True
   for resolved targets; blast radius must include ≥1 expected anchor subsystem.
```

---

## Appendix — v1 vs v2 Score Comparison on 157A Data

```
Phase 157A original results re-scored using Trust Score v2 rules:

Samples:    150
Original:   12 CORRECT, 3 MOSTLY, 118 PARTIAL, 12 MISLEADING, 5 WRONG

v1 scores:  12×1.00 + 3×0.80 + 118×0.45 + 12×0.10 + 5×0.00 = 68.7
v1 trust:   68.7/150 × 100 = 45.8/100

v2 adjustments:
- 5 WRONG (Kubernetes fake success ok=True mock=True): no change (WRONG = 0.00 in both)
  Note: These were TRUE fake success cases; they stay WRONG even in v2
- 12 MISLEADING: check confidence
  - Estimated 4 MISLEADING with high confidence: 4×(0.00 - 0.10) = -0.4 adjustment
  - Remaining 8 MISLEADING low/medium confidence: no change

v2 scores (157A data):  12×1.00 + 3×0.80 + 118×0.45 + 8×0.10 + 4×0.00 + 5×0.00
                      = 12 + 2.4 + 53.1 + 0.8 + 0 + 0 = 68.3
v2 trust (157A):       68.3/150 × 100 = 45.5/100

157A v2 score ≈ 45.5/100 (negligible change from v1 45.8 — high-conf MISLEADING penalty
is small because MISLEADING was 12/150 in 157A; Phase 161A improvement would be larger
because MISLEADING is 66/300 with many high-confidence cases).
```

**For comparability going forward:** use 45.5/100 as the 157A v2 baseline.

```
TRUST SCORE V2 BASELINES
═══════════════════════════════════════════════════════════════════
Phase 157A (v2 scoring):   45.5/100  ← Comparable baseline
Phase 161A (v2 corrected): 38.9/100  ← Measurement change effects visible
Post-Phase-164 target:      58/100   ← Minimum acceptable after Bug A+B fixes
Public beta target:         68/100   ← Symbol Evidence Phase 1 required
General availability:       78/100   ← Symbol Evidence Phase 2+3 required
```
