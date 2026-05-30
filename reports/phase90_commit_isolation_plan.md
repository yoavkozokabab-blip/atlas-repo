# Phase 90 Commit Isolation Plan

Date: 2026-05-30

Branch: `phase78-tool-registry`  
HEAD: `86a56c27` — `phase79: harden shadow llm router safety`

**Scope:** Prepare a clean Phase 90-only staging list. **No code was changed** in this pass.

---

## 1. Git evidence collected

### Commands run

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
git status --short
git ls-files --others --exclude-standard -- builder_core reports scripts tests
git branch --show-current
git log -1 --oneline
git ls-files builder_core/
```

### Key findings

| Observation | Detail |
| --- | --- |
| **`builder_core/` is entirely untracked** | `git ls-files builder_core/` returns nothing; whole package is `?? builder_core/` |
| **No Phase 90 files are committed yet** | All Phase 90 work lives in the working tree only |
| **Branch is behind Builder Core work** | HEAD is Phase 79; Builder Core phases 82–90 were never committed |
| **Large unrelated dirty tree** | ~10k `data/backups/*` deletions, runtime reports, voice WIP, router/classifier edits |

Filtered status (excluding `data/backups` noise) shows **modified tracked files that must not be staged**:

```text
 M .env.example
 M actions/registry.py
 M brain/intent_classifier.py
 M brain/router.py          ← explicit exclusion
 M config.py
 M voice/continuous_mic.py   ← explicit exclusion
 M voice/human_interruption.py
 M voice/interruption_manager.py
 M voice/realtime_tts.py
 M voice/streaming_pipeline.py
 M voice/streaming_stt/stream_session.py
?? voice/human_conversation.py
?? actions/project_intelligence_actions.py
?? project_intelligence/
 … hundreds of generated reports/blocker_trends/jarvis_investigations …
```

---

## 2. Phase 90-only files (verified)

Expected vs actual:

| Expected path | Status |
| --- | --- |
| `builder_core/bug_intelligence/finding.py` | **Present** — header: Phase 90 |
| `builder_core/bug_intelligence/facts.py` | **Present** — header: Phase 90 |
| `builder_core/bug_intelligence/agents.py` | **Present** — pipeline stages (no phase header; Phase 90 only in tree) |
| `builder_core/bug_intelligence/engine.py` | **Present** — header: Phase 90 |
| `builder_core/cli.py` | **Present** — **not Phase-90-only** (Phase 82–89 commands + unified wiring) |
| `builder_core/tests/test_phase90_unified_engine.py` | **Present** |
| `reports/phase90_rule_migration_table.md` | **Present** |
| `reports/phase90_unified_builder_intelligence_engine.md` | **Missing** — not found in repo |

### Strict Phase 90 artifact list (6 code paths + 1 report + 1 test)

```text
builder_core/bug_intelligence/finding.py
builder_core/bug_intelligence/facts.py
builder_core/bug_intelligence/agents.py
builder_core/bug_intelligence/engine.py
builder_core/tests/test_phase90_unified_engine.py
reports/phase90_rule_migration_table.md
```

### Phase 90 touch on shared files (partial, not isolatable without context)

| File | Phase 90 role | Also contains |
| --- | --- | --- |
| `builder_core/cli.py` | Routes `analyze-file`, `bug-scan`, `security-scan` through `bi_engine`; unified section renderer | Phase 82 init/ask/risk; Phase 83 bug commands; legacy `benchmark-quixbugs` |
| `builder_core/tests/test_bug_intelligence.py` | Comments reference unified engine sections | Phase 83 tests |

There is **no separate diff** for `cli.py` — the entire file is new/untracked.

---

## 3. Required dependency files (older uncommitted phases)

Phase 90 **imports and cannot run without** these modules (import graph from `engine.py` → `agents.py`):

```
engine.py
  └─ agents.py
       ├─ finding.py          (Phase 90)
       ├─ facts.py            (Phase 90) → dataflow.py, valueflow.py
       ├─ patterns.py         (Phase 83 + 87 rewire)
       ├─ security.py         (Phase 89)
       └─ semantic_reasoning.py (Phase 83, via AlgorithmAgent)
```

### Minimum runnable dependency set (17 modules + package skeleton)

| Phase | Path | Why required |
| ---: | --- | --- |
| 82 | `builder_core/__init__.py` | Package |
| 82 | `builder_core/store.py` | `cli.py` project root resolution |
| 82 | `builder_core/cli.py` | CLI entry + Phase 90 commands |
| 83 | `builder_core/semantic_reasoning.py` | `AlgorithmAgent` |
| 83 | `builder_core/bug_intelligence/patterns.py` | `LogicBugAgent` |
| 83 | `builder_core/bug_intelligence/findings.py` | Pattern dataclass shape (used by `patterns.py`) |
| 83 | `builder_core/bug_intelligence/algorithm_profiles.py` | Semantic profiles |
| 86 | `builder_core/bug_intelligence/dataflow.py` | `facts.py` |
| 89 | `builder_core/bug_intelligence/valueflow.py` | `facts.py` |
| 89 | `builder_core/bug_intelligence/security.py` | `SecurityAgent` |
| 90 | `finding.py`, `facts.py`, `agents.py`, `engine.py` | Unified engine |

Optional but **strongly recommended in same commit**:

| Path | Reason |
| --- | --- |
| `builder_core/bug_intelligence/__init__.py` | Package exports |
| `builder_core/tests/test_phase86_dataflow.py` | Guards dataflow layer |
| `builder_core/tests/test_phase87_dataflow_rewire.py` | Guards Phase 87 rewire |
| `builder_core/tests/test_phase89_value_dataflow_taint.py` | Guards taint/security |
| `builder_core/tests/test_bug_intelligence.py` | Regression for legacy + unified CLI |
| `reports/phase87_dataflow_rule_rewire.md` | Documents Phase 87 dependency |
| `reports/phase89_value_dataflow_taint.md` | Documents Phase 89 dependency |

### Not required for Phase 90 engine runtime (exclude from minimal commit)

| Path | Phase | Notes |
| --- | ---: | --- |
| `builder_core/benchmark.py`, `semantic_reasoning` benchmark path | 83–85 | Used only by `benchmark-quixbugs` CLI |
| `builder_core/external_benchmark.py`, `benchmarks/holdout/**` | 84–85 | Holdout harness; engine doc says benchmarks stay on legacy path |
| `builder_core/ask.py`, `indexer.py`, `risk.py`, … | 82 | Project intelligence CLI; unrelated to Phase 90 engine |
| `builder_core/algorithm_profiles.py` (root) | 83 | Duplicate of bug_intelligence copy; semantic uses `builder_core/algorithm_profiles.py` via `from . import semantic_reasoning` parent — verify: semantic_reasoning imports `from .algorithm_profiles` which is **builder_core/algorithm_profiles.py** |

**Import check:** `semantic_reasoning.py` line 10: `from .algorithm_profiles import detect_profiles` → requires `builder_core/algorithm_profiles.py` (root), not only `bug_intelligence/algorithm_profiles.py`.

Add to dependency set:

```text
builder_core/algorithm_profiles.py
builder_core/python_analysis.py   # only if benchmark-quixbugs kept in cli; not needed for engine tests
```

Phase 90 tests run with:

```powershell
py -3 -m pytest builder_core/tests/test_phase90_unified_engine.py -q
```

No QuixBugs checkout required for that test file.

---

## 4. Files that must NOT be staged

### Explicit user exclusions

```text
voice/**
brain/router.py
brain/intent_classifier.py   # also modified; keep out unless separate Phase 80 commit
actions/**                   # unless separate phase commit
project_intelligence/**
config.py
.env.example
```

### Generated / runtime / unrelated reports

```text
data/**
reports/blocker_trends/**
reports/jarvis_investigations/**
reports/jarvis_logs/**
reports/hypothesis_engine/**
reports/notifications/**
reports/proactive_monitor/**
reports/root_cause_engine/**
reports/verification_plans/**
reports/causal_analysis/**
reports/phase80_smoke_samples.json
reports/phase80_sample_outputs.txt
data/external_benchmarks/**
```

### Other uncommitted phase work (do not mix into Phase 90 commit)

```text
reports/phase80_project_intelligence.md
reports/phase84_external_benchmark_plan.md
reports/phase85_*
scripts/smoke_phase*
scripts/run_phase84_holdout_benchmark.py
scripts/generate_phase85_evidence.py
tests/test_phase80_project_intelligence_questions.py
tests/test_phase84_external_benchmark.py
tests/test_project_intelligence_questions.py
actions/project_intelligence_actions.py
project_intelligence/**
```

### Entire `builder_core/` extras (optional modules — stage only if doing monolithic Builder Core commit)

```text
builder_core/ask.py
builder_core/indexer.py
builder_core/risk.py
builder_core/retrieval.py
builder_core/topics.py
builder_core/decisions.py
builder_core/gitutil.py
builder_core/external_benchmark.py
builder_core/benchmarks/**
builder_core/scripts/smoke_phase82*
builder_core/tests/test_builder_core.py
```

---

## 5. Staging recommendations

### Option A — **Recommended:** Builder Core stack commit (82–90 foundation)

Phase 90 **cannot** ship alone. Commit the **minimum runnable Builder Core stack** in one isolated commit (or 86→89→90 stacked commits on a `builder-core` branch).

```powershell
cd C:\J.A.R.V.I.S\local_jarvis

# Package skeleton + CLI
git add builder_core/__init__.py
git add builder_core/store.py
git add builder_core/cli.py
git add builder_core/algorithm_profiles.py

# Bug intelligence stack (83 → 89 → 90)
git add builder_core/semantic_reasoning.py
git add builder_core/bug_intelligence/__init__.py
git add builder_core/bug_intelligence/algorithm_profiles.py
git add builder_core/bug_intelligence/analyzer.py
git add builder_core/bug_intelligence/findings.py
git add builder_core/bug_intelligence/patterns.py
git add builder_core/bug_intelligence/ranking.py
git add builder_core/bug_intelligence/dataflow.py
git add builder_core/bug_intelligence/valueflow.py
git add builder_core/bug_intelligence/security.py
git add builder_core/bug_intelligence/finding.py
git add builder_core/bug_intelligence/facts.py
git add builder_core/bug_intelligence/agents.py
git add builder_core/bug_intelligence/engine.py

# Tests
git add builder_core/tests/__init__.py
git add builder_core/tests/test_bug_intelligence.py
git add builder_core/tests/test_phase86_dataflow.py
git add builder_core/tests/test_phase87_dataflow_rewire.py
git add builder_core/tests/test_phase89_value_dataflow_taint.py
git add builder_core/tests/test_phase90_unified_engine.py

# Phase 90 (+ supporting) reports only
git add reports/phase90_rule_migration_table.md
git add reports/phase87_dataflow_rule_rewire.md
git add reports/phase89_value_dataflow_taint.md
git add reports/phase90_commit_isolation_plan.md
```

Verify before commit:

```powershell
py -3 -m pytest builder_core/tests/test_phase90_unified_engine.py -q
py -3 -m pytest builder_core/tests/test_phase86_dataflow.py builder_core/tests/test_phase87_dataflow_rewire.py builder_core/tests/test_phase89_value_dataflow_taint.py -q
git diff --cached --name-only
```

Suggested commit message:

```text
builder_core: unified intelligence engine (phases 86–90 stack)

Add dataflow, value-flow/taint security, and Phase 90 unified finding schema,
pipeline agents, and CLI wiring. Benchmark harness intentionally unchanged.
```

---

### Option B — Phase 90-only (documentation + new modules, **not runnable alone**)

Use only if committing **after** Option A already landed, or as a second commit on top of an existing Builder Core base.

```powershell
git add builder_core/bug_intelligence/finding.py
git add builder_core/bug_intelligence/facts.py
git add builder_core/bug_intelligence/agents.py
git add builder_core/bug_intelligence/engine.py
git add builder_core/tests/test_phase90_unified_engine.py
git add reports/phase90_rule_migration_table.md
git add reports/phase90_commit_isolation_plan.md
# Also stage cli.py if not already committed:
git add builder_core/cli.py
```

**Will fail tests** unless Phase 86/89/83 dependencies are already on the branch.

---

### Option C — Strict Phase 90 file list only (smallest diff, **broken in isolation**)

```powershell
git add `
  builder_core/bug_intelligence/finding.py `
  builder_core/bug_intelligence/facts.py `
  builder_core/bug_intelligence/agents.py `
  builder_core/bug_intelligence/engine.py `
  builder_core/tests/test_phase90_unified_engine.py `
  reports/phase90_rule_migration_table.md `
  reports/phase90_commit_isolation_plan.md
```

**Do not use** unless dependency commit already exists.

---

## 6. Dependency risk matrix

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Entire `builder_core/` untracked | **High** | First Builder Core commit must include dependency stack, not Phase 90 alone |
| `cli.py` mixes phases 82–90 | **Medium** | Accept monolithic CLI commit or split only after extracting shared base |
| Missing `phase90_unified_builder_intelligence_engine.md` | **Low** | Add in follow-up doc commit or rename `phase90_rule_migration_table.md` as primary artifact |
| `brain/router.py` / `voice/**` accidentally staged | **High** | Use path-scoped `git add`; run `git diff --cached --name-only` gate |
| Benchmark vs engine path split | **Low** | `benchmark-quixbugs` still uses `semantic_benchmark.evaluate_quixbugs`; staging `benchmark.py` optional |
| Duplicate `algorithm_profiles.py` (root vs bug_intelligence) | **Medium** | Include **both** or consolidate in a later refactor commit |
| Runtime report noise in `git status` | **Medium** | Never `git add reports/` without explicit path list |

---

## 7. Can Phase 90 be committed alone?

| Question | Answer |
| --- | --- |
| Can Phase 90 files be **named** in isolation? | **Yes** — 4 modules + 1 test + 1 report |
| Can Phase 90 be **committed and run tests** in isolation? | **No** — requires `dataflow`, `valueflow`, `security`, `patterns`, `semantic_reasoning`, `store`, `cli` |
| Does it require a **prior Builder Core commit**? | **Yes** — on current branch nothing under `builder_core/` is tracked |
| Recommended strategy | **One Builder Core foundation commit (Option A)** on a dedicated branch, then optional doc-only follow-ups |

---

## 8. Pre-commit checklist

```powershell
# 1. Confirm staged set is Builder Core only
git diff --cached --name-only

# 2. Confirm exclusions absent
git diff --cached --name-only | Select-String -Pattern 'voice/|brain/router|project_intelligence|data/'

# 3. Run Phase 90 tests
py -3 -m pytest builder_core/tests/test_phase90_unified_engine.py -q

# 4. Optional dependency tests
py -3 -m pytest builder_core/tests/test_phase86_dataflow.py builder_core/tests/test_phase87_dataflow_rewire.py builder_core/tests/test_phase89_value_dataflow_taint.py -q
```

---

## 9. Summary counts

| Category | Count |
| --- | ---: |
| Phase 90-only new modules | 4 |
| Phase 90 test file | 1 |
| Phase 90 report(s) present | 1 (`phase90_rule_migration_table.md`) |
| Phase 90 report missing | 1 (`phase90_unified_builder_intelligence_engine.md`) |
| Minimum dependency modules (excl. tests) | ~15 |
| Untracked `builder_core/` files total | 64 |
| Modified tracked files to **avoid** | brain/router, voice/*, config, actions/registry, … |

---

## 10. `git diff --name-only` for this plan

This audit added one file only:

```text
reports/phase90_commit_isolation_plan.md
```

(No analyzer or semantic rule changes.)
