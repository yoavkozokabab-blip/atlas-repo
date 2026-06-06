# Phase 173C Red Team Report

Date: 2026-06-06
Role: adversarial engineer
Scope: repository memory, exports, impact analysis, scans, cache, diagnostics, installer, trust system, graph building, symbol evidence, memory persistence, workflow APIs.

This pass did not modify Atlas production code. It created this report set only:

- `reports/phase173c_red_team.md`
- `reports/phase173c_attack_surface.md`
- `reports/phase173c_ship_blockers.md`

## Executive Verdict

Atlas is not ready for unsupervised external beta if the goal is developer trust.

The repository-switch stale-state bug appears mitigated in the current checkout: selecting a different repo clears scan state and workflows refuse until rescan. However, Atlas can still be broken in higher-impact ways:

1. It can reuse a stale graph after source edits.
2. It can miss invalidation in large repositories.
3. It can accept poisoned repository memory and export fake deltas.
4. It can silently fail to persist memory.
5. It can return `ok=true` Build/Investigation outputs on unsupported or near-empty graph coverage.

## Probe Results

| Probe | Result | Trust impact |
| --- | --- | --- |
| Repository switch without rescan | Passed current checkout. Scan state cleared; workflows refused. | Previous wrong-repo class reduced, keep regression tests. |
| Same-size/same-mtime source edit | Failed. Second scan cache hit and graph stayed stale. | P0: wrong graph, wrong exports, wrong impact. |
| File outside first 2500 signature sample | Failed. Signature unchanged. | P1: large repo invalidation gap. |
| Repository memory persistence | Failed in audit environment. `.json.tmp` remained; final JSON missing. | P1: memory drift and silent data loss. |
| Repository memory poisoning | Failed. Fake previous hub/risk appeared in memory delta. | P0: poisoned export context. |
| Unsupported Go Build/Investigation | Failed. Returned `ok=true` and selected a Python helper file. | P1: hallucination-like user output. |
| Unsupported Go Impact | Passed better than Build/Investigation. Returned `target_not_resolved`. | Not a current blocker for this route. |
| Support bundle source leak | No source leak found in prior probe. | Residual privacy risk only. |

## Issues

### RT-01: Stale Graph After Edited Import

Reproduction:

1. Scan a repo with `main.py` importing `dep_b.py`.
2. Edit `main.py` to import `dep_c.py` while preserving same file length and mtime.
3. Scan again.
4. Atlas reports a scan cache hit.
5. The graph still says `main.py -> dep_b.py`.

Root cause:

`_scan_signature` in `jarvis_desktop/api.py:466-486` does not hash file content and stops after a sample. The cache restore path trusts this signature for graph, index, risks, and evidence store.

Risk:

Atlas can tell the user what breaks based on old code. This corrupts repository map, impact analysis, Build Plan, Investigation, exports, and repository memory.

Suggested mitigation:

Add correctness-grade invalidation for graph-contributing files. Same-length import edits must invalidate graph edges. Stale cache should degrade graph health rather than present as fresh evidence.

### RT-02: Large Repo Cache Invalidation Blind Spot

Reproduction:

1. Create more than 2500 Python files.
2. Add or modify `z/late.py` outside the first sampled set.
3. Compare `_scan_signature` before and after.
4. Signature remains unchanged.

Root cause:

`_scan_signature` exits after 2500 files.

Risk:

Large repositories can change without cache invalidation. This is especially dangerous because Atlas is being positioned around large-repo context reduction.

Suggested mitigation:

Use complete graph-file manifests or explicitly mark sampled signatures as partial. Do not let sampled signatures back a healthy graph/cache claim.

### RT-03: Silent Repository Memory Persistence Failure

Reproduction:

1. Run `repository_memory.persist()` with a valid memory object.
2. It returns an empty string in this audit environment.
3. A `.json.tmp` file is left behind.
4. Manual `os.replace(tmp, final)` raises `PermissionError: [WinError 5] Access is denied`.

Root cause:

`repository_memory.persist()` catches `OSError` and returns `""`. `update_after_scan()` does not surface this as degraded and still places memory into process state.

Risk:

Atlas can appear to remember a repository during the current session but lose memory after restart, with no user-visible explanation. This causes memory drift and support confusion.

Suggested mitigation:

Track memory persistence status as part of scan metadata. If persistence fails, mark repository memory degraded and expose the exception type in diagnostics.

