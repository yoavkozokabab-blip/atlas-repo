# Phase 157A - Hallucination Taxonomy

Atlas rarely produced completely arbitrary prose, but it repeatedly produced outputs that sounded more grounded than they were. The major hallucination mode is **false specificity**: naming a plausible-looking concept, module, or root cause without enough supporting graph evidence.

## Failure Category Counts

| Category | Count | Primary risk |
|---|---:|---|
| thin_grounding | 118 | Output gives directional context but not enough evidence for trust. |
| repo_grounded | 12 | No hallucination flag in this audit. |
| irrelevant_target_pollution | 7 | Wrong concept/config/docs/fallback details contaminate the result. |
| nonsensical_root_cause | 5 | Investigation root cause names syntax/import tokens or weak file anchors. |
| target_resolution_failure | 5 | Existing file cannot be resolved and a mock target-not-found response is returned. |
| repo_grounded_with_limits | 3 | Mostly useful, but incomplete evidence or missing affected files. |

## Flag Counts

| Flag | Count |
|---|---:|
| unknown | 107 |
| typing. | 23 |
| fallback | 23 |
| package.json | 13 |
| random | 12 |
| __future__.annotations | 11 |
| eslint | 7 |
| dataclasses | 6 |
| target not found | 5 |
| no module node matched | 5 |
| .prettierrc | 2 |
| prettier | 2 |
| pathlib | 1 |

## Top Misleading Patterns

| Pattern | Evidence | Affected samples | Trust impact |
|---|---|---:|---|
| Curated concept leakage | Build Plans for event bus, recorder retention, migration safety, and relation telemetry selected EMA / Trading Systems. | 4 | Makes a normal engineering plan look like unrelated financial-analysis output. |
| Mock target-not-found success | Kubernetes Impact returned `ok=true`, `mock=true`, and target-not-found for existing files. | 5 | Users can mistake a failed graph lookup for a valid result unless they notice the mock field. |
| Thin grounding at scale | 118/150 samples were PARTIALLY_CORRECT with thin grounding. | 118 | Outputs often tell users a plausible direction but not enough evidence to act. |
| Weak investigation root causes | Investigations named low-value anchors such as `__future__.annotations`, `typing`, `dataclasses`, or import-like terms. | 5+ | Root-cause trust drops even when the likely subsystem is plausible. |
| Unsupported language health mismatch | Kubernetes reported only 3 modules from 24,860 files while graph health was healthy. | 6 Kubernetes Impact/graph-dependent samples | Hides language-support limitations and causes downstream wrongness. |

## Worst Examples

