# Phase 140 — Reliability Hardening

_Generated 2026-06-04 13:14:47_

Reliability-only hardening: degraded-scan detection, a safe transient
retry, and a failure taxonomy so Atlas processes repositories repeatedly
without manual intervention. No new intelligence, concepts, billing or UI.

## Success-rate dashboard

| Metric | Rate |
|---|---:|
| Scan success | **95.8%** |
| Graph build success (modules+edges) | **75.0%** |
| Impact success (live) | **66.7%** |
| Investigation success (live) | **100.0%** |

Evidence base: **24 scan executions** across **18 distinct repositories** (6 live repeated scans + 18 ingested from the overnight validation campaign).

## Failure taxonomy (every outcome classified)

| Category | Count |
|---|---:|
| Healthy (`ok`) | 20 |
| Unresolved-import explosion (`unresolved_import_explosion`) | 2 |
| Timeout (`timeout_failure`) | 1 |
| Zero-edge graph (`zero_edge_graph`) | 1 |

## Detected faults

| Repository | Source | Category | Modules | Edges | Warning |
|---|---|---|---:|---:|---|
| atlas_self | overnight | `timeout_failure` | 0 | 0 | Scan timed out before the full graph was built; results are partial. |
| langchain | overnight | `zero_edge_graph` | 1689 | 0 | No dependency edges resolved across 1689 modules — impact analysis will be weak. |
| openbb | overnight | `unresolved_import_explosion` | 1062 | 47 | 99% of imports are unresolved — cross-file impact may be under-counted. |
| sqlmodel | overnight | `unresolved_import_explosion` | 21 | 38 | 89% of imports are unresolved — cross-file impact may be under-counted. |

## Reliability features added (this phase)

1. **Degraded-scan auto-detection** (`jarvis_desktop/reliability.py`): every
   scan result is classified; degraded scans (0 modules, 0 edges, partial /
   timed-out graph, unresolved-import explosion, memory pressure) surface a
   warning immediately via `scan['reliability']` + `scan['health_warnings']`.
2. **Safe transient retry** (`api.scan_repository`): a massive-mode build that
   yields 0 modules from >500 files is rebuilt once (side-effect-free). Only
   `zero_module_scan` is auto-retried — timeouts and hard failures are not.
3. **Failure taxonomy**: stable categories (`ok`, `scan_crash`, `scan_failed`,
   `zero_module_scan`, `zero_edge_graph`, `partial_graph`, `timeout_failure`,
   `unresolved_import_explosion`, `memory_pressure`, `empty_repo`).
4. **Reliability harness** (`benchmarks/reliability/`): scans repos repeatedly,
   classifies every outcome, and writes this dashboard — reproducible.

## Repeatability evidence (live, repeated scans)

| Repository | Attempt | Category | Modules | Edges | Seconds | Impact ok | Investigation ok |
|---|---:|---|---:|---:|---:|:--:|:--:|
| django | 1 | `ok` | 929 | 2916 | 24.4 | ✓ | ✓ |
| django | 2 | `ok` | 929 | 2916 | 23.3 | ✓ | ✓ |
| fastapi | 1 | `ok` | 73 | 159 | 3.3 | ✓ | ✓ |
| fastapi | 2 | `ok` | 73 | 159 | 3.4 | ✓ | ✓ |
| quixbugs | 1 | `ok` | 4 | 0 | 0.2 | – | ✓ |
| quixbugs | 2 | `ok` | 4 | 0 | 0.2 | – | ✓ |

## Ingested campaign outcomes (breadth)

| Repository | Category | Modules | Edges |
|---|---|---:|---:|
| django | `ok` | 929 | 2915 |
| fastapi | `ok` | 73 | 159 |
| flask | `ok` | 24 | 129 |
| home_assistant | `ok` | 9709 | 36013 |
| nestjs | `ok` | 1276 | 2310 |
| nextjs | `ok` | 3114 | 5010 |
| pydantic | `ok` | 113 | 330 |
| qdrant | `ok` | 4 | 0 |
| quixbugs | `ok` | 4 | 0 |
| react | `ok` | 1717 | 3117 |
| requests | `ok` | 20 | 66 |
| rich | `ok` | 106 | 313 |
| typer | `ok` | 35 | 117 |
| vscode | `ok` | 7563 | 13228 |
| atlas_self | `timeout_failure` | 0 | 0 |
| openbb | `unresolved_import_explosion` | 1062 | 47 |
| sqlmodel | `unresolved_import_explosion` | 21 | 38 |
| langchain | `zero_edge_graph` | 1689 | 0 |

## Assessment

- **20/24** scan executions classified healthy or legitimately-empty; every fault has a category and an immediate warning.
- The previously-unhandled VS Code degenerate scan (0 modules) is now
  auto-detected and retried; timeouts and zero-edge graph failures are
  surfaced rather than silently producing empty analysis.
- Remaining known faults (self-scan timeout, zero-edge on edge-sparse repos)
  are now **classified and visible**, not silent — the prerequisite for
  unattended, repeatable processing.
