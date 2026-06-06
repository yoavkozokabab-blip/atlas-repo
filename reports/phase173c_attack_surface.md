# Phase 173C Atlas Red Team Attack Surface

Date: 2026-06-06
Workspace: `C:\J.A.R.V.I.S\local_jarvis`
Current HEAD observed: `ec41740ee`

This audit was run against the current dirty working tree. It is intentionally adversarial and report-only. No production code was changed.

## Trust Boundaries

Atlas currently has several trust boundaries where stale or untrusted state can become user-facing evidence:

| Surface | Entrypoints | Stored state | Primary trust risk |
| --- | --- | --- | --- |
| Repository selection | `select_repository`, `scan_repository` | `_STATE["path"]`, `_STATE["scan"]`, `_STATE["graph"]`, `_STATE["index"]` | Wrong repository answers if path and scan state diverge |
| Scan cache | `_scan_signature`, `_STATE["scan_cache"]` | Full scan, graph, index, risks, evidence store | Stale graph after source edits |
| Repository memory | `repository_memory.load`, `update_after_scan`, `session_export_packet` | `{data_dir}/memory/{repo_id}.json`, `_STATE["repository_memory"]` | Poisoned or stale deltas copied into exports |
| Workflow APIs | `plan_change`, `investigate_symptom`, `change_impact_simulation`, `context_export` | Global `_STATE` plus planner output | False success, wrong files, unsupported-language confidence |
| Exports | `atlas_export.attach_workflow_exports`, `context_export`, `session_export_packet` | Full/minimal/memory export text | Corrupted context pasted into LLMs |
| Graph building | dependency graph, module map, graph health | `_STATE["graph"]`, scan summary fields | Partial graph represented as healthy |
| Symbol evidence | impact and planning target selection | evidence store, graph nodes, semantic routing | Target not resolved, or false target selected |
| Diagnostics | `install_support.export_support_bundle` | diagnostics JSON, scan metadata, logs | Support bundles leak paths/log data or hide failures |
| Installer/startup | launchers, packaged runtime, support page | logs and startup checks | User sees failure without a safe recovery path |
| Memory persistence | `repository_memory.persist` | atomic temp-to-final JSON writes | Silent persistence failure or orphan temp files |

## Code-Level Attack Map

| ID | Code path | Observation | Failure class |
| --- | --- | --- | --- |
| AS-01 | `jarvis_desktop/api.py:466-486` | `_scan_signature` hashes repo path, scope, size, and integer mtime for only the first 2500 files. It does not hash file contents. | Stale cache, invalidation bug |
| AS-02 | `jarvis_desktop/api.py:884-887` | `scan_repository` trusts the signature to decide cache hits. Cached scan, graph, index, risks, and evidence store are restored together. | Cache poisoning / stale graph |
| AS-03 | `jarvis_desktop/repository_memory.py:186-197` | `load()` accepts any JSON with the expected version. It does not verify repo_id, repo_path, scan signature, schema bounds, or integrity. | Memory poisoning |
| AS-04 | `jarvis_desktop/repository_memory.py:166-180` | `persist()` catches `OSError`, attempts cleanup, and returns an empty path. Callers do not surface this as a degraded state. | Silent memory persistence failure |
| AS-05 | `jarvis_desktop/repository_memory.py:530-557` | `update_after_scan()` computes deltas against previous memory, persists, and still caches memory in `_STATE` even if persistence fails. | Memory drift |
| AS-06 | `jarvis_desktop/api.py:2593-2618` | Build Plan now refuses if no scan or path mismatch, but still accepts poor graph health once a scan exists. | False confidence on partial graph |
| AS-07 | `jarvis_desktop/api.py:2621-2640` | Investigation uses planning context and can return `ok=true` on unsupported/near-empty graph scans. | Fake success / weak evidence |
| AS-08 | `jarvis_desktop/api.py:2643-2680` | Impact has more honest failure behavior for unresolved targets, but depends on graph and semantic resolution quality. | Target resolution failure |
| AS-09 | `jarvis_desktop/atlas_export.py:245-339` | Memory export can carry delta text from repository memory into workflow exports. Poisoned memory therefore contaminates LLM context. | Export corruption |
| AS-10 | `jarvis_desktop/install_support.py:395-416` | Support bundle states no source code is included and includes diagnostics/logs. A probe found no source leak, but path/log redaction remains a privacy boundary. | Diagnostics leakage risk |

## Red-Team Findings

### AS-F1: Stale Scan Cache After Source Edit

Reproduction:

1. Scan a repository containing `main.py -> dep_b.py`.
2. Change `main.py` to import `dep_c.py`, preserving same file length and mtime.
3. Scan again in the same Atlas process.
4. Observe `scan2.cache.hit=true` while graph edges still show `main.py -> dep_b.py`.

Root cause:

`_scan_signature` uses file metadata and a 2500-file sample, not content hashes. The scan cache is then trusted as authoritative.

Risk:

Impact analysis, repository map, exports, and memory can describe old code after a developer edits or checks out new source. This directly creates wrong answers with high user trust damage.

Suggested mitigation:

Require content-backed invalidation for code files that enter the graph, or store per-file fingerprints in the cache and invalidate any graph node touched by a changed file. At minimum, mark cache-derived scans as possibly stale when timestamp precision or sample limits are insufficient.

### AS-F2: Large Repository Signature Blind Spot

Reproduction:

