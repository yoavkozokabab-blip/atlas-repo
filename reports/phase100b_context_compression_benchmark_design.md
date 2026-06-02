# Phase 100B — Context Compression Benchmark Design

**Status:** Design only. No code.
**Date:** 2026-05-31
**Goal:** Define the definitive, repeatable **Claude vs Claude+JARVIS** benchmark
that measures whether JARVIS's deterministic repository intelligence lets an agent
answer real developer questions with **less context** at **equal-or-better answer
quality**.
**Subject under test:** JARVIS Builder Core intelligence (RU-2/RU-3 `ask`, depgraph
94A, impact 94B) as a context-compression layer for a coding agent.

---

## 0. Hypothesis and what is measured

**Claim to test:**

> For architecture, impact, bug, and code-understanding questions about a real
> repository, **Claude + JARVIS** reaches an answer of **equal or higher quality**
> than **Claude alone**, while consuming **substantially fewer input tokens, less
> wall-clock time, and lower cost** — because JARVIS returns small, structured,
> evidence-backed answers instead of forcing the agent to read raw code into
> context.

**Context compression** = the reduction in input tokens / peak context occupancy
needed to reach a correct answer. The benchmark is only meaningful if **answer
quality is held constant or improved** — a cheaper *wrong* answer is the worst
outcome and is scored as a failure (§4, §5).

**The independent variable is tool availability — nothing else.** Same model, same
prompts, same repo snapshot, same scaffold; only the toolset differs between arms.

---

## 1. The two arms

| | **Arm A — Claude alone (baseline)** | **Arm B — Claude + JARVIS** |
|---|---|---|
| Model | Fixed model + version (record exact id) | identical |
| Tools | Generic code tools only: `read_file`, `grep`, `glob`, `list_dir` | Same generic tools **plus** JARVIS: `ask`, `graph summary`, `impact-file`, `impact-module` (Builder Core CLI/MCP) |
| Repo | Pinned commit snapshot | identical snapshot; JARVIS index/depgraph prebuilt at that commit |
| Scaffold | Fixed agent loop, max turns, temperature 0 | identical |
| Instruction | "Answer using the repository." | "Answer using the repository; JARVIS tools are available." |

Arm B is expected to substitute many raw-file reads (Arm A) with a few compact
JARVIS queries. Everything else is held identical so the measured delta is
attributable to JARVIS.

---

## 2. Task suite (26 real developer tasks)

26 preregistered tasks across the four required categories, grounded in the real
`local_jarvis` repo (RU-2 measured: 4,060 files; subsystems `voice`(133),
`actions`(65), `builder_core`(47), `brain`, `core`, `conversation`, …). Each task
has a **preregistered reference answer** and a **ground-truth anchor** (a
deterministic fact the answer must contain), authored before any arm is run.

### 2.1 Architecture questions (8) — JARVIS path: `ask` (RU-2/RU-3)

| ID | Task | JARVIS tool (Arm B) | Ground-truth anchor |
|---|---|---|---|
| A1 | What are the most important production subsystems? | `ask` (subsystem) | voice/actions/builder_core/brain/core present; no benchmark dirs |
| A2 | Which directories have the highest concentration of production code? | `ask` (production_layout) | ranked by `role_counts.production_code` |
| A3 | Which subsystems are most central to the architecture? | `ask` (subsystem centrality) | high import fan-in subsystem (e.g. `core`) |
| A4 | What happens when a user speaks a voice command? | `ask` (execution_path) | voice/voice_loop → core path; cites `voice/` |
| A5 | What are the entry points of the system? | `ask` (entrypoint) | `main.py`/`cli.py`/`voice_loop.py` |
| A6 | List the top directories and their purpose. | `ask` (architecture) | top-level subsystem map |
| A7 | How is the bug-intelligence engine structured? | `ask` + targeted read | `builder_core/bug_intelligence/engine.py` agents pipeline |
| A8 | Which folders are production vs tests vs benchmarks? | `ask` (role grouping) | RU-2 roles; benchmark dirs flagged |

### 2.2 Impact analysis (6) — JARVIS path: `impact-file` / `impact-module` (94B)

