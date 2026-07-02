# DESIGN — Claude vs Claude+Atlas value benchmark (NOT YET RUN)

**Date:** 2026-06-20 · **Status:** design only — do not execute until approved.
**Purpose:** measure whether Atlas improves a coding agent's *real task performance*, not just retrieval. Designed so a human can score answers **blindly** and the result is defensible against "you optimized for a positive outcome."

---

## 1. The two arms (only one variable changes)

| | Arm A — Claude alone | Arm B — Claude + Atlas |
|---|---|---|
| Model | same model + version pinned | same |
| Temperature / max tokens / system prompt | identical | identical |
| Repo access | the repo tree + ability to open/grep files (a normal agent) | same **plus** the Atlas context pack / MCP tools for that task |
| Everything else | — | — |

Only the presence of Atlas differs. Arm A is **not** "no information" — it's a competent agent that can grep and read files (otherwise the comparison is a strawman). Atlas's job is to make that agent faster/better, so the baseline must be a real working agent.

## 2. Tasks, repos, ground truth (reuse the labeled set)

- **20 tasks** (scale to 50 after the pilot), 5 each across **requests, Atlas, langchain, home-assistant** — the same labeled tasks + grep-verified gold files/symbols from the retrieval benchmark (`atlas_value_benchmark.py`). Reusing them lets the objective sub-metrics (relevant files/symbols found) be scored automatically, and ties the two benchmarks together.
- Each task is a realistic request ("fix connection retry in the HTTP adapter"), not a trivia question.

## 3. What each run captures (per task × per arm)

A machine-readable record:
```
{ task_id, arm, model, repo,
  answer_markdown,            # the agent's full response
  files_referenced: [...],    # files the answer cites/edits
  symbols_referenced: [...],
  tests_suggested: [...],
  tokens_in, tokens_out, wall_clock_s, tool_calls }
```
Objective metrics computed automatically (no human needed): token usage, time, **file recall / symbol recall** vs gold, and a **fabrication count** (referenced files/symbols that do not exist in the repo — checked against the index).

## 4. Blind human scoring (the core requirement)

### 4a. Anonymization pipeline (mandatory before scoring)
Atlas leaves fingerprints (the `ATLAS_CONTEXT_PACK` block, "symbol slices", relevance scores). If a grader can tell which arm is which, the study is dead. So a **normalizer** runs before grading:
- Strip any Atlas-specific scaffolding from the *captured answer* (the agent's answer should already be prose; ensure no pasted pack headers, no "Atlas says", no relevance numbers).
- Reformat both arms' answers into one identical template (Summary / Files / Symbols / Plan / Tests / Risks).
- Assign a random `submission_id`; store the `submission_id → (task, arm)` key **separately**, released only after scoring.
- Randomize presentation order; counterbalance so arm A isn't always first.

### 4b. Rubric (pre-registered, anchored 0–5)
Graders score each anonymized answer on:

| Dimension | 0 | 3 | 5 |
|---|---|---|---|
| **Correctness** | wrong/irrelevant | partially correct, key idea present | correct + complete |
| **Relevant files** | none of the real files | some | identifies the right file(s) |
| **Relevant symbols** | none | some | names the right function/class |
| **Implementation plan** | none/hand-wavy | plausible steps | precise, ordered, actionable |
| **Tests suggested** | none | mentions testing | names the right tests / new cases |
| **Hallucination (reverse)** | invents files/APIs | minor imprecision | nothing fabricated |
| **Missed risks (reverse)** | ignores blast radius | notes some | flags the real downstream risks |

Plus a forced-choice: *"Which answer would you rather hand a junior engineer?"* (A/B/tie) — a simple, robust signal.

### 4c. Who grades (no self-grading)
- **≥2 independent human engineers** familiar with the repos, grading blind.
- Report **inter-rater agreement** (Cohen's κ or Krippendorff's α); if κ < 0.4 the rubric is too fuzzy — fix and re-grade.
- An LLM-judge may be used as a *third, secondary* signal **only if** it is a different model/provider than the arm-B generator, and never as the sole judge. The headline result is human.

## 5. Bias controls (so the result is trustworthy)
- **Pre-register** the rubric, tasks, gold labels, and analysis plan before any run (commit them, hash them).
- **Separate generation from scoring** — different people/sessions; graders never see the arm.
- **Same prompt template** for both arms except the Atlas context injection.
- **Counterbalanced order**, randomized submission ids.
- **Report failures** — tasks where Atlas hurt (e.g., misled the agent) must be listed, not hidden.
- **Pre-commit a null/negative result is publishable** — if Atlas doesn't help, say so.

## 6. Analysis
- Paired per-task deltas (B − A) per dimension; mean + 95% CI (bootstrap); paired sign test / Wilcoxon for significance.
- Effect size (Cliff's delta or Cohen's d) — "is it big enough to notice", not just p<0.05.
- Stratify by repo and by task_type (bug/feature/refactor/security…) to find where Atlas helps most/least.
- Cost view: quality delta **per 1k tokens** and **per minute** (Atlas should improve quality *and* reduce tokens/time, or the trade-off must be stated).

## 7. Pilot → scale gate
Run the **20-task pilot** first. Proceed to 50 only if: κ ≥ 0.4 (rubric reliable) AND the pilot shows a directional effect worth powering. Pre-compute the sample size needed for the observed pilot effect.

## 8. What this design deliberately avoids
- No self-grading by the generating model.
- No un-blinded comparison.
- No cherry-picked tasks (tasks fixed up front from the labeled set).
- No "Atlas-shaped" tasks chosen to flatter Atlas.

## 9. Honest limitation
This requires real model trials + human graders — it cannot be run inside this dev session credibly (the agent here would be judging itself). It is specified so the owner (or an independent evaluator) can execute it. The objective sub-metrics (files/symbols/tokens/time/fabrication) can be automated; **correctness, plan quality, and missed risks require the human blind grade.**
