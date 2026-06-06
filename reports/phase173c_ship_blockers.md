# Phase 173C Ship Blockers

Date: 2026-06-06
Verdict: NO-GO for unsupervised external beta until the P0/P1 blockers below are fixed and regression-tested.

This is a red-team blocker list, not a feature proposal. It lists failures that can still destroy user trust.

## Blocker Summary

| ID | Severity | Area | Status | Why it blocks shipping |
| --- | --- | --- | --- | --- |
| SB-01 | P0 | Scan cache / graph | Confirmed current failure | Atlas can answer from stale graph after source edits. |
| SB-02 | P0 | Repository memory | Confirmed current failure | Memory can be poisoned and exported as repository evidence. |
| SB-03 | P1 | Memory persistence | Confirmed in audit environment | Memory persistence can fail silently while UI proceeds. |
| SB-04 | P1 | Unsupported language workflows | Confirmed current failure | Build/Investigation return `ok=true` from inadequate evidence. |
| SB-05 | P1 | Large repo invalidation | Confirmed current failure | Files outside the first 2500 signature sample do not invalidate cache. |
| SB-06 | P2 | Global state concurrency | Static high-risk surface | One global `_STATE` can mix repo, graph, memory, and workflow context under overlap. |

## SB-01: Stale Scan Cache / Stale Graph

Reproduction:

1. Create `main.py` importing `dep_b.py`.
2. Scan the repo.
3. Edit `main.py` to import `dep_c.py`, preserving same file length and mtime.
4. Scan again.
5. Observe cache hit and graph still reporting `main.py -> dep_b.py`.

Evidence:

```text
scan2_cache_hit: true
file_text_now: import dep_c
main_edges_after: module:dep_b.py
```

Root cause:

`jarvis_desktop/api.py:466-486` builds the scan signature from path, scope, size, and integer mtime for a limited sample. `jarvis_desktop/api.py:884-887` then trusts that signature to restore cached scan data.

Risk:

Atlas can generate repository map, impact analysis, investigation, Build Plan, and export prompts from code that no longer exists. This is the single most direct trust destroyer.

Suggested mitigation:

Use content-backed invalidation for files that contribute graph nodes/edges, or mark cache-derived graphs as stale/partial when content identity is not proven. Add a regression test that changes an import to another same-length import and verifies the graph edge changes.

## SB-02: Repository Memory Poisoning

Reproduction:

1. Seed the repository memory JSON with a valid version and fake previous architecture facts.
2. Scan the repo.
3. Request the session export packet.
4. The memory packet includes a delta referencing fake previous facts.

Evidence:

```text
removed_hub: MALICIOUS_FAKE_HUB
removed_risks: MALICIOUS_FAKE_RISK
session_count: 43
```

Root cause:

`jarvis_desktop/repository_memory.py:186-197` accepts any JSON with `version == MEMORY_VERSION`. It does not validate repo_id, repo_path, graph fingerprint, scan signature, schema bounds, or integrity.

Risk:

Fake memory can be exported to Claude/Cursor/Codex as trusted context. The user may believe Atlas remembered a real architecture change when the previous memory was stale or malicious.

Suggested mitigation:

Reject memory unless repo_id, canonical path, memory schema, bounds, and graph/content fingerprint match expectations. If validation fails, start fresh memory and explicitly report memory reset/degraded status.

## SB-03: Silent Memory Persistence Failure

Reproduction:

1. Call `repository_memory.persist()` with a valid memory object.
2. In the audit environment, it returns an empty string.
3. A `.json.tmp` file remains.
4. Manual replace in the same path raised `PermissionError: [WinError 5] Access is denied`.

Evidence:

```text
json_exists_after_scan: false
tmp_files_after_scan: *.json.tmp
persist_result: ""
```

Root cause:

`jarvis_desktop/repository_memory.py:166-180` catches `OSError` and returns `""`. `update_after_scan()` ignores the returned path and still caches memory in process state.

Risk:

Atlas can appear to have durable repository memory during one session while silently losing it across restarts. Worse, stale `.tmp` files can accumulate and diagnostics may not explain why memory is missing.

Suggested mitigation:

Make persistence failure visible in scan metadata and diagnostics. Treat memory as degraded when final write fails. Include exception type, not raw sensitive paths, in support output.

## SB-04: Unsupported-Language Build/Investigation False Success

Reproduction:

1. Scan a Go-style repository containing one incidental Python helper file.
2. Run Build Plan: `add event bus tracing`.
3. Run Investigation: `why are duplicate events being fired`.
4. Both return `ok=true` and point at `hack/boilerplate/boilerplate.py`.

Evidence:

```text
scan.module_count: 1
scan.dependency_edges: 0
build.ok: true
build.graph_health: healthy
investigate.ok: true
investigate.likely area: hack/boilerplate/boilerplate.py
impact.ok: false
impact.status: target_not_resolved
```

Root cause:

Build/Investigation do not share the stricter insufficient-evidence behavior seen in Impact. Graph health can be presented as healthy even when coverage is effectively one incidental Python file in a non-Python repo.

Risk:

Users on Go, Java, C#, TypeScript-heavy, or mixed repositories may receive confident-looking plans for unrelated helper scripts. This creates immediate "Atlas is hallucinating" trust loss.

Suggested mitigation:

Normalize unsupported-language and low-coverage handling across Build, Investigation, and Impact. Do not return `ok=true` with ranked files when graph coverage is unsupported or trivial.

## SB-05: First-2500-File Invalidation Blind Spot

Reproduction:

1. Create a repository with more than 2500 files.
2. Modify `z/late.py`, outside the first sampled files.
3. Compute `_scan_signature` before and after.
4. The signature is unchanged.

Evidence:

```text
unchanged: true
late_file: reports/phase173c_current_probe2/repo_blindspot/z/late.py
```

Root cause:

`jarvis_desktop/api.py:474-485` exits signature generation after 2500 files.

Risk:

Large repositories are the hardest and most valuable Atlas use case. The current invalidation model is least trustworthy exactly where users need it most.

Suggested mitigation:

Separate fast estimate sampling from correctness-critical invalidation. Use complete graph-file manifests, incremental change tracking, or an explicit "sampled cache" degraded status that prevents strong trust claims.

## SB-06: Shared Global State Race Surface

Reproduction:

Static inspection shows `_STATE` stores active path, scan, graph, index, risks, memory, scan job, cache, and workflow performance in one mutable process-level object. A simple concurrent scan probe did not reproduce a mismatch, but the race surface remains.

Root cause:

Repository context is global rather than session-scoped. Scan and workflow operations can read and write the same structure.

Risk:

Overlapping scans or workflow requests can produce wrong-repo exports or mixed graph/memory state if the interleaving lands badly.

Suggested mitigation:

Bind every workflow to a repo_id and scan_id, and refuse export if they do not match the active visible repository. Add concurrency tests for simultaneous scan plus Build/Investigation/Impact/export requests.

## Current Non-Blockers Checked

| Area | Current result |
| --- | --- |
| Repository switch without rescan | Current checkout clears scanned state. Workflows refused until rescan. |
| Unsupported Go Impact target | Current checkout returned `ok=false` / `target_not_resolved`, not fake success. |
| Support bundle source content | Prior probe did not find source content in generated support bundle entries. |

## Release Decision

NO-GO for first unsupervised beta.

Atlas can still produce trusted-looking answers from stale graph state, poisoned memory, and unsupported-language scans. Those are not cosmetic issues; they directly invalidate the premise that Atlas gives grounded repository intelligence.
