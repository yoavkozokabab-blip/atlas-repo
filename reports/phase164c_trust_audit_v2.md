# Phase 164C Trust Audit v2

Date: 2026-06-05
HEAD: `17f0887f1`
Scope: measurement only. No Atlas production code, benchmark code, detector logic, route logic, UI code, or intelligence behavior was modified.
Method: canonical Trust Audit v2 from `reports/phase164b_audit_normalization.md`: 150 fixed prompts, 8 fixed repositories, v2 REFUSAL handling, and high-confidence MISLEADING penalty.

## Final Verdict

FAIL

Trust Score v2: **89.3/100** across 150 samples.

## Required Phase 164 Checks

| Check | Observed | Result |
| --- | --- | --- |
| Trust Score v2 >= 58 | 89.3/100 | PASS |
| EMA leakage rate | 0/100 = 0.0% | PASS |
| Kubernetes Impact refusal correctness | 5/6 | FAIL |
| High-confidence unsafe rate < 2% | 0/150 = 0.0% | PASS |
| Fake-success rate | 0/150 = 0.0% | PASS |

## Workflow Breakdown

| Workflow | N | Trust Score | CORRECT | MOSTLY_CORRECT | PARTIAL | REFUSAL | MISLEADING | WRONG |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Build Plan | 50 | 88.7 | 34 | 9 | 7 | 0 | 0 | 0 |
| Investigation | 50 | 89.1 | 35 | 8 | 7 | 0 | 0 | 0 |
| Impact | 50 | 90.0 | 39 | 5 | 0 | 5 | 0 | 1 |

## Classification Counts

| Classification | Count |
| --- | --- |
| CORRECT | 108 |
| MOSTLY_CORRECT | 22 |
| PARTIAL | 14 |
| REFUSAL | 5 |
| MISLEADING | 0 |
| WRONG | 1 |

## Repository Breakdown

| Repo | N | Trust Score | CORRECT | MOSTLY | PARTIAL | REFUSAL | MISLEADING | WRONG | Graph health |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| home_assistant | 21 | 91.7 | 14 | 6 | 1 | 0 | 0 | 0 | partial |
| django | 21 | 92.6 | 15 | 5 | 1 | 0 | 0 | 0 | watch |
| fastapi | 18 | 98.9 | 17 | 1 | 0 | 0 | 0 | 0 | watch |
| vscode | 18 | 97.8 | 16 | 2 | 0 | 0 | 0 | 0 | partial |
| airflow | 18 | 95.6 | 14 | 4 | 0 | 0 | 0 | 0 | partial |
| celery | 18 | 98.9 | 17 | 1 | 0 | 0 | 0 | 0 | healthy |
| typeorm | 18 | 96.7 | 15 | 3 | 0 | 0 | 0 | 0 | watch |
| kubernetes | 18 | 41.1 | 0 | 0 | 12 | 5 | 0 | 1 | unsupported |

## Scan State

| Repo | ok | Scan sec | Files | Modules | Edges | Subsystems | Unresolved imports | Graph health | Degraded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| home_assistant | True | 329.85 | 25893 | 9709 | 36013 | 1512 | 59473 | partial | True |
| django | True | 18.12 | 6870 | 929 | 2915 | 9 | 1377 | watch | False |
| fastapi | True | 2.54 | 2753 | 73 | 159 | 7 | 560 | watch | False |
| vscode | True | 28.03 | 14892 | 7563 | 13228 | 226 | 67338 | partial | True |
| airflow | True | 89.5 | 12341 | 4332 | 835 | 33 | 31640 | partial | True |
| celery | True | 5.65 | 810 | 215 | 575 | 11 | 1035 | healthy | False |
| typeorm | True | 2.54 | 3738 | 569 | 2735 | 323 | 288 | watch | False |
| kubernetes | True | 5.43 | 24860 | 3 | None | 430 | 14 | unsupported | True |

## Top 20 Remaining Failures

