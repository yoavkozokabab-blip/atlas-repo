# Phase 100E — Context Compression Benchmark Execution

**Status:** Execution complete
**Date:** 2026-06-01
**Protocol:** `phase100b_context_compression_benchmark_design.md`
**Constraints:** No detector changes; no benchmark tuning

---

## 1. Executive summary

| Item | Value |
|------|-------|
| Tasks | 20 (architecture 8, impact 6, repository understanding 6) |
| Trials per task × arm | 3 |
| Repository | `C:\J.A.R.V.I.S\local_jarvis` |
| Commit | `b2871fafeeacbe247117ef4a8d68027580429a68` |
| Model (token pricing proxy) | `claude-sonnet-4-20250514 (token accounting proxy)` |
| **Verdict** | **PARTIAL** |
| Suite compression ratio (A/B tokens) | 3.168× |
| Mean quality Claude Only → +JARVIS | 2.15 → 2.0 (Δ -0.15) |
| Elapsed | 396.6s |

**Execution mode:** Deterministic harness measuring **tool-result context** for each arm.
Arm A simulates Claude-only `read_file`/`grep` paths preregistered per task; Arm B invokes
live JARVIS `ask` / `graph summary` / `impact-*` tools. Token counts use chars÷4 (Phase 100B §3).
Quality uses automated anchor matching (0–4); blinded human scoring is recommended before product claims.

---

## 2. Summary table (suite medians)

| Metric | Claude Only (A) | Claude + JARVIS (B) | Δ / ratio |
|--------|----------------:|--------------------:|-----------|
| Total input tokens (sum of task medians) | 71,429 | 23,242 | 3.168× |
| Peak context tokens (sum of medians) | 71,429 | 23,242 | 3.073× |
| Wall-clock (sum of medians, s) | 13.23 | 13.03 | 1.5% reduction |
| Cost USD (sum of medians) | $0.4132 | $0.1220 | 70.5% reduction |
| Mean answer quality (0–4) | 2.15 | 2.0 | -0.15 |

### Index build (Arm B, amortized separately)

| Index + depgraph build | 316.744s | ~6,453,965 token-equivalent |
| Depgraph degraded | True |

---

## 3. Tier metrics by category

| Category | Tasks | Compression A/B | Mean quality A | Mean quality B |
|----------|------:|------------------:|---------------:|---------------:|
| architecture | 8 | 2.854× | 1.12 | 2.38 |
| impact | 6 | 4.899× | 2.33 | 2.00 |
| repository_understanding | 6 | 2.534× | 3.33 | 1.50 |

---

## 4. Success gates (Phase 100B §5)

Per-task **answer quality** (0–4, anchor-based) substitutes for blinded human scoring in
this automated run. **Break-even** (index amortized over steady-state token savings):
~2,227 tasks at current per-task median savings.

| Collected metric | Arm A | Arm B | Notes |
|------------------|-------|-------|-------|
| Input / total tokens | 71,429 | 23,242 | chars÷4 proxy |
| Peak context | 71,429 | 23,242 | max turn occupancy |
| Wall-clock (s) | 13.23 | 13.03 | harness only |
| Cost (USD) | $0.413 | $0.122 | frozen Sonnet price table |
| Answer quality (mean) | 2.15 | 2.00 | automated anchors |

| Gate (Phase 100B §5) | Pass |
|----------------------|:----:|
| quality_non_inferiority | no |
| no_fabrication_regression | no |
| token_compression_2x | yes |
| cost_reduction_40pct | yes |
| architecture_compression_3x | no |
| impact_compression_3x | yes |
| control_integrity | no |
| trap_honesty | yes |

---

## 5. Per-task results

| ID | Category | Arm A tokens | Arm B tokens | Ratio | Q(A) | Q(B) |
|----|----------|-------------:|-------------:|------:|-----:|-----:|
| A1 | architecture | 9,489 | 2,324 | 4.08× | 0 | 4 |
| A2 | architecture | 589 | 1,476 | 0.4× | 1 | 1 |
| A3 | architecture | 585 | 774 | 0.76× | 1 | 1 |
| A4 | architecture | 8,955 | 1,177 | 7.61× | 0 | 4 |
| A5 | architecture | 11,279 | 1,265 | 8.92× | 2 | 1 |
| A6 | architecture | 1,967 | 2,315 | 0.85× | 0 | 4 |
| A7 | architecture | 3,841 | 2,120 | 1.81× | 4 | 2 |
| A8 | architecture | 585 | 1,617 | 0.36× | 1 | 2 |
| I1 | impact | 1,310 | 945 | 1.39× | 2 | 1 |
| I2 | impact | 6,466 | 954 | 6.78× | 4 | 1 |
| I3 | impact | 586 | 816 | 0.72× | 1 | 4 |
| I4 | impact | 11,591 | 942 | 12.3× | 4 | 1 |
| I5 | impact | 580 | 810 | 0.72× | 1 | 4 |
| I6 | impact | 5,934 | 935 | 6.35× | 2 | 1 |
| C1 | repository_understanding | 3,972 | 1,240 | 3.2× | 0 | 0 |
| C2 | repository_understanding | 8,064 | 1,578 | 5.11× | 4 | 0 |
| C3 | repository_understanding | 6,425 | 1,406 | 4.57× | 4 | 4 |
| C4 | repository_understanding | 816 | 2,132 | 0.38× | 4 | 0 |
| C5 | repository_understanding | 679 | 956 | 0.71× | 4 | 1 |
| C6 | repository_understanding | 976 | 947 | 1.03× | 4 | 4 |

---

## 6. Artifacts

| File | Description |
|------|-------------|
| `data/benchmarks/phase100e/manifest.json` | Frozen run manifest |
| `reports/phase100e_run/raw_trials.json` | Per trial metrics |
| `reports/phase100e_run/task_summary.json` | Medians per task × arm |
| `reports/phase100e_run/verdict.json` | Suite gates + verdict |

---

## 7. Honest limitations

- No live Claude API calls were made; arms differ only in **context delivered** to the agent.
- Automated quality is anchor-based; product claims should add blinded human scoring (100B §6.2).
- Single-repo (`local_jarvis`); generalization requires re-pinning the manifest on other repos.
- Index-build cost is excluded from per-task steady-state medians but reported separately.

