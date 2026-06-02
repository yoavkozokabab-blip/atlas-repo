# RU-1 — Repository Understanding Audit

**Status:** Audit only. No code, no fixes, no tuning. Explains the failure.
**Date:** 2026-05-31
**Question:** Why does `ask()` retrieve benchmark/dataset content (BugsInPy,
QuixBugs, holdout, phase benchmark reports) instead of repository architecture
(`core/`, `voice/`, `browser/`, `autonomy/`, `README_ARCHITECTURE`)?

---

## 0. TL;DR

`ask()` cannot retrieve repository architecture because **it never looks at the
architecture.** Two compounding defects:

1. **The corpus is `reports/*.md`, not the code.** The primary answerer
   (`project_intelligence`) searches `reports/*.md` plus a **hardcoded 13-file
   code list**. `reports/` is 90 markdown files, **36 benchmark/eval-themed vs 13
   architecture-themed**, and **35 of 90 mention BugsInPy/QuixBugs/holdout**. So
   the searchable universe is dominated by phase/benchmark write-ups.
2. **Production code is weighted zero.** `core/`, `voice/`, `browser/`,
   `autonomy/`, `conversation/`, `memory/`, `desktop/`, `vision/` appear **0
   times** in the code-source list. They are not underweighted — they are
   **absent**. Meanwhile the secondary pipeline (`builder_core` indexer) ingests
   `benchmarks/holdout/pairs/bugsinpy_*/buggy.py` as category **`src`** — the same
   weight as `voice/realtime_tts.py`.

Measured: across 10 architecture questions, **49 of 50 cited sources were
`reports/*.md`; exactly 1 was a code file** (`flags.py`). Subsystem directories
appeared **0 times**. Ranking is pure keyword-overlap with a report-filename
phase boost — there is no notion of "this is a dataset, that is architecture."

---

## 1. The two `ask()` pipelines

| Pipeline | Entry | Corpus | Has an "index"? |
|---|---|---|---|
| **Project Intelligence** (primary repo-question answerer) | `project_intelligence.engine.answer_question` | `reports/*.md` + hardcoded `CODE_SOURCES` + 2 test files | No — globs live per query |
| **Builder Core** | `builder_core.cli ask` → `ask.answer` | `index.json` chunks from `indexer.build_index` (walks all files) | Yes — `.jarvis_builder/index.json` |

Both exhibit the failure, for different mechanical reasons (Sections 2, 6–8).

## 2. Task 1 — exact retrieval trace

### 2a. Project Intelligence (`answer_question`)
1. `routing` matches the builder question → `answer_question(text)`.
2. `gather_evidence(text)`:
   - `extract_keywords` (drop stop-words, len ≥ 3) and `extract_phase_numbers`.
   - **`search_reports`** — globs **every** `reports/*.md`, scores each passage by
     keyword overlap, adds **+0.5** if the filename contains the question's phase
     number. *(This is the dominant source.)*
   - **`search_code_modules`** — only if a keyword hits a tiny fixed set
     (`router, classifier, intent, tool, registry, handler, action, shadow, flag,
     audit, llm, phase, architecture, risk`) **or** a phase number is present; then
     iterates the **hardcoded `CODE_SOURCES`** (13 files: `README_ARCHITECTURE.md`,
     `README.md`, `brain/*`, `tools/*`, `actions/*`, `config.py`).
   - **`search_tests`** — 2 fixed test files, only if `test`/`phase` in keywords.
   - Architecture fallback: if architecture-like or no evidence, add
     `README_ARCHITECTURE.md`, `README.md`, `reports/phase73_100_roadmap.md`.
3. **Dedup by path** (keep the single highest-scoring passage per file), sort by
   score, **return top 5** (`MAX_FILES_IN_ANSWER = 5`).

The set of files that *can* be returned is therefore: all of `reports/*.md`, plus
13 hardcoded code files, plus 2 tests. **Nothing under `core/`, `voice/`,
`browser/`, `autonomy/`, `conversation/`, `memory/` can ever be cited.**

### 2b. Builder Core (`indexer.build_index` → `retrieval.search`)
- `build_index` walks the whole tree (skipping `.git`, `node_modules`, `venv`, …)
  and `_categorize`s each file into `readme | docs | src | test`. It extracts
  bounded "chunks" and stores them in `index.json`.
- `retrieval.search` scores chunks by keyword overlap with light category boosts
  (`readme 1.4`, `docs 1.3`, `src 1.0`, `test 0.7`).