### RT-04: Repository Memory Poisoning

Reproduction:

1. Write a version-valid memory JSON for a repo path.
2. Include fake previous facts such as `MALICIOUS_FAKE_HUB`.
3. Scan the repo.
4. Ask for the session export packet.
5. The exported memory delta references the fake previous hub/risk.

Root cause:

`repository_memory.load()` checks only the version field. It does not verify the expected repo_id, canonical repo path, graph fingerprint, schema, value ranges, or integrity.

Risk:

Fake memory becomes trusted LLM context. This can make external AI tools reason from nonexistent repository history.

Suggested mitigation:

Validate memory identity and integrity before computing deltas. Reject suspicious previous memory and start a fresh session with an explicit reset notice.

### RT-05: Unsupported-Language Build/Investigation False Success

Reproduction:

1. Scan a Go-style repo that contains one incidental Python helper file.
2. Run Build Plan: `add event bus tracing`.
3. Run Investigation: `why are duplicate events being fired`.
4. Both workflows return `ok=true`.
5. Both route to `hack/boilerplate/boilerplate.py` or similar helper evidence.

Root cause:

Build and Investigation do not enforce the same refusal/degraded behavior as Impact. A tiny Python helper can make graph health appear healthy enough for workflow output even when the target repository is unsupported.

Risk:

Atlas looks like it understands a Go/Kubernetes repo while actually planning around a helper script. This is one of the fastest ways an external developer loses trust.

Suggested mitigation:

Use a shared evidence sufficiency gate across Build, Investigation, and Impact. If coverage is unsupported or graph evidence is too thin, return `ok=false` or explicit insufficient-evidence status, with no ranked files.

### RT-06: Global State Race Surface

Reproduction:

Static inspection: `_STATE` stores active path, scan, graph, index, risks, memory, cache, scan job, and workflow state globally. A basic concurrent scan probe did not reproduce a mismatch, but there is no strong session boundary around workflow reads.

Root cause:

Global mutable state is shared across scans and workflows.

Risk:

Concurrent scan/workflow operations can produce mixed repo or mixed scan results, especially when browser UI actions overlap.

Suggested mitigation:

Attach repo_id and scan_id to every workflow request and response. Refuse export when active state no longer matches the scan used to build the answer.

### RT-07: Export Trust Depends On Compromised Inputs

Reproduction:

Memory poisoning flows into `session_export_packet`. Build/Investigation/Impact exports are attached by `atlas_export.attach_workflow_exports`.

Root cause:

Exports do not independently verify that scan_id, memory_ref, graph health, and active repo path are all consistent before presenting compact context.

Risk:

Even if the Atlas UI appears cautious, the copied prompt can carry stale or poisoned facts into Codex/Claude/Cursor.

Suggested mitigation:

Every export should include and validate repo_id, scan_id, graph_health, cache freshness, and memory validation status. If any are degraded, the export must say so plainly.

## Non-Findings And Improvements

### Repository Switch Guard

Current checkout behavior:

- Scan repo A.
- Select repo B without scanning.
- `current_summary()` returns no scan.
- Build Plan returns `requires_rescan`.
- Investigation returns no scan.
- Impact returns no graph.
- Session export returns no scan.

This is the correct shape. Keep it covered by regression tests because it was previously a high-risk failure class.

### Unsupported Impact Refusal

For the probed Go target, Impact returned `ok=false` and `target_not_resolved`. That is safer than Build/Investigation and should be the model for other workflows.

### Support Bundle Source Content

A prior support bundle probe did not find source content or the secret test filename in the generated bundle. The residual risk is log/path privacy, not direct source inclusion.

## What Could Still Destroy User Trust?

1. Atlas answers from a stale graph after a normal source edit.
2. Atlas misses changes in large repositories because only the first 2500 files influence cache invalidation.
3. Atlas exports poisoned or stale repository memory as if it were trusted repository context.
4. Atlas silently loses repository memory persistence and gives inconsistent behavior across restarts.
5. Atlas says `ok=true` on unsupported-language repositories and points users to unrelated helper files.
6. Atlas lets external LLM prompts inherit stale graph, stale memory, or weak-evidence context.
7. Atlas uses one global runtime state object, leaving race-condition risk around overlapping scan/workflow/export calls.

Until these are fixed, the biggest product risk is not that Atlas lacks features. It is that Atlas can sound grounded when its evidence is stale, poisoned, or from the wrong coverage model.
