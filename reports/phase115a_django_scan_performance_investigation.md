# Phase 115A - Django Scan Performance Investigation

## Scope
- Repository under test: `C:\J.A.R.V.I.S\django`
- Objective: measure desktop scan performance without changing Builder Core behavior or optimizing.
- Diagnostic output: `reports/phase115a_django_scan_performance_metrics.json`

## What Was Instrumented
- Backend stage timing recorder added in `jarvis_desktop/api.py` (`_StageRecorder`, `_safe_rss_bytes`).
- Stage-level telemetry recorded for:
  - `pre_scan_estimate`
  - `indexing_repository`
  - `building_dependency_graph`
  - `extracting_architecture`
  - `detecting_architectural_risks`
  - `extracting_contracts` (desktop stage marker)
  - `generating_verification_evidence` (desktop stage marker)
  - `building_ai_context_packets` (with per-packet timing/tokens)
  - `graph_payload_preparation`
  - `final_summary_serialization`
- Scan status endpoint enhanced to report completion flags: `scan_status()`.
- Diagnostic APIs added:
  - `current_scan_performance()`
  - `run_scan_diagnostic(...)`
  - HTTP routes in `jarvis_desktop/server.py`:
    - `GET /api/repositories/current/scan-performance`
    - `POST /api/repositories/diagnostics/scan`

## Diagnostic Run
- Command executed:
  - `api.run_scan_diagnostic(r"C:\J.A.R.V.I.S\django", output_path="reports/phase115a_django_scan_performance_metrics.json", timeout_sec=900)`
- Outcome:
  - Timed out at 900 seconds (`timed_out: true`)
  - Scan did not complete
  - Backend stage at timeout: `building_graph`
  - `scan_complete: false`

## Stage Timing (Measured)

| Stage | Duration (ms) | Files Seen | Code Files | Modules | Edges | Notes |
|---|---:|---:|---:|---:|---:|---|
| `validate_repository_path` | 307 | 6939 | 2960 | 0 | 0 | Fast path validation |
| `pre_scan_estimate` | 900 | 6939 | 2960 | 1924 (estimate) | 0 | Fast estimator |
| `building_dependency_graph` | > 900000 (in-progress) | 6939 | 2960 | - | - | Not completed before timeout |

## Total Scan Time
- Completed scan time: **not reached**.
- Measured wall-clock before timeout: **900000 ms** (15 minutes), with scan still running.

## Slowest Stage
- `building_dependency_graph` is the dominant stage and did not finish within 15 minutes.

## Is The Scan Actually Stuck Or Only Slow?
- Evidence indicates **not crashed**, but **extremely slow in backend graph build**:
  - Scan job remained active (`cancelled: false`)
  - Stage remained `building_graph`
  - No completion payload emitted
- This is operationally perceived as "stuck", but telemetry indicates long-running compute.

## Is Frontend Progress Accurate?
- Frontend scan progress in `jarvis_desktop/static/app.js` is timer-driven, not backend-stage-driven:
  - Stages are advanced by `setInterval(..., 850)` and bar percent is synthetic.
  - The label "Building AI context packets" can be displayed while backend is still in `building_graph`.
- Conclusion: **UI progress is misleading for long scans** (80% label can diverge from actual backend stage).

## Context Packet Generation Findings
- Added packet-level instrumentation in `scan_repository()`:
  - packet count
  - per-packet estimated tokens
  - per-packet duration
  - slowest packet
  - explicit `serial_generation: true`
- In this Django run, packet generation telemetry did not execute yet because dependency graph stage did not finish.
- Therefore, current bottleneck is upstream of packet generation.

## Likely Root Cause (Current Evidence)
- Primary bottleneck is in dependency graph construction call inside desktop scan:
  - `depgraph.build_graph(repo)` in `jarvis_desktop/api.py::scan_repository`.
- Given repo scale (~6939 files, 2960 code files), this stage dominates end-to-end latency before any packet work begins.

## Recommended Optimization Plan (Do Next, Not In 115A)
1. Add sub-stage instrumentation inside dependency graph build path (builder-side timings) to isolate parser/import-resolution hot spots.
2. Add incremental progress reporting from backend scan stages to frontend (replace synthetic timer with real status polling).
3. Add timeout/heartbeat details to scan-status so UI can show "still computing graph" with elapsed time.
4. Profile dependency graph build on Django with cProfile/py-spy to identify highest cumulative functions.
5. Evaluate bounded-scope graph mode for very large Python repos as a controlled fallback (without changing default semantics until validated).

## Exact Files / Functions Involved
- `jarvis_desktop/api.py`
  - `_StageRecorder`
  - `_safe_rss_bytes`
  - `scan_repository`
  - `scan_status`
  - `current_scan_performance`
  - `run_scan_diagnostic`
- `jarvis_desktop/server.py`
  - `_route_handlers` additions for scan performance + diagnostics
- `jarvis_desktop/static/app.js`
  - `scanFlow`
  - `STAGES` / `setInterval` synthetic progress path