| ID | Repo | Workflow | Class | Score | Confidence | Matched anchors | Tags | Prompt | Evidence excerpt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P-KU-06 | kubernetes | Impact | WRONG | 0.0 | low |  | kubernetes_impact_not_refused | staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go | {"affected_file_count": 2, "affected_files": ["hack/boilerplate/boilerplate.py", "argumentparser", "abspath", "add", "add_argument", "any", "append", "check_underscore_in_flags", "close"], "affected_node_ids": [], "affected_subsystems": ["hack"], "architectural_blast_radius": 9,  |
| I-HA-06 | home_assistant | Investigation | PARTIAL | 0.45 | medium | helpers |  | why state changes are not observed by listeners | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why state changes are not observed by listeners". Likely area: homeassistant/components/automation/reproduce_state.py. A3. Repository evidence Status: Partially Implemented Evidence score: 55.0/100 Found: - E |
| B-DJ-05 | django | Build Plan | PARTIAL | 0.45 | medium | migrations |  | add migration safety checker | CHANGE PLAN =========== Goal: add migration safety checker Files to inspect first: - django/core/management/commands/squashmigrations.py - django/core/management/commands/optimizemigration.py - django/core/management/commands/makemigrations.py - django/core/management/base.py - d |
| B-KU-01 | kubernetes | Build Plan | PARTIAL | 0.45 | low | admission, webhook | scope_pollution, noise_root, unsupported_language_partial | add admission webhook timeout metrics | CHANGE PLAN =========== Goal: add admission webhook timeout metrics Detected concept: Webhook Receiver - Webhook Receiver Domain: Backend Engineering / integration Knowledge quality: Source-backed Concept confidence: medium - Repo mapping: medium Concept understanding: HTTP endpo |
| B-KU-02 | kubernetes | Build Plan | PARTIAL | 0.45 | low | audit, request | noise_root, unsupported_language_partial | add API server audit logging | CHANGE PLAN =========== Goal: add API server audit logging Detected concept: Structured logging - Logging / audit trail Domain: Infrastructure / DevOps / observability Knowledge quality: Curated Concept confidence: medium - Repo mapping: medium Concept understanding: Consistent s |
| B-KU-03 | kubernetes | Build Plan | PARTIAL | 0.45 | low | scheduler, plugin | noise_root, unsupported_language_partial | add scheduler plugin latency metrics | CHANGE PLAN =========== Goal: add scheduler plugin latency metrics Files to inspect first: - hack/boilerplate/boilerplate.py - hack/verify-flags-underscore.py - staging/src/k8s.io/kubectl/pkg/util/i18n/translations/extract.py Files likely to change: - hack/boilerplate/boilerplate |
| B-KU-04 | kubernetes | Build Plan | PARTIAL | 0.45 | low | controller, retry | noise_root, unsupported_language_partial | add controller retry backoff telemetry | CHANGE PLAN =========== Goal: add controller retry backoff telemetry Detected concept: Retry with Backoff - Retry with Backoff Domain: Distributed Systems / resilience Knowledge quality: Source-backed Concept confidence: high - Repo mapping: medium Concept understanding: Retry tr |
| B-KU-05 | kubernetes | Build Plan | PARTIAL | 0.45 | low | kubelet, pod | noise_root, unsupported_language_partial | add kubelet pod lifecycle tracing | CHANGE PLAN =========== Goal: add kubelet pod lifecycle tracing Files to inspect first: - hack/boilerplate/boilerplate.py - hack/verify-flags-underscore.py - staging/src/k8s.io/kubectl/pkg/util/i18n/translations/extract.py Files likely to change: - hack/boilerplate/boilerplate.py |
| B-KU-06 | kubernetes | Build Plan | PARTIAL | 0.45 | low | crd, validation | noise_root, unsupported_language_partial | add CRD schema validation warnings | CHANGE PLAN =========== Goal: add CRD schema validation warnings Files to inspect first: - hack/boilerplate/boilerplate.py - hack/verify-flags-underscore.py - staging/src/k8s.io/kubectl/pkg/util/i18n/translations/extract.py Files likely to change: - hack/boilerplate/boilerplate.p |
| I-KU-01 | kubernetes | Investigation | PARTIAL | 0.45 | low | admission, webhook | scope_pollution, noise_root, unsupported_language_partial | why admission webhook latency spikes | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why admission webhook latency spikes". Likely area: hack/boilerplate/boilerplate.py. A2. Domain knowledge Concept: Webhook Receiver - Webhook Receiver Domain: Backend Engineering Knowledge quality: Source-bac |
| I-KU-02 | kubernetes | Investigation | PARTIAL | 0.45 | low | audit, request | noise_root, unsupported_language_partial | why audit events are missing for requests | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why audit events are missing for requests". Likely area: hack/boilerplate/boilerplate.py. A3. Repository evidence Status: Not Found Evidence score: 0.0/100 Found: Missing: - Side-by-side slippage/fill compari |
| I-KU-03 | kubernetes | Investigation | PARTIAL | 0.45 | low | scheduler, plugin | noise_root, unsupported_language_partial | why scheduler plugin latency is high | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why scheduler plugin latency is high". Likely area: hack/boilerplate/boilerplate.py. A3. Repository evidence Status: Not Found Evidence score: 0.0/100 Found: Missing: - Side-by-side slippage/fill comparison B |
| I-KU-04 | kubernetes | Investigation | PARTIAL | 0.45 | low | deployment, controller | scope_pollution, noise_root, unsupported_language_partial | why deployment controller retries forever | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why deployment controller retries forever". Likely area: staging/src/k8s.io/kubectl/pkg/util/i18n/translations/extract.py. A2. Domain knowledge Concept: Kubernetes - Kubernetes Domain: Cloud Knowledge quality |
| I-KU-05 | kubernetes | Investigation | PARTIAL | 0.45 | low | kubelet, pod | noise_root, unsupported_language_partial | why kubelet restarts pods unexpectedly | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why kubelet restarts pods unexpectedly". Likely area: hack/boilerplate/boilerplate.py. A3. Repository evidence Status: Not Found Evidence score: 0.0/100 Found: Missing: - Side-by-side slippage/fill comparison |
| I-KU-06 | kubernetes | Investigation | PARTIAL | 0.45 | low | crd, validation | noise_root, unsupported_language_partial | why CRD validation rejects valid schema | INVESTIGATION REPORT ==================== A. Symptom summary Reported: "why CRD validation rejects valid schema". Likely area: hack/boilerplate/boilerplate.py. A3. Repository evidence Status: Not Found Evidence score: 0.0/100 Found: Missing: - Side-by-side slippage/fill compariso |

## EMA Leakage Samples

None observed.

## Kubernetes Impact Refusals

| ID | Target | ok | status | Class | Score | Tags |
| --- | --- | --- | --- | --- | --- | --- |
| P-KU-01 | pkg/kubelet/kubelet.go | False | target_not_resolved | REFUSAL | 0.4 | expected_refusal |
| P-KU-02 | pkg/scheduler/scheduler.go | False | target_not_resolved | REFUSAL | 0.4 | expected_refusal |
| P-KU-03 | pkg/controller/deployment/deployment_controller.go | False | target_not_resolved | REFUSAL | 0.4 | expected_refusal |
| P-KU-04 | staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go | False | target_not_resolved | REFUSAL | 0.4 | expected_refusal |
| P-KU-05 | staging/src/k8s.io/apiserver/pkg/audit/request.go | False | target_not_resolved | REFUSAL | 0.4 | expected_refusal |
| P-KU-06 | staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go | True | resolved | WRONG | 0.0 | kubernetes_impact_not_refused |

## High-Confidence Unsafe Outputs

None observed.

## Fake Success Outputs

None observed.

## Notes

- The run used a dedicated runtime data directory under `reports/phase164c_runtime/` to avoid touching normal Atlas desktop state.
- The runner parsed prompt IDs and anchor expectations directly from `reports/phase164b_audit_normalization.md`.
- REFUSAL is scored as 0.40 when it is honest and expected, especially for unsupported Kubernetes Impact targets.
- MISLEADING with `high` or `medium-high` confidence is scored as 0.00 per v2 confidence calibration.
- Total wall time: 512.0 seconds.