- **Defect:** `_categorize` puts `benchmarks/holdout/pairs/bugsinpy_*/buggy.py`
  and `fixed.py` into **`src`** — identical weight to `core/types.py` and
  `voice/realtime_tts.py` (verified). There is **no `benchmark`/`dataset` category
  and no demotion.** `SKIP_DIRS` does not exclude `benchmarks/`. (Only `reports/`
  JSON dumps escape, because `.json` is not an indexed extension.)

## 3. Task 3 — measured source distribution (10 example questions)

Ran the real `project_intelligence.answer_question` on 10 architecture questions.
**50 cited sources total → 49 `reports/*.md`, 1 code file** (`flags.py`).
Subsystem code (`voice/ browser/ autonomy/ core/ conversation/ memory/`):
**0 occurrences.**

| Question | Cited sources (all `reports/*.md` unless noted) |
|---|---|
| How does the **voice** system work? | current_state_audit, jarvis_codebase_audit_phase73_100, master_audit, real_readiness_score, roadmap_to_90_percent |
| How does **browser** automation work? | agent_architecture_report, builder_ux_audit, consolidation_plan, current_state_audit, operator_production_readiness |
| How does **autonomy** work? | agent_architecture_report, builder_ux_audit, consolidation_plan, current_state_audit, jarvis_codebase_audit_phase73_100 |
| How is **memory** handled? | builder_ux_audit, consolidation_plan, jarvis_codebase_audit_phase73_100, llm_first_architecture, master_audit |
| **detector precision/recall?** | phase85_generalization_strategy, phase89_value_dataflow_taint, phase90_unified…engine, phase91_benchmark_engine_migration, phase93_interprocedural_architecture |
| How does **holdout** evaluation work? | phase79_llm_router…, phase84_external_benchmark_plan, phase85_generalization_strategy, phase88_architecture_review, phase89_value_dataflow_taint |

Two patterns: architecture-worded questions return **audit/meta reports**
(`master_audit`, `jarvis_codebase_audit_phase73_100` appear in almost every
answer); benchmark-worded questions return **100% benchmark phase reports**. In
neither case is the actual subsystem source ever consulted — for "how does voice
work," not one file under `voice/` is read.

## 4. Task 2 — why BugsInPy / benchmark content dominates

Four reinforcing causes:

1. **Corpus skew.** The searchable corpus is `reports/*.md`: 90 files, **36
   benchmark/eval-themed, 35 mentioning BugsInPy/QuixBugs/holdout**, vs 13
   architecture-themed. By volume, benchmark write-ups *are* the corpus.
2. **Keyword overlap favors benchmark prose.** Builder questions use words
   (`engine, pipeline, detector, validation, precision, repository, evidence`)
   that saturate the benchmark/phase reports, so those reports win the
   `hits/len(keywords)` score.
3. **The phase-number boost (+0.5)** drags the matching phase report — usually a
   benchmark report — to the top of any question mentioning a phase.
4. **Datasets indexed as production code (Builder Core path).** BugsInPy
   `buggy.py`/`fixed.py` are category `src`; being short, keyword-dense algorithm
   files, they out-compete sprawling real modules on per-chunk overlap.

## 5. Task 4 — ranking signals (enumerated)

| Signal | Where | Effect |
|---|---|---|
| `score_passage = hits/len(keywords)` | `ranking.score_passage` | pure keyword-overlap fraction |
| `+0.15` bonus if ≥3 keyword hits | `ranking.score_passage` | mild boost for dense matches |
| `+0.5` report-filename phase boost | `retrieval.search_reports` | **dominant** — pins the phase report |
| category boosts `readme 1.4 / docs 1.3 / src 1.0 / test 0.7` | `builder_core/retrieval` | weak, and **no benchmark/dataset class** |
| dedup by path, keep max passage | `gather_evidence` / retrieval | one passage per file |
| top-K cut (`5` PI / `6` BC) | `gather_evidence` / retrieval | small result set amplifies skew |

**Absent signals:** file role (production vs test vs benchmark vs dataset vs
generated), directory importance, doc-type (architecture doc vs phase log),
recency/centrality, or any penalty for evaluation/dataset content. Ranking is
**content-blind to what a file *is*.**

## 6. Task 5 — are README_ARCHITECTURE / README / core / voice / browser / autonomy underweighted?

| Target | In PI source set? | In BC index? | Net |
|---|---|---|---|
| `README_ARCHITECTURE.md` | yes (CODE_SOURCES + fallback) | yes (`readme`, ×1.4) | **present but drowned** — 2 README files vs 90 reports, no role priority |
| `README.md` | yes | yes | same |
| `core/` | **no (0 in CODE_SOURCES)** | yes, as `src` (×1.0) | **PI: zero. BC: equal to datasets** |
| `voice/` | **no** | yes, as `src` | same — invisible to PI |
| `browser/` | **no** | yes, as `src` | same |
| `autonomy/` | **no** | yes, as `src` | same |
| `conversation/`, `memory/`, `desktop/`, `vision/` | **no** | yes, as `src` | same |

