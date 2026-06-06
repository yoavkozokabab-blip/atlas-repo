# Phase 164-DIAG-CODEX - Trust Failure Reproduction Audit

Date: 2026-06-05

Scope: diagnostic reproduction only. No Atlas production code and no benchmark code were modified. A raw diagnostic JSON artifact was written under `reports/` for traceability.

## Method

- Loaded `reports/phase161b_failure_forensics.md` and the Phase 161A raw measurement artifact from `%TEMP%/phase161a_truth_audit_raw.json`.
- Reproduced cases through `jarvis_desktop.server.dispatch`, the same route table used by the HTTP API.
- Routes exercised: `/api/planning/change`, `/api/planning/investigate`, `/api/planning/impact`.
- Repos scanned for this focused reproduction: `django, airflow, vscode, typeorm, kubernetes`.
- Full raw response JSON: `reports/phase164_diag_codex_reproduction_raw.json`.

## Selection

| Selection bucket | Count |
| --- | --- |
| integration_requested | 10 |
| integration_selected | 10 |
| untested_selected | 9 |
| measurement_selected | 5 |
| audit_selected | 11 |
| total_selected | 35 |

## Repository Scan Context

| Repo | Scan seconds | Graph health | Modules | Edges | Unresolved imports | Unresolved ratio |
| --- | --- | --- | --- | --- | --- | --- |
| django | 22.343 | watch | 929 | 2915 | 1377 | 0.3208 |
| airflow | 111.287 | partial | 4332 | 835 | 31640 | 0.9743 |
| vscode | 36.065 | partial | 7563 | 13228 | 67338 | 0.8358 |
| typeorm | 3.451 | watch | 569 | 2735 | 288 | 0.0953 |
| kubernetes | 7.089 | unsupported | 3 | 0 | 14 | 1.0 |

## Diagnostic Classification Summary

| Diagnostic class | Count |
| --- | --- |
| CONFIRMED_ENGINE_BUG | 17 |
| CONFIRMED_AUDIT_BUG | 4 |
| INCONCLUSIVE | 3 |
| CONFIRMED_EXPECTED_REFUSAL | 11 |

## Phase 161B Bucket Coverage

| Phase 161B bucket | Reproduced cases |
| --- | --- |
| D. Integration bug | 10 |
| C. Untested route | 9 |
| B. Measurement change | 5 |
| E. Audit bug | 11 |

## Minimal Reproduction Table

