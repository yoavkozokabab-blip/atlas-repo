# Phase 104E — End-to-End Benchmark Protocol

**Status:** Design only. No production code changes, no benchmark task changes.
**Date:** 2026-06-01
**Purpose:** The final, reproducible protocol to prove **Codex Alone vs JARVIS
Compact + Codex** (and later **Claude Alone vs JARVIS Compact + Claude**) using
manual subscription runs — no API keys.

**Inputs in hand:** Phase 103 framework (`codex_alone` / `jarvis_plus_codex`,
`RunLog`, `ManualScore`, summary); 104A token accounting; 104B context profiling;
104C compact packets (**verbose 9,839 → compact 4,692 tokens, 52.3% reduction**);
104D cached context generation (planned). Corpus: **21 tasks, 8 task types, repo
`local_jarvis`** (pinned commit).

---

## 0. The one thing this protocol must get right

Codex/Claude run **manually** and the UI does **not** expose exact tool-read
tokens. So the protocol's job is to make the comparison **fair and honest under
estimation**: the same estimation method applied to both arms, fresh sessions,
blinded scoring, quality measured before cost, and every token number labelled an
estimate. A cheaper-but-wrong answer must **lose**.

---

## 1. Fair token measurement (Q1)

**Metric: "input context to answer" = prompt tokens + tokens of everything the
model READ to produce the answer.** Estimated identically for both arms (chars/4),
so the *relative* comparison is fair even though absolutes are approximate.

| Arm | Prompt tokens | Read tokens | How measured |
|---|---|---|---|
| `codex_alone` | small (task only) | **large** (files/grep it opens) | record a **read manifest**: every file the tool opened + line ranges; estimate via chars/4 of those ranges |
| `jarvis_plus_codex` | **compact packet** (~4,692) | small (few targeted reads) | prompt is known (`estimated_count`); add any extra files read, same method |

Rules:
1. **Read manifest is mandatory.** Most tools show a tool-call/file log even without token counts — copy the list of files (and ranges) read into the run-log `notes`. Estimate tokens from those bytes (chars/4).
2. **Same estimator both arms** (`tokens.estimate_tokens`, chars/4). Never compare a UI number for one arm against an estimate for the other.
3. **UI override when available.** If the tool *does* expose a context/prompt token count, record it as `estimated_input_tokens` and set the manifest note to "UI-exact".
4. **Output tokens** = chars/4 of the saved answer (auto via `estimated_count`).
5. **Label everything an estimate** (`token_numbers_are_estimates: true`, already in `RunLog`). Report medians, not single runs, to dampen estimation noise.
6. **Do not cap reads.** `codex_alone` must read what it needs — that *is* the cost JARVIS removes. Record it; don't suppress it.

