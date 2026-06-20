# ATLAS VALUE VALIDATION BENCHMARK — Atlas vs naive repo search

**Date:** 2026-06-20 · 20 labeled tasks · 4 repos · harness `scripts/atlas_value_benchmark.py` · raw `atlas_value_benchmark_raw.json`
**Constraint honored:** no retrieval/ranking/MCP code was changed — this is measurement + analysis only.

---

## What this measures (and what it does NOT)

- **Ground truth is independent of Atlas:** for each task the gold file(s) = where the canonical symbol is **defined**, resolved by ripgrep (`class X`/`def X`), not by any retriever's output.
- **Baseline = "no Atlas" agent behavior:** ripgrep the repo for the task's keywords, rank files by match count, take top-8. This is what an agent does without Atlas.
- **Atlas:** `build_context_pack_from_state` → recommended files + symbol slices, over the same indexed-file universe.
- **NOT measured here:** end-to-end task *outcome* (correctness, plan quality, missed risks) — that needs blind model trials and is **designed, not run**, in `claude_vs_atlas_benchmark_design.md`. I will not claim outcome wins I haven't measured.

---

## Results — 8 metrics, Atlas vs grep

| Repo | Method | Hit@1 | Hit@3 | Hit@5 | File recall@5 | Symbol recall | Fabrications | Tokens | Retrieve time |
|---|---|---|---|---|---|---|---|---|---|
| **OVERALL (20)** | **Atlas** | **0.35** | **0.65** | **0.85** | **0.76** | **0.80** | **0** | **~2,750 / task** | 2.2s build* |
| | grep | 0.05 | 0.20 | 0.30 | 0.30 | n/a | n/a | ~110,862 (top-8 files) | 0.15s |
| requests (5) | Atlas | 0.40 | **1.00** | **1.00** | **1.00** | 1.00 | 0 | 2,561 | 0.06s |
| | grep | 0.00 | 0.40 | 0.80 | 0.80 | — | — | 84,630 | 0.02s |
| Atlas itself (5) | Atlas | 0.60 | 0.80 | **1.00** | **1.00** | 0.80 | 0 | 2,565 | 0.25s |
| | grep | 0.20 | 0.40 | 0.40 | 0.40 | — | — | 172,968 | 0.03s |
| langchain (5) | Atlas | 0.40 | 0.40 | 0.60 | 0.50 | 0.80 | 0 | 3,046 | 1.5s |
| | grep | 0.00 | 0.00 | 0.00 | 0.00 | — | — | 156,817 | 0.07s |
| home-assistant (5) | Atlas | 0.00 | 0.40 | 0.80 | 0.55 | 0.60 | 0 | 2,827 | 7.2s |
| | grep | 0.00 | 0.00 | 0.00 | 0.00 | — | — | 29,030 | 0.49s |

\* Atlas build time is per-task after a **one-time scan** (requests ~2s … home-assistant ~566s for 25,893 files). grep has no scan but pays it back on every query with 40× the tokens and near-zero precision on big repos. "Tokens" = Atlas pack size vs the total tokens an agent would read if it opened grep's top-8 files.

---

## Atlas Advantage Report

### 1. Is Atlas measurably better than a naive repository search?
**Yes — unambiguously.** Across 20 independently-labeled tasks Atlas beats grep on every retrieval metric: Hit@3 0.65 vs 0.20, Hit@5 0.85 vs 0.30, file recall 0.76 vs 0.30, with **0 fabrications** and **~40× fewer tokens**. On the two large repos (langchain, home-assistant) grep scored **0** on Hit@1/@3/@5 — naive keyword search simply does not find the implementation there.

### 2. By how much?
- **Hit@3: 3.3×** (0.65 vs 0.20). **Hit@5: 2.8×** (0.85 vs 0.30). **File recall: 2.5×** (0.76 vs 0.30).
- **Tokens: ~40× fewer** (2,750 vs 110,862). The agent reads a 2.7k-token pack instead of opening ~111k tokens of mostly-wrong files.
- **Large repos: effectively ∞** — grep's Hit@k = 0 on langchain and home-assistant; Atlas got the right file into the top-5 on 60–80% of those.
- **Fabrication: 0%** for Atlas (every referenced file/symbol exists in the repo, verified).

### 3. Where does Atlas win?
- **Large / messy repos.** grep drowns in noise: its top hits were `tests/`, `docs/`, and Home-Assistant snapshot `.ambr` files — never the implementation. Atlas surfaces the real module.
- **Token efficiency** (~40×) and **symbol recall** (0.80) — it names the right function/class, not just the file.
- **Top-3/top-5 precision** and **zero fabrication** — safe to hand to an agent.

### 4. Where does Atlas lose?
Honest weaknesses (from the raw data):
- **Hit@1 is only 0.35** — Atlas reliably puts the right file in the top-3/5 but often at **rank 2**, not rank 1 (e.g., requests `models.py`, Atlas `context_pack.py`).
- **3 hard misses (gold not in top-5):** langchain `llms.py` (BaseLLM) and `prompts/base.py` (BasePromptTemplate), and home-assistant `core.py` (EventBus). Pattern: deeply-nested core modules and 5k-line "god files" in huge monorepos.
- **home-assistant Hit@1 = 0** — among 25,893 files the canonical component competes with thousands of look-alikes; Atlas lands it in top-5 (80%) but rarely first.
- **Latency / scan cost:** grep answers in ~0.15s; Atlas's per-task build is sub-second on normal repos but the one-time scan is heavy on huge repos (HA 566s).

### 5. Would a professional engineer notice the improvement?
**Yes — clearly, on real-world repos.** On a 25k-file codebase, grep hands back test snapshots and docs and the engineer finds nothing useful; Atlas returns the right file in the top-5 ~80% of the time with 40× less to read. On small repos (requests) the gap is smaller but still real (grep ranks `tests/` and `docs/` above `adapters.py`; Atlas puts the implementation in the top-3 every time). The token reduction alone (2.7k vs 111k) is a difference any engineer feels immediately.

---

## Labeling caveats (disclosed, not hidden)
- Gold = grep for `class/def <symbol>`. For **generic names** (`Entity`, `EventBus`, `InMemoryVectorStore`) this also matched test fixtures (e.g., `tests/pylint/...`, `test_indexing.py`), inflating some gold sets with test files Atlas correctly de-prioritized — this makes Atlas's recall look *lower* than its real implementation-finding ability in those cases.
- Recall/Hit are over the top-8 (Hit@k for k≤5); a larger k would raise Atlas's recall further.
- 5 tasks/repo is a pilot; numbers have wide CIs. Scale to 50 (5×) for tighter intervals.

---

## VERDICT: **Very useful** (for the retrieval/context layer)

Atlas is **measurably and substantially better** than naive repository search — 2.5–3.3× hit/recall, ~40× fewer tokens, zero fabrication, and the decisive advantage that **grep is essentially useless on large real-world repos where Atlas still works**. A professional engineer would notice.

It is **not yet** "mission critical" on the evidence in hand, for two honest reasons: (1) this measures retrieval, not end-to-end task outcomes — the Claude-vs-Claude+Atlas A/B (`claude_vs_atlas_benchmark_design.md`) is designed but unrun; (2) Hit@1 (0.35) and large-repo recall have clear, nameable gaps. Close those and prove the outcome A/B, and the case for "mission critical on large codebases" is within reach.

**Next:** run the blind Claude-vs-Claude+Atlas benchmark (design ready) to convert "better retrieval" into "better answers." Do not start until approved.