So: `README_ARCHITECTURE`/`README` are *underweighted* (correct files, no
priority, outnumbered ~45:1 by reports). The subsystem directories are not
underweighted at all in PI — they are **structurally excluded** (zero weight); in
BC they are present but **indistinguishable from BugsInPy dataset code.**

## 7. Task 6 — proposed architecture-aware retrieval (design, not built)

- **Promote architecture anchors as a first-class tier:** `README_ARCHITECTURE.md`,
  `README.md`, top-level package docstrings, and each subsystem's entry module —
  retrieved and ranked above phase logs for architecture-class questions.
- **Index the code, not just the reports.** For "how does X work," the source of
  truth is `X/` — module docstrings, public class/function signatures, and
  `__init__` exports — not a report *about* X. Build retrieval over a **structural
  summary of each subsystem** (its modules, exported symbols, docstrings), so a
  voice question reaches `voice/`.
- **Question→region routing:** map subsystem nouns (voice, browser, autonomy,
  memory, router) to directories and bias retrieval toward that region's code +
  its README, before falling back to reports.
- **Separate "what is it" from "why was it built":** architecture questions →
  code + architecture docs; history questions ("why was phase N") → reports. Today
  both collapse onto `reports/*.md`.
- **Rank by role, then keywords** (see Section 8), not keywords alone.

## 8. Task 7 — proposed benchmark/dataset demotion (design, not built)

- **Exclude evaluation corpora from the answer index by default:**
  `builder_core/benchmarks/**`, `reports/**/<run>/**.json` dataset dumps, and any
  BugsInPy/QuixBugs/holdout pairs. They are *evaluation inputs*, not repository
  architecture, and must not be retrievable as "src."
- **Demote benchmark/phase reports for architecture questions:** keep them
  retrievable for *history* questions, but apply a strong negative weight (or a
  separate tier) when the question is "how does the system work."
- **Strip the blanket phase-filename `+0.5` boost** for architecture questions; it
  exists to serve "why was phase N," and it actively harms architecture retrieval.
- **Cap report share of an answer:** e.g. at most N of K cited sources may be
  `reports/*.md`, forcing code/architecture sources into the result set.

## 9. Task 8 — proposed repository-role classification (design, not built)

Replace the flat `readme/docs/src/test` categorization with an explicit **role**
per file, assigned deterministically from path + content:

| Role | Detection (deterministic) | Default retrieval weight |
|---|---|---|
| **production code** | code file outside test/benchmark/dataset/generated dirs | **high** |
| **tests** | `test_*`/`*_test`, `tests/`, `__tests__/`, `spec/` | low |
| **benchmarks** | `benchmarks/`, QuixBugs/holdout/BugsInPy paths, pair dirs (`buggy.py`/`fixed.py`) | **excluded from answers** (eval-only) |
| **datasets** | `*.json/*.jsonl` review/finding dumps, `*_run/` artifacts, manifests | **excluded** |
| **generated artifacts** | `__pycache__`, `dist/`, `build/`, vendored, lockfiles, `*.pyc` | excluded |
| **docs** | `README*`, `*.md`, `docs/` — sub-split: **architecture docs** vs **phase/history reports** | architecture-doc: high; phase/history: low (history-only) |

The role becomes the **primary ranking dimension**; keyword overlap is the
tie-breaker *within* a role. This single change is what separates "the voice
subsystem" (production code) from "a benchmark report that mentions voice" and
from "a BugsInPy pair."

## 10. Root-cause summary

The failure is **not** a ranking-tuning issue; it is a **corpus and role** issue:

1. **Wrong corpus** — answers are drawn from `reports/*.md` (benchmark-dominated)
   and a 13-file hardcoded list; the actual subsystems are not in the searchable
   set (PI) or are flattened to `src` (BC).
2. **No role model** — benchmarks, datasets, tests, generated artifacts, phase
   reports, architecture docs, and production code are all treated as equal
   keyword bags.
3. **Ranking blind to file identity** — keyword overlap + a phase-filename boost,
   with no demotion for evaluation/dataset content and no promotion for
   architecture sources.

Fixing it means (6) indexing and routing to the code/architecture, (7) demoting/
excluding evaluation corpora, and (8) classifying every file by role and ranking
role-first — **none of which is implemented here.** This report only explains the
failure.
