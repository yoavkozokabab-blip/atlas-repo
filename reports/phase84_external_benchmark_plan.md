# Phase 84 — External Benchmark Validation Plan

Date: 2026-05-30

## Executive Summary

**BugsInPy cannot be used directly in this Windows environment** without Docker/Linux
tooling. A **lightweight static holdout benchmark** was built and measured instead.

**Recommendation: B — validate on additional corpora first** before expanding QuixBugs
semantic rules. Holdout measurement shows partial algorithm-rule transfer but also
**precision regression** (100% on QuixBugs → 66.7% on holdout) from rules that fire on
correct transfer implementations.

---

## 1. BugsInPy Investigation

### What BugsInPy Is

[BugsInPy](https://github.com/soarsmu/BugsInPy) is a benchmark of **493 real bugs**
from **17 Python projects** (youtube-dl, pandas, ansible, black, tqdm, etc.), inspired
by Defects4J. Each bug includes:

| Artifact | Purpose |
| --- | --- |
| `projects/<name>/bugs/<id>/bug.info` | Python version, buggy/fixed commit SHAs, failing test |
| `bug_patch.txt` | Unified diff (fix patch) |
| `run_test.sh`, `setup.sh`, `requirements.txt` | Reproduction scripts |
| `framework/bin/bugsinpy-*` | Bash CLI: checkout, compile, test, coverage |

### Repository Size (metadata-only sparse clone)

Probe clone command:

```powershell
git clone --depth 1 --filter=blob:none --sparse `
  https://github.com/soarsmu/BugsInPy `
  data\external_benchmarks\BugsInPy_probe
cd data\external_benchmarks\BugsInPy_probe
git sparse-checkout set framework projects
```

Observed:

| Metric | Value |
| --- | ---: |
| GitHub reported size | ~1.3 MB (metadata); sparse `projects/` + `framework/` ≈ 2,324 files |
| Projects | 17 |
| Bug entries (`bug.info` files) | 501 |
| Primary language in repo | Shell (framework scripts) |

Full reproduction additionally checks out **upstream project repos** at pinned commits
(not stored inline) — disk and network cost is much larger than the metadata tree.

### Installation Requirements (official)

From BugsInPy README and Dockerfile:

1. Clone `https://github.com/soarsmu/BugsInPy`
2. Add `framework/bin` to `PATH`
3. **Recommended:** Docker (`docker build`, `docker run`) with Ubuntu-based image
4. Per-bug Python version via Miniconda/uv (e.g. `python_version="3.8.1"` in `bug.info`)
5. Run `bugsinpy-checkout -p <project> -i <id> -v 0|1 -w <workspace>`
6. Run `bugsinpy-compile` and `bugsinpy-test`

Documented resource guidance for reproducing all projects: **4 cores, 8 GB RAM, ~100 GB disk**.

### Windows Compatibility

| Requirement | This environment | Compatible? |
| --- | --- | --- |
| Bash checkout/test scripts | PowerShell only | **No** — `bugsinpy-checkout` is `#!/usr/bin/env bash` |
| Docker | `docker` not installed | **No** |
| Per-bug Python versions (3.6–3.9 typical) | Python **3.13.0** system default | **No** for test reproduction |
| Upstream compile/test | Linux-oriented deps, conda/pip mix | **Unreliable on native Windows** |
| Static reading of `bug_patch.txt` | UTF-8 text files | **Yes** (metadata only) |

### Benchmark Structure (relevant to Builder Core)

BugsInPy ground truth is **test-based**: buggy checkout fails a specific test; fixed
checkout passes. Builder Core Bug Intelligence is **static AST / semantic-rule**
analysis — it does not run tests.

To use BugsInPy faithfully you must:

1. Check out buggy and fixed file versions at pinned commits
2. Identify changed source files from `bug_patch.txt`
3. Run static analysis on those files (optional test-free subset)

Step 1 requires the full BugsInPy framework (blocked here).

---

## 2. Feasibility Verdict

### Full BugsInPy reproduction: **NOT FEASIBLE** in this environment

Reasons:

- No Docker
- Bash-only framework scripts
- Per-bug legacy Python versions and Linux package dependencies
- User constraint: **do not modify external repositories** (checkout mutates workspaces)

### Static metadata extraction: **FEASIBLE** (partial)

`bug_patch.txt` and `bug.info` can be read without checkout. This supports building
**derived holdout snippets**, not official BugsInPy test-verified evaluation.

---

## 3. Lightweight Holdout Benchmark (Implemented)

Because full BugsInPy is blocked, a **12-case holdout corpus** was added under:

```text
builder_core/benchmarks/holdout/
  manifest.json
  pairs/<case_id>/buggy.py
  pairs/<case_id>/fixed.py
```

### Corpus composition

| Category | Cases | Purpose |
| --- | ---: | --- |
| Independent classic Python bugs | 6 | Non-QuixBugs, non-algorithm (mutable default, wrong operator, etc.) |
| Synthetic algorithm transfer | 3 | Same invariant families as QuixBugs rules, different code |
| BugsInPy patch-derived snippets | 3 | Real-world bugs from tqdm/black/PySnooper patches (minimal wrappers) |

No new semantic rules were added. Evaluation reuses existing `analyze_python()` semantic
findings (same methodology as QuixBugs benchmark in `builder_core/benchmark.py`).

### Evaluation methodology

For each holdout pair:

- **TP** — semantic finding on `buggy.py`
- **FN** — no semantic finding on `buggy.py`
- **FP** — semantic finding on `fixed.py`
- **TN** — no semantic finding on `fixed.py`

File-level precision/recall (paired with QuixBugs Phase 83E convention).

---

## 4. Commands Run

### Environment probe

```powershell
Test-Path C:\Repos\QuixBugs          # True
Test-Path C:\Repos\BugsInPy          # False
docker --version                     # not installed
py -3 --version                      # Python 3.13.0
```

### BugsInPy metadata probe

```powershell
git clone --depth 1 --filter=blob:none --sparse `
  https://github.com/soarsmu/BugsInPy `
  data\external_benchmarks\BugsInPy_probe
cd data\external_benchmarks\BugsInPy_probe
git sparse-checkout set framework projects
(Get-ChildItem projects -Recurse -Filter bug.info).Count   # 501
Get-ChildItem projects -Directory                          # 17 projects
```

### QuixBugs baseline (in-domain)

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

### External holdout (out-of-domain / transfer)

```powershell
py -3 scripts/run_phase84_holdout_benchmark.py
py -3 scripts/smoke_phase84_external_benchmark.py
```

---

## 5. Benchmark Results

### 5.1 QuixBugs (in-domain baseline — unchanged)

| Metric | Value |
| --- | ---: |
| Buggy files | 40 |
| Correct files | 40 |
| **TP** | 12 |
| **FP** | 0 |
| **FN** | 28 |
| **TN** | 40 |
| **Precision** | 1.0000 |
| **Recall** | 0.3000 |

### 5.2 External holdout (12 cases)

| Metric | Value |
| --- | ---: |
| Cases | 12 |
| **TP** | 2 |
| **FP** | 1 |
| **FN** | 10 |
| **TN** | 11 |
| **Precision** | 0.6667 |
| **Recall** | 0.1667 |
| **Accuracy** | 0.5417 |

### 5.3 Per-case breakdown

| Case | Source | Buggy findings | Fixed findings (FP) |
| --- | --- | --- | --- |
| `transfer_bfs_empty_queue` | synthetic_transfer | `bfs_queue_exhaustion`, `bfs_missing_visited_tracking`, `graph_traversal_cycle_handling` | `bfs_missing_visited_tracking`, `graph_traversal_cycle_handling` |
| `transfer_gcd_no_rotate` | synthetic_transfer | `recursive_euclidean_state_not_rotated` | — |
| `transfer_quicksort_duplicates` | synthetic_transfer | — | — |
| 6 classic independent cases | independent | — | — |
| 3 BugsInPy-derived snippets | bugsinpy_patch | — | — |

### 5.4 Interpretation

1. **QuixBugs rules partially transfer** to synthetically rewritten algorithm code
   (BFS `while True`, GCD rotation) — confirms rules are not filename-literal.
2. **Precision is not preserved on transfer**: correct BFS still triggers
   `bfs_missing_visited_tracking` and `graph_traversal_cycle_handling` — rules are
   over-eager outside the QuixBugs corpus.
3. **No detection on real-world BugsInPy-style bugs** (encoding, executor fallback,
   API argument order) — current semantic rule set is **algorithm-domain-specific**,
   not general bug intelligence.
4. **Quicksort duplicate rule did not fire** on synthetic transfer case — profile or
   pattern matching is still tightly coupled to QuixBugs structure.

---

## 6. Path to Full BugsInPy Validation (Future)

When Linux/Docker is available:

```bash
git clone https://github.com/soarsmu/BugsInPy
cd BugsInPy && docker build -t bugsinpy .
docker run -dt -v ./projects:/home/bugsinpy/projects -v ./workspace:/home/workspace --name bip bugsinpy
docker exec -it bip bash
bugsinpy-checkout -p tqdm -v 0 -i 1 -w /home/workspace/tqdm-buggy
bugsinpy-checkout -p tqdm -v 1 -i 1 -w /home/workspace/tqdm-fixed
# Static-only Builder Core pass on changed files from bug_patch.txt
```

Recommended subset for first full pass: **20 bugs** across 5 projects (tqdm, black,
PySnooper, httpie, cookiecutter) — diverse bug types, smaller checkout cost.

---

## 7. Recommendation

### Choose **B — validate on additional corpora first**

Do **not** expand QuixBugs semantic rules yet.

Rationale:

| Evidence | Implication |
| --- | --- |
| QuixBugs precision 100%, recall 30% | In-domain tuning works but coverage is low |
| Holdout precision **66.7%** with only 12 cases | Rule expansion on QuixBugs alone risks **increasing false positives** on non-QuixBugs code |
| Holdout recall **16.7%** on mixed corpus | Algorithm rules do not generalize to real-world BugsInPy bug classes |
| Full BugsInPy blocked here | Need Docker/Linux pipeline OR grow the static holdout corpus before rule growth |

### Next steps (ordered)

1. **Expand holdout to 30–50 cases** — more BugsInPy patch snippets + synthetic transfer variants
2. **Add holdout gate to CI** — fail if precision on holdout drops below 0.90
3. **Tighten BFS ancillary rules** — `bfs_missing_visited_tracking` should not fire on correct minimal BFS
4. **Provision Docker/Linux runner** for official BugsInPy static checkout benchmark
5. Only then resume QuixBugs recall expansion (Phase 83C roadmap) with holdout guardrails

---

## 8. Files Added (Phase 84)

| Path | Role |
| --- | --- |
| `builder_core/external_benchmark.py` | Holdout evaluator |
| `builder_core/benchmarks/holdout/manifest.json` | Case catalog |
| `builder_core/benchmarks/holdout/pairs/*/` | 12 buggy/fixed pairs |
| `scripts/run_phase84_holdout_benchmark.py` | QuixBugs + holdout runner |
| `scripts/smoke_phase84_external_benchmark.py` | Smoke test |
| `reports/phase84_external_benchmark_plan.md` | This report |

Local-only investigation artifact (not committed required):

```text
data/external_benchmarks/BugsInPy_probe/   # sparse metadata clone for investigation
```

---

## 9. Safety / Boundary Confirmation

- No new semantic bug rules added
- No voice, browser, trading, website, router, or memory changes
- No external repository modifications
- Evaluation is read-only static analysis