**Why this is fair:** the JARVIS thesis is "answer with less context." The honest
measure is total context consumed to reach the answer, counted the same way for
both arms. Prompt-size-only comparison is *rejected* (it flatters `codex_alone`,
whose reads aren't in its prompt).

---

## 2. Contamination controls (Q2)

| Control | Rule |
|---|---|
| **Fresh session per (task × arm)** | one task, one arm, one brand-new chat; close it before the next. Never run arm A then arm B in the same conversation. |
| **Memory off** | disable tool/account memory (Codex/Cursor/ChatGPT memory features) for the benchmark workspace. |
| **No leakage** | the model never sees other tasks' prompts, expected answers, scoring rubric, or the other arm's answer. |
| **Pinned repo** | both arms use the same pinned commit SHA (read-only). Record the SHA. |
| **Counterbalanced order** | alternate which arm runs first across tasks (A-first on odd tasks, B-first on even) to cancel operator learning; still fresh sessions. |
| **Blinded scoring** | the reviewer scores answers with the arm label hidden (rename files `taskid_X.txt` / `taskid_Y.txt`); un-blind only after scores are recorded. |
| **One operator config** | same tool, same model version, same machine for a given run set; record them. |
| **Audit fields** | record `session_id` (or a sequential session counter) per run to prove isolation. |

---

## 3. Exact manual workflow

Per **(task × arm)**:

1. **Generate** the package (offline): `cli generate` → `reports/benchmarks/<run_id>/<task_id>/{codex_alone,jarvis_plus_codex}.prompt.md` (+ run-log/score templates). The `jarvis_plus_codex` prompt already embeds the **compact** JARVIS packet.
2. **Open a fresh session** in the tool (memory off).
3. **Paste** the arm's prompt. Start the timer at first send.
4. Let the model answer (it may read files for `codex_alone`). **Stop the timer** at the final answer.
5. **Save** the answer to `answers/<task_id>.<mode>.txt`.
6. **Record the run** (`cli record-run` or edit `run_log.<mode>.json`): model/tool + version, start/end time, elapsed, `estimated_input_tokens` (prompt + read manifest), output tokens, the **read manifest** in `notes`, `session_id`.
7. **Close the session.** Next run = new session.
8. After all runs for a task, **blinded-score** both answers (`cli score` / edit `score.<mode>.json`): the four 0–5 axes + `task_success` + TP/FP/FN.
9. When the run set is complete: `cli summary --run-dir <run_dir>` → `summary.md` + `summary.json`.

Operator order for a task: counterbalanced arm-first; both arms scored together,
blinded.

---

## 4. Scoring rubric (Q3 dimensions live here)

Per answer, a **blinded** reviewer fills `ManualScore` (0–5 each unless noted):

| Axis | Meaning |
|---|---|
| `correctness` | Is the answer factually right vs the expected answer / repo ground truth? |
| `evidence_quality` | Are cited files/paths **real and on-point**? (separate from correctness) |
| `completeness` | Does it cover what the task asked? |
| `hallucination_risk` | 0 = no fabrication; 5 = invented paths/claims (**lower is better**) |
| `task_success` | boolean: would a developer accept this answer as done? |
| `true/false/false-neg` | for defect tasks: TP/FP/FN for bug-finding precision/recall |

`total_score` (0–100) = `(correctness + evidence_quality + completeness + (5 −
hallucination_risk)) / 20 × 100` — the existing `ManualScore.total_score`. **A
fabricated path forces `hallucination_risk` high and caps the score** (honesty gate).

Two reviewers where possible; record both; adjudicate disagreements > 1 point.

---

## 5. Timing rules

- **Elapsed = model wall-clock**: from first prompt send to final answer. Excludes
  human scoring and note-taking.
- For `codex_alone`, elapsed **includes** the model's own file-reading/exploration
  (that is real latency the developer experiences).
- **Context-generation time is measured separately** (§8): the JARVIS-side cost to
  build the compact packet (index/graph). It is *not* added to the model elapsed,
  because in production the packet is precomputed/cached. Report it as its own
  metric (the 104D caching axis).
- Record `start_time`/`end_time` (ISO) and `elapsed_seconds`; if the UI only shows
  duration, record that as `elapsed_seconds` and leave timestamps blank.
- Use medians across the run; single-run timings are noisy.

---

## 6. Separating the four dimensions (Q7)

Reported as **separate columns; never merged into one number**:

| Dimension | Source | Aggregate |
|---|---|---|
| **Quality improvement** | `total_score` delta + `task_success` rate | mean delta (points), success-rate delta |
| **Token reduction** | total input tokens (prompt + reads) | **median** % reduction (A→B) |
| **Speedup** | `elapsed_seconds` ratio A/B | median speedup × |
| **Evidence quality** | `evidence_quality` axis + `hallucination_risk` | mean evidence score; count of fabrications (must be 0) |

The summary already emits `average_estimated_token_reduction_percent`,
`average_speedup`, `average_quality_delta_points`, and per-mode
`bug_finding_accuracy` — keep them distinct. **Dimension-separation rule:** a token
or speed win is never reported without its quality delta beside it.

---

## 7. Win / loss / tie (Q6)

Quality first, then cost. Epsilons: quality `ε_q = 3` points (of 100); token margin
`ε_t = 10%` relative.

```
For each task (A = codex_alone, B = jarvis_plus_codex):
  if total_score(B) < total_score(A) − ε_q              -> LOSS   (quality regression; cost irrelevant)
  elif total_score(B) > total_score(A) + ε_q            -> WIN    (strictly better answer)
  else  (quality within ε_q, i.e. non-inferior):
      if tokens(B) ≤ (1 − ε_t)·tokens(A)                -> WIN    (same quality, ≥10% cheaper)
      elif tokens(B) ≥ (1 + ε_t)·tokens(A)              -> LOSS   (same quality, ≥10% pricier)
      else                                              -> TIE
  Hard override: any FALSE confirmation (FP on a confirmed_defect task that A got right) -> LOSS
```

Primacy: a quality regression past `ε_q` is a LOSS regardless of token savings.

---

## 8. Compact + caching vs prose / no-cache (Q8)

Two **independent** axes — do not conflate:

| Axis | Controls | Metric it moves | How to compare |
|---|---|---|---|
| **Context format** (prose ↔ compact, 104C) | the embedded packet | **tokens** (9,839 → 4,692) | A/B the two formats on the same tasks; tokens differ, model run identical |
| **Caching** (no-cache ↔ cached, 104D) | how the packet is *generated* | **context-generation latency** (not tokens) | micro-benchmark of packet build time; identical packet bytes |

Rules:
1. **Primary model runs use COMPACT** (the production format) vs `codex_alone`.
2. **Token reduction is attributed to format, not cache** — caching produces the
   *same* bytes, so it cannot change token counts. Verify `compact == cached
   bytes` so caching is provably token-neutral.
3. **Caching is benchmarked separately** as packet-generation wall-clock
   (no-cache vs cached), reported as a JARVIS-side latency metric — *not* added to
   model elapsed (§5).
4. **One prose-vs-compact A/B** on the 5 pilot tasks confirms the 52.3% token cut
   holds **and** quality does not drop (compact `total_score` ≥ prose within `ε_q`).
   This is the evidence that compaction preserved answer quality.

So: format axis → token claim; cache axis → speed-of-generation claim; both kept
separate from the model-run quality/latency claim.

---

## 9. Pilot benchmark plan — 5 tasks first (Q3 selection)

Run the **5-task pilot** to validate the protocol (estimation, isolation, scoring)
before the full set. Chosen to span 5 of 8 task types, include the two
highest-JARVIS-advantage tasks, and a bug-finding task (different axis + a control
where JARVIS must *not* hallucinate):

| Pilot task | Type | Why |
|---|---|---|
| `risk01_ranking` | architectural_risk | biggest packet compression (808→300); strong ground truth (config #1) |
| `impact01_config` | impact_analysis | high advantage; ground truth (~212 importers) |
| `dep01_engine_edges` | dependency_analysis | crisp, checkable edges |
| `ru01_subsystems` | repository_understanding | foundational subsystem map |
| `defect01_wrong_operator` | confirmed_defect_detection | exercises TP/FP/FN + the no-fabrication gate (control) |

Pilot size: 5 tasks × 2 arms = **10 model runs** + the prose-vs-compact A/B on
these 5 (§8.4). Pilot **passes** if: protocol executes cleanly (fresh sessions,
read manifests captured, blinded scores recorded), JARVIS has **0 quality
regressions** and **0 fabrications**, and the median token reduction is materially
positive. Fix protocol issues here, then proceed.

---

## 10. Full benchmark plan — 21 tasks (Q4)

After the pilot, run the **full 21-task corpus** (all 8 task types):

- 21 tasks × 2 arms = **42 model runs**, fresh sessions, counterbalanced order.
- Same workflow (§3), metadata (§11), scoring (§4).
- **Two operators** repeat the full run independently where feasible (inter-operator
  agreement strengthens external credibility).
- Plus the **caching micro-benchmark** (§8.3) once, and the **prose-vs-compact
  A/B** carried from the pilot (optionally extended to a few full-set tasks).
- Aggregate via `cli summary`: per-mode token/latency/quality/bug-accuracy,
  win/loss/tie, per-task breakdown.

Task-type coverage (for reporting by family): RU 3, dependency 3, impact 3,
architectural_risk 3, contract 2, verification 2, confirmed_defect 3, fix_planning 2.

---

## 11. Metadata that must be manually recorded (Q5)

Per run (extends `RunLog` via `notes`; nothing schema-breaking):

```
task_id, mode/arm, session_id (isolation proof)
model_tool_used + version, operator
repo_commit_sha, context_format (compact|prose), cache (hit|miss|none)
start_time, end_time, elapsed_seconds
estimated_input_tokens  (+ read_manifest: [file:lines, ...] in notes; or "UI-exact")
estimated_output_tokens, token_numbers_are_estimates=true
raw_answer_path, notes
```

Per answer (`ManualScore`): correctness, evidence_quality, completeness,
hallucination_risk, task_success, true/false/false-neg, reviewer id, blinded=true.

Run-level (manifest): run_id, framework/schema versions, task set hash, operator(s),
date, tool versions.

---

## 12. Go / no-go thresholds (Q9: minimum external-strength result)

**GO (externally showable)** — all must hold on the **full 21-task** run:

| Gate | Threshold |
|---|---|
| **No quality regression** | `jarvis_plus_codex` `total_score ≥ codex_alone` on **every** task within `ε_q` (0 LOSS by quality) |
| **No new false confirmations** | 0 added FP on confirmed_defect/verification tasks (precision not worse) |
| **No fabrications** | 0 hallucinated paths in the JARVIS arm |
| **Token reduction** | **median total-input-token reduction ≥ 40%** at equal-or-better quality |
| **Win rate** | JARVIS WIN on **≥ 60%** of tasks; LOSS on **0** by quality |
| **Coverage** | wins span **≥ 4** of the 8 task types (not one family) |
| **Reproducibility** | pinned SHA, fresh sessions, ≥ 2 reviewers (or 2 operators) agree; JARVIS packet deterministic |

**NO-GO / HOLD** if any quality regression, any fabrication/false confirmation, or
median token reduction < 40%. (A strong *internal* result with token reduction
30–40% and 0 regressions is a "promising, not yet external" hold.)

The defensible external sentence this earns:
> "Across 21 real developer tasks on a pinned repo, JARVIS Compact + Codex matched
> or beat Codex Alone on answer quality on every task, with a median ~XX% reduction
> in input tokens, zero quality regressions, and zero new false bug confirmations
> (token numbers are estimates; method published)."

---

## 13. Example result table (illustrative — numbers are placeholders)

Per-task (excerpt):

| Task | Type | A score | B score | Quality Δ | A tokens | B tokens | Token Δ | Speedup | Winner |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| risk01_ranking | arch_risk | 70 | 90 | +20 | 12,400 | 3,300 | −73% | 1.8× | B (win) |
| impact01_config | impact | 75 | 90 | +15 | 11,900 | 3,100 | −74% | 1.9× | B (win) |
| dep01_engine_edges | dependency | 80 | 85 | +5 | 6,400 | 2,600 | −59% | 1.4× | B (win) |
| ru01_subsystems | repo_under | 85 | 85 | 0 | 7,000 | 3,000 | −57% | 1.3× | B (win, cheaper) |
| defect01_wrong_operator | defect | 90 | 90 | 0 | 2,800 | 2,500 | −11% | 1.0× | tie |

Aggregate (illustrative):

| Metric | Codex Alone | JARVIS Compact + Codex |
|---|---:|---:|
| Avg total_score | 78 | 88 |
| Task success rate | 0.81 | 0.95 |
| Median input tokens | 8,900 | 3,000 |
| Median token reduction | — | **~62%** |
| Median speedup | — | 1.5× |
| Bug-finding precision | 1.0 | 1.0 (no new FP) |
| **Win / Loss / Tie** | — | **17 / 0 / 4** |

Caching micro-benchmark (separate): compact packet generation — no-cache `Xs` →
cached `Ys` (token-neutral; identical bytes).

---

## 14. Constraints honored

- No production code change, no benchmark-task change (the 21-task corpus is frozen).
- Tokens labelled estimates; same method both arms; medians reported.
- Quality measured **before** cost; cheaper-but-wrong loses; fabrication caps the score.
- Uncertainty preserved (read manifests, estimate labels, separate dimensions).
- Format (token) and cache (speed) axes kept separate; compact==cached bytes verified.

---

## 15. Bottom line

Run **5 pilot tasks** to harden the protocol (fresh sessions, read-manifest token
estimation, blinded scoring, prose-vs-compact A/B), then the **full 21 tasks ×
2 arms** with two operators. Measure four **separate** dimensions, decide
win/loss/tie with quality first, and gate the external claim on **zero quality
regressions, zero fabrications, ≥40% median token reduction, ≥60% win rate across
≥4 task types**. Caching is benchmarked separately as generation latency, not
tokens. That produces an honest, reproducible "matched-or-better quality at large
token reduction" result fit to show externally.