1. Create a repository with more than 2500 files.
2. Modify a file outside the first sampled 2500 paths.
3. Recompute `_scan_signature`.
4. The signature remains unchanged.

Root cause:

`_scan_signature` stops after `sample >= 2500`.

Risk:

Atlas targets large repositories, but large repos are exactly where cache invalidation is least complete. Late-path changes can fail to invalidate graph, impact, and export outputs.

Suggested mitigation:

Do not cap invalidation at the same sample used for fast UI estimates. Use a complete manifest hash for graph-eligible files, a cheap directory fingerprint plus changed-file index, or an explicit degraded cache status when sampling is used.

### AS-F3: Repository Memory Persistence Can Fail Silently

Reproduction:

1. Call `repository_memory.persist()` with a valid memory object under the audit workspace.
2. It returns `""`.
3. A `.json.tmp` file remains and no final `.json` memory file is created.
4. Manual `os.replace(tmp, final)` in the same path raised `PermissionError: [WinError 5] Access is denied`.

Root cause:

`persist()` swallows `OSError` and returns an empty path. `update_after_scan()` does not propagate or mark this as degraded.

Risk:

Repository memory may appear active for the current process while not being durable across restarts. Users can see inconsistent memory behavior without a warning.

Suggested mitigation:

Surface memory persistence failures in scan metadata, exports, and diagnostics. Treat memory persistence failure as degraded memory, not a silent success. Preserve the exception type and target path class without leaking sensitive paths.

### AS-F4: Repository Memory Poisoning Through Version-Only JSON

Reproduction:

1. Seed `{data_dir}/memory/{repo_id}.json` with a version-valid memory file for the repo.
2. Add fake previous hubs/risks such as `MALICIOUS_FAKE_HUB`.
3. Scan the repo.
4. `ATLAS_REPOSITORY_MEMORY v1` shows a delta referencing the fake previous hub and fake previous risk.

Observed packet excerpt:

```text
removed_hub: MALICIOUS_FAKE_HUB
new_risk: helper
since 2000-01-01T00:00:00Z
```

Root cause:

`repository_memory.load()` checks only `version`. It does not validate repo_id, repo_path, schema, bounds, previous scan identity, graph fingerprint, or integrity.

Risk:

Local stale or malicious memory can contaminate export context. Since this is sent to Codex/Claude/Cursor as repository evidence, it can steer the model toward nonexistent architecture changes.

Suggested mitigation:

Validate memory against current repo_id and path, enforce schema and bounds, include a graph/content fingerprint, and reject implausible deltas. If the previous memory cannot be trusted, start a fresh memory session and disclose that memory was reset.

### AS-F5: Unsupported-Language Workflows Return Success

Reproduction:

1. Scan a small Go-style repository with one Python helper file.
2. Run Build Plan prompt: `add event bus tracing`.
3. Run Investigation prompt: `why are duplicate events being fired`.
4. Build and Investigation both return `ok=true`, low-medium confidence, and select `hack/boilerplate/boilerplate.py`.

Observed behavior:

```text
Build: ok=true, confidence=low-medium, graph_health=healthy
Investigation: ok=true, confidence=low-medium, likely area: hack/boilerplate/boilerplate.py
Impact: ok=false, status=target_not_resolved
```

Root cause:

Unsupported or near-empty scans are not treated consistently across workflow APIs. Impact refuses more honestly, but Build and Investigation still produce plans from weak context.

Risk:

A user scanning Kubernetes, Go, Java, C#, or mixed-language repos can receive plausible but wrong plans. This is a major trust failure because the UI presents an answer instead of a refusal.

Suggested mitigation:

When graph coverage is unsupported, near-zero, or dominated by helper scripts, Build and Investigation should return explicit insufficient-evidence status and no ranked files. Graph health must not become `healthy` from a single incidental Python helper.

### AS-F6: Global Runtime State Race Surface

Reproduction:

Static inspection shows one module-level `_STATE` object stores active repo path, graph, scan, memory, cache, performance data, and workflow context. A simple concurrent scan probe did not produce a mismatch, but there is no obvious workflow-level lock around scan and workflow reads.

Root cause:

The runtime uses shared mutable process state for multi-step workflows.

Risk:

If two browser actions, scan jobs, or workflow API calls overlap, a workflow can read state mid-transition or after another repo has replaced global state.

Suggested mitigation:

Use a repository/session scoped state object or lock scan-to-workflow transitions. At minimum, every workflow response should include the repo_id and scan_id it used, and exports should verify they match the visible active repository.

## Checks That Passed

| Check | Result |
| --- | --- |
| Repository switch without rescan | Current checkout clears scan state. Build Plan, Investigation, Impact, and session export refused after `select_repository(repo_b)` until rescan. |
| Impact on unsupported Go target | Current checkout returned `ok=false` and `target_not_resolved` rather than fake impact success. |
| Support bundle source leak probe | Prior probe found no source content or secret filename in the support bundle entries inspected. |

## Highest-Risk Surfaces

1. Scan cache invalidation: stale graph can silently infect every workflow.
2. Repository memory persistence and integrity: memory can vanish silently or be poisoned.
3. Unsupported-language workflow handling: Build/Investigation can still emit plausible answers without enough evidence.
4. Global state: current guards improved repository switching, but concurrent workflow boundaries remain fragile.
5. Export trust: any stale graph or poisoned memory becomes portable context for external AI tools.