| ID | Task | JARVIS tool | Ground-truth anchor |
|---|---|---|---|
| I1 | What modules import `builder_core/bug_intelligence/engine.py`? | `impact-file` | reverse `imports` set |
| I2 | What breaks if the signature of `analyze_source` changes? | `impact-file` (callers) | resolved caller set + unresolved-edge caveat |
| I3 | Which modules have the highest incoming-dependency count? | `graph summary` / `ask` (dependency) | depgraph `top_imported_modules` |
| I4 | What is the blast radius of editing `core/app.py`? | `impact-file` (transitive) | transitive closure + degraded/unknown honesty |
| I5 | Are there import cycles, and where? | `graph summary` | depgraph `import_cycles` |
| I6 | What depends on the `voice` subsystem? | `impact-module` | subsystem reverse deps |

### 2.3 Bug investigation (6) — JARVIS path: `ask` (risk/bug) + engine

| ID | Task | JARVIS tool | Ground-truth anchor |
|---|---|---|---|
| B1 | What are the riskiest files in the repo? | `ask` (risk) / `risk-report` | churn/coverage/size risk signals |
| B2 | Are there logic-bug review leads in `<file X>`? | `analyze <file>` | engine findings (AST signals, not proof) |
| B3 | Find inconsistent-return review leads in a given module. | `analyze` | `inconsistent_return` advisory leads |
| B4 | Does `<function Y>` have an obvious off-by-one / boundary issue? | `analyze` | detector output for that file |
| B5 | Which files lack test coverage and are large (risk)? | `ask` (risk) | untested + large signal |
| B6 | Is `<security-relevant file>` exposed to injection review leads? | `security` | security findings (review leads) |

### 2.4 Code understanding (6) — incl. controls & traps

| ID | Task | JARVIS tool | Role |
|---|---|---|---|
| C1 | What does `indexer.build_index` return (shape)? | targeted read (JARVIS gives the file fast) | normal |
| C2 | Explain the wakeword → command flow. | `ask` + read | normal |
| C3 | Summarize the responsibilities of `brain/router.py`. | `ask` + read | normal |
| C4 | **Control:** Explain this single 30-line function's logic (file given). | none special (both read the file) | JARVIS must **not lose** here |
| C5 | **Control:** Fix a typo's blast radius in a leaf util used nowhere. | both | JARVIS must not over-claim |
| C6 | **Trap:** What calls `self.dispatch()` (a dynamic method call)? | `impact` returns *unresolved* | tests JARVIS **honesty** (unknown beats guessing) — quality credit for correctly saying "unresolved", not penalty |

**Suite balance:** 20 JARVIS-advantaged tasks + 2 controls + 1 trap (+ extend to
30 by adding 2 architecture, 1 impact, 1 bug if needed). Controls and the trap
prevent a cherry-picked result: JARVIS must not *lose* on control tasks and must
not *fabricate* on the trap.

---

## 3. Metrics (exact definitions)

Captured per **(task × arm × trial)**:

| Metric | Definition |
|---|---|
| **Input tokens** | Sum of all tokens fed to the model across the task's turns (system + task prompt + every tool result read into context + prior-turn history). The primary compression metric. |
| **Output tokens** | Model-generated tokens across the task. |
| **Total tokens** | input + output. |
| **Peak context size** | Maximum context-window occupancy (tokens) at any single turn — how "full" the window got. |
| **Wall-clock time** | End-to-end seconds from task start to final answer (includes JARVIS query latency for Arm B). |
| **Cost (USD)** | `input_tokens × in_price + output_tokens × out_price`, using a **frozen, recorded price table** for the exact model. |
| **Tool calls** | Count by type (`read`/`grep`/`glob` vs `ask`/`graph`/`impact`). Shows *how* compression happens. |
| **Answer quality** | 0–4 rubric (§4), blinded dual-scored. |

**Index-build accounting (Arm B):** the one-time `init` (index + depgraph) cost is
recorded **separately** and reported two ways: (a) **per-task steady-state**
(excluded — amortized across many queries), and (b) **amortized** over the suite,
with the **break-even query count** at which Arm B's cumulative tokens/cost drop
below Arm A. Honesty: a single query may not repay the index build; the steady-state
per-query win and the break-even point are both reported.