| Repo | Workflow | Classification | Prompt / target | Evidence preview |
|---|---|---|---|---|
| home_assistant | build | MISLEADING | add event bus tracing | CHANGE PLAN =========== Goal: add event bus tracing Detected concept: EMA - EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Concept confidence: medium - Re |
| home_assistant | build | MISLEADING | add recorder retention policy | CHANGE PLAN =========== Goal: add recorder retention policy Detected concept: EMA - EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Concept confidence: med |
| home_assistant | investigation | MISLEADING | why are duplicate events being fired | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why are duplicate events being fired". Pattern recognized: duplicate events. Likely area: homeassistant/help |
| home_assistant | investigation | MISLEADING | why do websocket clients disconnect after auth refresh | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why do websocket clients disconnect after auth refresh". Likely area: homeassistant/auth/auth_store.py. A2. |
| home_assistant | investigation | MISLEADING | why recorder writes stop after database reconnect | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why recorder writes stop after database reconnect". Likely area: homeassistant/components/recorder/models/da |
| home_assistant | investigation | MISLEADING | why state changes are not observed by listeners | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why state changes are not observed by listeners". Likely area: homeassistant/helpers/event.py. A3. Repositor |
| home_assistant | impact | MISLEADING | homeassistant/core.py | {"ok": true, "target": "homeassistant/core.py", "target_node_id": "module:homeassistant/core.py", "semantic_concept": "", "semantic_label": "", "resolved_modules": [], "resolved_sy |
| django | build | MISLEADING | add migration safety checker | CHANGE PLAN =========== Goal: add migration safety checker Detected concept: EMA - EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Concept confidence: medi |
| django | impact | MISLEADING | django/core/handlers/base.py | {"ok": true, "target": "django/core/handlers/base.py", "target_node_id": "module:django/core/handlers/base.py", "semantic_concept": "", "semantic_label": "", "resolved_modules": [] |
| airflow | investigation | MISLEADING | why DAG parsing is slow after deploy | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why DAG parsing is slow after deploy". Likely area: airflow-core/src/airflow/api_fastapi/core_api/routes/pub |
| airflow | investigation | MISLEADING | why task retries ignore backoff | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why task retries ignore backoff". Likely area: airflow-core/src/airflow/ui/src/components/Graph/TaskNode.tsx |
| typeorm | build | MISLEADING | add relation loading telemetry | CHANGE PLAN =========== Goal: add relation loading telemetry Detected concept: EMA - EMA Domain: Trading Systems / indicator Knowledge quality: Source-backed Concept confidence: me |
| kubernetes | impact | WRONG | pkg/kubelet/kubelet.go | {"ok": true, "mock": true, "target": "pkg/kubelet/kubelet.go", "reason": "Target not found in the production graph.", "direct_impact": [], "indirect_impact": [], "affected_files": |
| kubernetes | impact | WRONG | pkg/scheduler/scheduler.go | {"ok": true, "mock": true, "target": "pkg/scheduler/scheduler.go", "reason": "Target not found in the production graph.", "direct_impact": [], "indirect_impact": [], "affected_file |
| kubernetes | impact | WRONG | pkg/controller/deployment/deployment_controller.go | {"ok": true, "mock": true, "target": "pkg/controller/deployment/deployment_controller.go", "reason": "Target not found in the production graph.", "direct_impact": [], "indirect_imp |
| kubernetes | impact | WRONG | staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go | {"ok": true, "mock": true, "target": "staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go", "reason": "Target not found in the production graph.", "d |
| kubernetes | impact | WRONG | staging/src/k8s.io/apiserver/pkg/audit/request.go | {"ok": true, "mock": true, "target": "staging/src/k8s.io/apiserver/pkg/audit/request.go", "reason": "Target not found in the production graph.", "direct_impact": [], "indirect_impa |

## Top Confidence Mismatches

Confidence mismatch here means the output had a medium/high confidence signal, `ok=true`, or a strong risk label while the reviewer classification was MISLEADING or WRONG.

| Repo | Workflow | Classification | Prompt / target | Why it mismatches |
|---|---|---|---|---|
| home_assistant | build | MISLEADING | add event bus tracing | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| home_assistant | build | MISLEADING | add recorder retention policy | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| home_assistant | investigation | MISLEADING | why are duplicate events being fired | Investigation named low-value syntax/import tokens as likely root cause. |
| home_assistant | investigation | MISLEADING | why do websocket clients disconnect after auth refresh | Investigation named low-value syntax/import tokens as likely root cause. |
| home_assistant | investigation | MISLEADING | why recorder writes stop after database reconnect | Investigation named low-value syntax/import tokens as likely root cause. |
| home_assistant | investigation | MISLEADING | why state changes are not observed by listeners | Investigation named low-value syntax/import tokens as likely root cause. |
| django | build | MISLEADING | add migration safety checker | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| airflow | investigation | MISLEADING | why DAG parsing is slow after deploy | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
| airflow | investigation | MISLEADING | why task retries ignore backoff | Investigation named low-value syntax/import tokens as likely root cause. |
| typeorm | build | MISLEADING | add relation loading telemetry | Some expected evidence appeared, but irrelevant/fallback/config pollution makes the result unsafe. |