| 161B # | Repo | Workflow | 161B bucket | Diagnostic class | Route | Payload | ok | status | confidence | evidence_count | mock | graph_health | unknown_mode | Rendered/user-facing summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | django | build | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/change | {"request": "add async view tracing"} | True | None | medium | 154 | None | watch | False | CHANGE PLAN =========== Goal: add async view tracing Detected concept: EMA EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Concept c... |
| 17 | django | investigation | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is async view tracing broken"} | True | None | high | 132 | None | watch | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is async view tracing broken". Likely area: django/db/backends/base/schema.py. A2... |
| 18 | django | build | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/change | {"request": "add migration safety checker"} | True | None | medium | 162 | None | watch | False | CHANGE PLAN =========== Goal: add migration safety checker Detected concept: EMA EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Con... |
| 21 | django | investigation | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is session cleanup policy broken"} | True | None | high | 126 | None | watch | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is session cleanup policy broken". Likely area: django/contrib/auth/__init__.py. ... |
| 19 | django | investigation | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is migration safety checker broken"} | True | None | high | 134 | None | watch | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is migration safety checker broken". Likely area: django/db/migrations/loader.py.... |
| 20 | django | investigation | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is template rendering metrics broken"} | True | None | high | 152 | None | watch | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is template rendering metrics broken". Pattern recognized: dashboard mismatch. Li... |
| 22 | django | impact | B. Measurement change | CONFIRMED_AUDIT_BUG | /api/planning/impact | {"target": "django/core/handlers/base.py"} | True | resolved | low | 463 | None | watch | False | {"affected_file_count": 24, "affected_files": ["django/contrib/auth/decorators.py", "django/contrib/auth/middleware.py", "django/dispatch/dispatcher.py", "dj... |
| 23 | django | impact | B. Measurement change | CONFIRMED_AUDIT_BUG | /api/planning/impact | {"target": "django/contrib/admin/options.py"} | True | resolved | high | 387 | None | watch | False | {"affected_file_count": 24, "affected_files": ["django/contrib/admin/__init__.py", "django/contrib/admin/decorators.py", "django/contrib/admin/filters.py", "... |
| 24 | django | impact | B. Measurement change | CONFIRMED_AUDIT_BUG | /api/planning/impact | {"target": "django/conf/__init__.py"} | True | resolved | high | 2739 | None | watch | False | {"affected_file_count": 24, "affected_files": ["django/conf/__init__.py", "django/conf/urls/i18n.py", "django/conf/urls/static.py", "django/contrib/admin/che... |
| 33 | airflow | build | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/change | {"request": "add connection secret rotation audit"} | True | None | medium | 116 | None | partial | False | CHANGE PLAN =========== Goal: add connection secret rotation audit Detected concept: EMA EMA Domain: Trading Systems / indicator Knowledge quality: Source-ba... |
| 34 | airflow | investigation | D. Integration bug | INCONCLUSIVE | /api/planning/investigate | {"symptom": "why is webserver RBAC audit logging broken"} | True | None | medium | 113 | None | partial | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is webserver RBAC audit logging broken". Likely area: airflow-core/src/airflow/ut... |
| 35 | airflow | build | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/change | {"request": "add session leak diagnostics"} | True | None | medium | 116 | None | partial | False | CHANGE PLAN =========== Goal: add session leak diagnostics Detected concept: EMA EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Con... |
| 36 | airflow | investigation | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is session leak diagnostics broken"} | True | None | medium | 115 | None | partial | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is session leak diagnostics broken". Pattern recognized: memory growth. Likely ar... |
| 37 | airflow | build | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/change | {"request": "add DAG processor memory metrics"} | True | None | medium | 115 | None | partial | False | CHANGE PLAN =========== Goal: add DAG processor memory metrics Detected concept: EMA EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed... |
| 38 | airflow | investigation | D. Integration bug | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is DAG processor memory metrics broken"} | True | None | medium | 114 | None | partial | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is DAG processor memory metrics broken". Pattern recognized: memory growth. Likel... |
| 41 | airflow | impact | B. Measurement change | CONFIRMED_AUDIT_BUG | /api/planning/impact | {"target": "airflow-core/src/airflow/www/app.py"} | True | resolved | low | 1836 | None | partial | False | {"affected_file_count": 24, "affected_files": ["airflow-core/src/airflow/api_fastapi/execution_api/app.py", "dev/breeze/src/airflow_breeze/utils/functools_ca... |
| 31 | vscode | investigation | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is extension activation diagnostics broken"} | True | None | medium | 103 | None | partial | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is extension activation diagnostics broken". Likely area: extensions/copilot/src/... |
| 32 | vscode | investigation | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is extension host crash reporting broken"} | True | None | medium | 105 | None | partial | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is extension host crash reporting broken". Likely area: extensions/copilot/src/ex... |
| 49 | typeorm | build | C. Untested route | INCONCLUSIVE | /api/planning/change | {"request": "add query builder cache metrics"} | True | None | medium-high | 119 | None | watch | False | CHANGE PLAN =========== Goal: add query builder cache metrics Detected concept: Redis Redis Domain: Databases / cache Knowledge quality: Source-backed Concep... |
| 57 | typeorm | investigation | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is datasource initialization metrics broken"} | True | None | medium-high | 115 | None | watch | False | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is datasource initialization metrics broken". Pattern recognized: dashboard misma... |
| 58 | kubernetes | build | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/change | {"request": "add admission webhook timeout metrics"} | True | None | low | 66 | None | unsupported | False | CHANGE PLAN =========== Goal: add admission webhook timeout metrics Detected concept: Webhook Receiver Webhook Receiver Domain: Backend Engineering / integra... |
| 59 | kubernetes | investigation | C. Untested route | INCONCLUSIVE | /api/planning/investigate | {"symptom": "why is admission webhook timeout metrics broken"} | True | None | low | 63 | None | unsupported | True | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is admission webhook timeout metrics broken". Pattern recognized: dashboard misma... |
| 60 | kubernetes | investigation | C. Untested route | CONFIRMED_ENGINE_BUG | /api/planning/investigate | {"symptom": "why is scheduler plugin latency metrics broken"} | True | None | low | 64 | None | unsupported | True | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why is scheduler plugin latency metrics broken". Pattern recognized: dashboard mismat... |
| 71 | kubernetes | impact | B. Measurement change | CONFIRMED_ENGINE_BUG | /api/planning/impact | {"target": "staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/vali... | True | resolved | low | 351 | None | unsupported | False | {"affected_file_count": 2, "affected_files": ["hack/boilerplate/boilerplate.py", "ArgumentParser", "abspath", "add", "add_argument", "any", "append", "check_... |
| 66 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/kubelet/kubelet.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/kubelet/kubelet.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or check that the repository is f... |
| 67 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/scheduler/scheduler.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/scheduler/scheduler.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or check that the repository ... |
| 68 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/controller/deployment/deployment_controller.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/controller/deployment/deployment_controller.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or ch... |
| 69 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/d... | False | target_not_resolved | low | 6 | None | unsupported | True | Target `staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go` was not found in the production graph. Choose an exact file path ... |
| 70 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "staging/src/k8s.io/apiserver/pkg/audit/request.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `staging/src/k8s.io/apiserver/pkg/audit/request.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or che... |
| 72 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/proxy/iptables/proxier.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/proxy/iptables/proxier.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or check that the reposito... |
| 73 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/controller/nodeipam/node_ipam_controller.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/controller/nodeipam/node_ipam_controller.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or check... |
| 74 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/volume/util/operationexecutor/operation_executor.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/volume/util/operationexecutor/operation_executor.go` was not found in the production graph. Choose an exact file path visible in Repository Map, ... |
| 75 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "cmd/kube-apiserver/app/server.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `cmd/kube-apiserver/app/server.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or check that the repos... |
| 76 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "staging/src/k8s.io/apiserver/pkg/audit/policy/checker.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `staging/src/k8s.io/apiserver/pkg/audit/policy/checker.go` was not found in the production graph. Choose an exact file path visible in Repository Map,... |
| 77 | kubernetes | impact | E. Audit bug | CONFIRMED_EXPECTED_REFUSAL | /api/planning/impact | {"target": "pkg/controlplane/apiserver/server.go"} | False | target_not_resolved | low | 6 | None | unsupported | True | Target `pkg/controlplane/apiserver/server.go` was not found in the production graph. Choose an exact file path visible in Repository Map, or check that the r... |

## Findings

- **Concept leakage is still reproducible in current live routes.** Several Build/Investigation routes still return EMA / Trading Systems for non-trading repositories.
- **Unsupported-language impact refusals are correctly honest.** Kubernetes Impact cases return `ok=false` / `target_not_resolved`; these are expected refusals, not fake-success impact results.
- **Unsupported-language Build/Investigation is still too eager.** Kubernetes Build/Investigation routes can return `ok=true` plans against an unsupported graph rather than an explicit refusal.
- **Some Phase 161B measurement-change rows are genuine measurement mismatch.** Resolved Impact responses may be thin, but they are not the same defect as target-not-found fake success.
- **No stale route was confirmed in this selected set.** The route table exercised the current `/api/planning/*` handlers; failures reproduced through the active handlers rather than a separate legacy endpoint.

## Final Verdict

The true dominant failure class is confirmed engine/integration behavior: current planning routes still emit unsafe or overconfident outputs on several reproduced cases.

Dominant reproduced class: **CONFIRMED_ENGINE_BUG**.