---

## 4. Scoring rubric

### 4.1 Answer-quality rubric (0–4, per task)

| Score | Meaning |
|---:|---|
| **4** | Fully correct, complete, and **evidence-backed** (cites real files/paths that exist). |
| **3** | Correct with minor omissions; no errors. |
| **2** | Partially correct; missing a material part. |
| **1** | Mostly wrong or misleading. |
| **0** | Wrong, or **fabricated** (hallucinated path / nonexistent subsystem / invented dependency). |

Rules:
- **Hallucination floor:** any fabricated source path, subsystem, or dependency edge
  → automatic **0**, regardless of fluency (mirrors JARVIS's "unknown beats
  guessing"). Saying "unresolved / I couldn't determine" **correctly** (trap C6) is
  **not** a penalty — score on whether that is the right answer.
- **Evidence requirement:** for architecture/impact tasks, an answer without a
  verifiable source citation caps at **2**.
- **Blinded dual scoring:** two reviewers, blinded to arm; disagreements adjudicated;
  inter-rater agreement reported.

### 4.2 Derived efficiency scores (per task, then aggregated)

| Score | Formula |
|---|---|
| **Compression ratio** | `median total_tokens(A) / median total_tokens(B)` (higher = more compression) |
| **Context reduction** | `median peak_context(A) / median peak_context(B)` |
| **Cost reduction** | `1 − cost(B)/cost(A)` |
| **Time reduction** | `1 − wall_clock(B)/wall_clock(A)` |
| **Quality delta** | `mean quality(B) − mean quality(A)` |
| **Quality-per-1k-tokens** | `quality / (total_tokens/1000)` — the headline efficiency number |

**Separation rule:** efficiency scores are reported **only alongside** the quality
delta. A compression number is never reported without its quality gate (§5).

---

## 5. Success and fail thresholds

Evaluated over the full 26-task suite (median per task, then aggregated).

### 5.1 SUCCESS (JARVIS is a net win) — all must hold
| Gate | Threshold |
|---|---|
| **Quality non-inferiority** | `mean quality(B) ≥ mean quality(A) − 0.2` **and** `mean quality(B) ≥ 3.0` |
| **No confident fabrication** | **0** tasks where B scores 0 (hallucination) while A scored ≥ 3 |
| **Token compression** | suite-median compression ratio **≥ 2.0×** (B ≤ 50% of A's input tokens) |
| **Cost reduction** | **≥ 40%** |
| **Category strength** | architecture + impact categories show compression **≥ 3.0×** |
| **Control integrity** | on control tasks (C4, C5), `quality(B) ≥ quality(A) − 0.2` and no large token penalty (B ≤ 1.25× A tokens) |
| **Trap honesty** | on C6, B correctly reports the call as unresolved (quality ≥ 3); does **not** fabricate a callee |

### 5.2 FAIL (JARVIS not justified) — any one
| Condition |
|---|
| `mean quality(B) < mean quality(A) − 0.5` (compression bought with accuracy loss) |
| Any category where B **fabricates** an answer A got right |
| Suite-median compression ratio **< 1.3×** (not worth integrating) |
| Arm B is **slower with no token/cost benefit** (`wall_clock(B) > wall_clock(A)` and compression < 1.3×) |
| Reproducibility failure: medians not stable across the required reruns (§6) |

### 5.3 PARTIAL
Anything between SUCCESS and FAIL (e.g., strong compression but quality delta in
`[−0.5, −0.2)`): report as **conditional** with the specific shortfall named; do not
round up to SUCCESS.

**Primacy rule:** quality dominates. A run with spectacular compression but a
quality regression past the FAIL bar is a FAIL, full stop.

---

## 6. Repeatable protocol

### 6.1 Freeze (record in the run manifest)
- Model id + version; agent scaffold version; tool definitions per arm.
- Repo commit SHA; JARVIS index + depgraph hash built at that SHA.
- Frozen price table (in/out USD per token).
- Task suite hash; preregistered reference-answer hash; rubric version.
- Temperature 0; fixed max-turns and max-tool-calls budget (identical per arm).

### 6.2 Run
1. Build JARVIS index/depgraph once at the pinned SHA (record its cost separately).
2. For each task × arm × **N = 3 trials**: run the agent to a final answer; capture
   all §3 metrics per trial.
3. Use **median** across trials per (task, arm) for token/time/cost (LLM agents are
   not byte-deterministic even at temp 0 — variance is reported via IQR).
4. **Blinded scoring:** collect final answers stripped of arm identity; two reviewers
   score 0–4; adjudicate; record inter-rater agreement.

### 6.3 Anti-gaming controls
- Tasks + reference answers **preregistered** before any run; no task added/removed
  after seeing results.
- **Control tasks** (no JARVIS advantage) and a **trap task** (honesty) included so a
  win cannot be cherry-picked.
- Same generic tools available to **both** arms (Arm B only *adds* JARVIS) — Arm A is
  never handicapped.
- Identical turn/tool budgets; identical repo snapshot.
- Reviewers blinded to arm; price table and model frozen across the whole run.

### 6.4 Reporting template
Per task: medians + IQR for tokens/context/time/cost, tool-call breakdown, quality
(A vs B), compression ratio. Aggregate: the §4.2 derived scores, the §5 verdict
(SUCCESS / PARTIAL / FAIL) with each gate's pass/fail, the break-even query count,
and the index-build cost. Publish raw per-trial data for independent recomputation.

### 6.5 Repeatability
Because the manifest pins model, repo SHA, index hash, price table, task hash, and
rubric, the benchmark can be re-run on a new model or a new repo by swapping those
pins. Re-running the **same** manifest must reproduce the verdict (medians stable
within reported IQR across ≥2 independent executions).

---

## 7. Honest caveats and threats to validity

- **Quality is the gate, not the prize.** The benchmark exists to prove compression
  *without* accuracy loss. Every efficiency number is reported with its quality
  delta; a wrong-but-cheap answer is a FAIL, not a win.
- **JARVIS honesty must be credited, not punished.** When JARVIS returns "unresolved"
  (dynamic dispatch, degraded graph), the correct answer may be "unknown"; scoring
  rewards the *correct* answer, so Arm B is not penalized for honest uncertainty
  (trap C6). Equally, Arm A reading code to resolve such a case and getting it right
  should win that task — that is a legitimate JARVIS limitation to surface.
- **Index-build amortization is disclosed,** with the break-even query count; the
  claim is steady-state per-query efficiency, not free setup.
- **Single-repo, single-language generalization.** Results on `local_jarvis` (Python)
  do not automatically transfer; the pinned-manifest protocol exists precisely so the
  benchmark can be re-run on other repos/languages before any general claim.
- **Agent non-determinism** is handled by N trials + IQR, not pretended away.
- **Token-accounting fidelity** depends on the harness counting *all* context
  (including tool results) identically for both arms; §3 fixes the definition.

---

## 8. Acceptance (definition of done for this design)

| Criterion | Met by |
|---|---|
| 20–30 real developer tasks across the 4 categories | §2 (26, extendable to 30) |
| Measures tokens, wall-clock, cost, answer quality, context size | §3 |
| Scoring rubric defined | §4 |
| Success & fail thresholds defined | §5 |
| Repeatable protocol (freeze → run → score → report) | §6 |
| Controls/traps + blinding + preregistration (anti-gaming) | §2.4, §6.3 |
| Honest caveats and validity threats | §7 |
| No code; this is a measurement protocol | whole doc |

---

## 9. Bottom line

The benchmark pits **Claude alone** (reads raw code into context) against **Claude +
JARVIS** (queries deterministic precomputed intelligence) on 26 preregistered
developer tasks, holding model/repo/scaffold identical and varying only tool
availability. JARVIS **wins** only if it delivers **≥2× token compression and ≥40%
cost reduction at equal-or-better answer quality with zero fabrication** — including
controls where it has no advantage and a trap where the honest answer is "unknown."
Quality is the gate; compression is the prize; and the frozen manifest makes the
result repeatable on any model or repo.
