# BLIND A/B BENCHMARK — EXECUTION STATUS

**Date:** 2026-06-20 · Design: `claude_vs_atlas_benchmark_design.md` · Harness: `scripts/ab_benchmark.py`
**Atlas frozen:** engine file hashes recorded in `ab_engine_freeze.sha256` (context_pack.py, root_cause.py, mcp_server/runtime.py) before/throughout; no retrieval/ranking/MCP changes.

---

## Honest status: the full blind A/B was NOT run in this session — by design integrity, not avoidance

The benchmark's validity depends on two things I structurally cannot provide from inside this session:

1. **No self-grading (design §4c).** I am Claude. If I generate both arms' answers *and* score them, I am grading my own work — the exact bias the design forbids and that you've told me to avoid. There is no independent human grader and no different-provider judge here. A self-graded "Atlas wins" would be fabrication.
2. **No isolated model trials.** Running the arms requires model calls; `ANTHROPIC_API_KEY` is **not set** in this environment (verified), and I am a single Atlas-saturated context, so I cannot credibly role-play an unbiased "Claude with no Atlas" across 40 isolated trials.

So I refused to manufacture answers/scores. Instead I made the design **executable** and ran the part that is valid without a model or a grader.

## What WAS executed here (valid, unbiased, model-free)

`ab_benchmark.py build` — for all 20 labeled tasks it constructs the two-arm prompts (identical system + answer template; the *only* difference is the context block: grep candidate list vs Atlas pack) and computes objective, model-free metrics: **does each arm's context contain the gold file?** and **context token size**.

This is the honest automated half of the A/B. It re-confirms, in the A/B framing, the committed retrieval result:

| Objective metric (model-free, n=20) | Arm A (grep context) | Arm B (Atlas context) |
|---|---|---|
| Context contains the gold file | **11/20 (55%)** | **17/20 (85%)** |
| Mean context tokens | 98 | 2,748 |

**Read the token row carefully (honest framing):** Arm A's 98 tokens is just a ranked *filename list* — it gives the model no code to reason about, and contains the right file only 55% of the time. Arm B's 2,748 tokens is a full actionable pack (evidence + symbols + slices) that contains the right file 85% of the time. The fair cost comparison is NOT "98 vs 2,748": a real grep agent must then **open** its candidate files to do the work — ~110,000 tokens of mostly-wrong files (per `atlas_value_validation_benchmark.md`), i.e. Atlas is **~40× cheaper to a usable answer**, not more expensive. Engine freeze verified (`sha256sum -c ab_engine_freeze.sha256` = OK for all three files).

**What this does NOT establish:** that Atlas yields *better answers* (correctness, plan quality, missed risks). That is the whole point of the human-graded A/B and requires the model + graders.

## How the owner runs the full A/B (turnkey)

```bash
# 1. Generate both arms' answers (needs a key; pick the model).
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export ATLAS_BENCH_MODEL=claude-sonnet-4-6        # or your choice; same model both arms
PYTHONPATH=. py -3 scripts/ab_benchmark.py build      # prompts + objective metrics
PYTHONPATH=. py -3 scripts/ab_benchmark.py run        # 20 tasks x 2 arms -> answers.jsonl + key.json
# 2. Blind packet for graders (strips arm identity, randomizes order).
PYTHONPATH=. py -3 scripts/ab_benchmark.py anonymize   # ab_blind/*.md + ab_scoring_sheet.csv
# 3. >=2 independent engineers each fill a copy: ab_scoring_<name>.csv
#    (score the 7 rubric dims 0-5 + the A/B-for-a-junior choice) WITHOUT seeing key.json.
# 4. Analyze (joins key, per-dimension deltas, paired sign test, Cohen's kappa).
PYTHONPATH=. py -3 scripts/ab_benchmark.py analyze
```

Guardrails baked into the harness: arm↔submission key is withheld in `key.json` until scoring is done; submissions are shuffled; answers share one template so graders can't fingerprint Atlas; `analyze` warns if fewer than 2 graders and reports inter-rater κ.

## Scale gate
This is the 20-task pilot. Expand to 50 only if the pilot shows a clear, significant Atlas win **and** inter-rater κ ≥ 0.4 (per design §7). "Atlas wins clearly" must come from the blind human grade, not from me.

## Bottom line
- **Retrieval value:** already measured and real — VERY USEFUL (`atlas_value_validation_benchmark.md`).
- **Answer-quality value (this A/B):** harness ready, objective half run; the human-graded verdict is **pending owner execution**. I will not report a win I did not measure.
