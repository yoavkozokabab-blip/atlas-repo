# Phase 161A - Failure Taxonomy

Date: 2026-06-05

## Requested Failure Categories

| Failure category | Count | Affected repositories | Workflow counts |
| --- | --- | --- | --- |
| concept_leakage | 244 | airflow, celery, django, fastapi, home_assistant, kubernetes, typeorm, vscode | build:70, investigation:74, impact:100 |
| wrong_target | 11 | kubernetes | impact:11 |
| fake_success | 77 | airflow, celery, django, fastapi, home_assistant, kubernetes, typeorm, vscode | build:20, investigation:26, impact:31 |
| false_root_cause | 29 | airflow, django, fastapi, home_assistant | investigation:29 |
| confidence_mismatch | 53 | airflow, celery, django, fastapi, home_assistant, typeorm, vscode | build:17, investigation:21, impact:15 |
| graph_health_mismatch | 36 | kubernetes | build:12, investigation:12, impact:12 |
| unsupported_language | 12 | kubernetes | impact:12 |
| scope_pollution | 204 | airflow, celery, django, fastapi, home_assistant, kubernetes, typeorm, vscode | build:77, investigation:76, impact:51 |
| weak_evidence | 76 | airflow, celery, django, fastapi, home_assistant, kubernetes, typeorm, vscode | build:23, investigation:28, impact:25 |
| generic_fallback | 179 | airflow, celery, django, fastapi, home_assistant, kubernetes, typeorm, vscode | investigation:83, build:61, impact:35 |

## Representative Examples

| Failure category | Repo | Workflow | Class | Confidence | Prompt | Matched evidence | Reviewer note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| concept_leakage | home_assistant | build | PARTIAL | high | add websocket audit logging | websocket_api, auth, http | Some expected anchors matched, but grounding was thin or noisy. |
| wrong_target | kubernetes | impact | WRONG | low | impact of changing pkg/kubelet/kubelet.go | kubelet | API returned ok=false or failed. |
| fake_success | home_assistant | build | MISLEADING | medium | add event bus tracing | helpers/event | Unrelated concept leakage with limited expected evidence. |
| false_root_cause | home_assistant | investigation | PARTIAL | medium | why is websocket audit logging broken | websocket_api, auth, http | Some expected anchors matched, but grounding was thin or noisy. |
| confidence_mismatch | home_assistant | build | MISLEADING | medium | add event bus tracing | helpers/event | Unrelated concept leakage with limited expected evidence. |
| graph_health_mismatch | kubernetes | build | MISLEADING | low | add admission webhook timeout metrics | admission, webhook | Docs/scripts/config pollution with limited expected evidence. |
| unsupported_language | kubernetes | impact | WRONG | low | impact of changing pkg/kubelet/kubelet.go | kubelet | API returned ok=false or failed. |
| scope_pollution | home_assistant | build | MISLEADING | medium | add event bus tracing | helpers/event | Unrelated concept leakage with limited expected evidence. |
| weak_evidence | home_assistant | build | MISLEADING | medium | add event bus tracing | helpers/event | Unrelated concept leakage with limited expected evidence. |
| generic_fallback | home_assistant | investigation | PARTIAL | medium | why is websocket audit logging broken | websocket_api, auth, http | Some expected anchors matched, but grounding was thin or noisy. |

## Interpretation

- **Concept leakage** is the dominant broad failure tag. It means Atlas often finds a plausible architecture phrase, but not enough task-specific causality.
- **Scope pollution** remains common, especially when subsystem or file selection includes broadly related but weakly causal modules.
- **Generic fallback** appears in 179 samples and is tightly coupled to unknown mode usage.
- **Weak evidence** appears in 76 samples; these outputs name some relevant files but do not provide enough source-backed proof.
- **Fake success** appears in 77 samples: every MISLEADING or WRONG output still returned `ok=true`.
- **Wrong target** is concentrated in Kubernetes Impact. Atlas correctly marks the graph unsupported, but the Impact workflow still emits failed target-resolution results as successful responses.

## Failure Categories By Severity

- Critical: fake_success, wrong_target, confidence_mismatch, graph_health_mismatch.
- High: false_root_cause, weak_evidence, unsupported_language.
- Medium: concept_leakage, scope_pollution, generic_fallback.

## Root-Cause Assessment

The highest-risk issue is not one specific detector. It is success semantics: weak, generic, unsupported, or target-not-found outputs still look operationally successful. A beta user would not know when to stop trusting the answer.
