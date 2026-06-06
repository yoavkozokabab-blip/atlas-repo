# Phase 177 — Live Claude Validation Plan

**Date:** 2026-06-06  
**Purpose:** Design a definitive live validation run using the Anthropic API to measure Atlas quality before external beta  
**Status:** Design only. Do not implement until after P0 fixes are applied.

---

## What This Validates

The existing Phase 170 validation used proxy scoring (export-grounded, no live Claude calls). This plan designs the live equivalent: real Claude API calls, real response scoring, real hallucination detection.

**Central question:** Does the medium demo + Phase 172 Repository Memory export + Phase 174 trust envelope produce Claude responses that are meaningfully better than Claude Alone — and do those responses justify asking 5 developers to use Atlas daily?

---

## Study Design

### Conditions

| Condition | What Claude receives |
|-----------|---------------------|
| **A — Claude Alone** | Repository name + 1-sentence description + task prompt. No file list. No graph data. |
| **B — Atlas MINIMAL** | Atlas minimal export (current) + task prompt. Includes session memory header. |
| **C — Atlas MEMORY** | Atlas delta export only + task prompt (memory header sent once, not per question). |

Condition C tests whether the Phase 172 delta format preserves quality at 57% fewer tokens.

### Repositories

| Repo | Why | Scale |
|------|-----|-------|
| FastAPI | Well-known; Claude has training knowledge; good baseline | 73 modules |
| Django | Claude knows it well; tests whether Atlas adds beyond training data | 929 modules |
| Home Assistant | Claude training knowledge thin; Atlas advantage should be largest | 9,709 modules |
| Medium Demo | The exact repo beta users will scan first; validate demo quality | 17 modules |

### Task Suite (15 tasks per repo)

Identical to Phase 170 suite plus 3 new demo-specific tasks:

**Build (5 tasks):**
- B01: add rate limiting
- B02: add audit logging
- B03: add feature flags
- B04: add request tracing
- B05: add config validation

**Investigate (5 tasks):**
- V01: why are duplicate events emitted?
- V02: why are requests slow?
- V03: why does auth fail?
- V04: why does websocket disconnect?
- V05: why does config validation fail?

**Impact (5 tasks):**
- I01: what breaks if I change authentication?
- I02: what breaks if I change routing?
- I03: what breaks if I change config loading?
- I04: what breaks if I change websocket support?
- I05: what breaks if I change event handling?

**Total:** 4 repos × 15 tasks × 3 conditions = **180 API calls**

---

## Scoring Rubric

Use Phase 165 rubric (0–5 scale):

| Score | Meaning |
|-------|---------|
| 5 | Correct, grounded, actionable; names real files; realistic tests |
| 4 | Mostly correct; minor missing details |
| 3 | Useful direction but incomplete or noisy |
| 2 | Partial and risky; heavy verification needed |
| 1 | Misleading or wrong target |
| 0 | Fails / refuses / hallucinates badly |

**Binary flags per response:**
- `correct_primary_file`: Does response name a file that actually exists in the repo?
- `hallucinated_file`: Does response name a file that does NOT exist?
- `correct_subsystem`: Does response identify the right code subsystem?
- `useful_for_cursor`: Would a Cursor user paste this response and start editing?
- `confidence_matches_quality`: Does Atlas confidence label (medium-high / low) match actual response quality?

---

## Metrics to Measure

### Primary (go/no-go)

| Metric | Target | Measured by |
|--------|--------|-------------|
| Quality delta (Atlas vs Claude Alone) | ≥ +0.5 average across all tasks | Rubric score comparison |
| Hallucination rate: Claude Alone | Confirm ≥ 50% on HA/VS Code | Binary hallucinated_file flag |
| Hallucination rate: Atlas | ≤ 5% across all repos | Binary hallucinated_file flag |
| Quality delta (MEMORY vs MINIMAL) | ≥ −0.2 (no significant degradation) | Rubric score comparison |
| Token cost: MEMORY vs MINIMAL | ≥ −50% | Measured from API usage |

### Secondary (product learning)

| Metric | Purpose |
|--------|---------|
| Latency per call (A vs B vs C) | Validate 174B claim: delta exports don't hurt latency |
| Token usage per call | Compute actual cost per workflow (not estimated) |
| Quality by workflow type | Are build/investigate/impact equally improved? |
| Quality by repo size | Does advantage scale with repo size as expected? |
| Demo repo quality (medium) | Baseline for what beta users will experience |
| Claude Alone quality on demo | If Claude Alone already scores 4/5 on a 17-module toy demo, Atlas adds nothing there |

---

## Expected Results (Based on Phase 165 Data)

| Repo | A (Claude Alone) expected | B (Atlas) expected | Hallucination A | Hallucination B |
|------|:-------------------------:|:------------------:|:---------------:|:---------------:|
| FastAPI | 3.0 | 3.8 | 80% | <5% |
| Django | 3.8 | 4.4 | 20% | <5% |
| Home Assistant | 2.0 | 3.8 | 100% | <5% |
| Medium Demo | 3.5 | 3.5–4.0 | 20–40% | <10% |

**Key insight from Phase 165:** Atlas advantage is largest on repos Claude doesn't know well (Home Assistant: +1.8) and smallest on repos Claude knows from training (Django: +0.6, FastAPI: +0.8). The medium demo (generic file names) will show modest improvement.

---

## System Prompt

```
You are a senior engineer helping implement or investigate a codebase change.

<atlas_context>
[SESSION HEADER OR "No Atlas context provided."]
</atlas_context>

<task>
[WORKFLOW PROMPT]
</task>

Be concrete. Name specific files. Order your steps. Note risks.
If you cannot identify specific files without reading the codebase, say so — do not invent file names.

After your answer, output exactly one line:
SCORES={"quality":N,"hallucinated_file":true|false,"correct_primary":true|false,"useful_for_cursor":true|false}
where N is 0–5.
```

---

## Score Extraction

Parse the `SCORES={}` line from Claude's response. Use a regex:
```python
import re, json
m = re.search(r'SCORES=(\{[^}]+\})', response_text)
if m:
    scores = json.loads(m.group(1))
```

If Claude fails to emit the SCORES line (rare), score manually via the rubric.

---

## Latency and Token Measurement

For every API call, record:
- `input_tokens` from the API response
- `output_tokens` from the API response
- Wall-clock time from request start to response complete
- Total cost estimate at current Haiku pricing ($0.25/M input, $1.25/M output)

Expected cost for full study: ~$2–4 for 180 Haiku calls.

---

## Pass Criteria

The live validation passes if:

| Criterion | Threshold |
|-----------|-----------|
| Atlas quality advantage (B vs A) | ≥ +0.5 averaged across all tasks |
| Atlas hallucination rate (B) | ≤ 5% across all repos |
| MEMORY quality vs MINIMAL (C vs B) | ≥ −0.2 (no degradation) |
| MEMORY token savings (C vs B) | ≥ −40% tokens |
| Demo repo (medium) quality (B) | ≥ 3.5 average |
| Demo repo (medium) hallucination (B) | ≤ 15% |

If all pass: Atlas is ready to show beta users as a quality improvement tool.  
If demo repo quality < 3.5: The medium demo is not good enough to be the default first experience — a better demo repo must be designed.

---

## What This Validation Cannot Measure

- Whether developers will find Atlas *useful* in their actual workflow (only user interviews measure this)
- Whether the UX makes the value obvious (only usability testing measures this)
- Whether the copy-paste workflow is smooth (only live screen observation measures this)
- Improvement on non-Python/TypeScript repos (Go, Java, C# — by design, these refuse)

---

## Pre-conditions Before Running

1. Apply P0 fixes (especially demo switch to medium, `function:` prefix fix)
2. Confirm `ANTHROPIC_API_KEY` set and Haiku model available
3. Confirm FastAPI, Django, Home Assistant repos available in `external_repos/`
4. Run Phase 170 harness first (`benchmarks/phase170_real_llm_validation.py`) as smoke test
5. Run Phase 172 harness (`benchmarks/phase172_memory_validation.py`) to get MEMORY baseline

---

## Output Format

Write results to `phase177_validation_raw.json` with:
```json
{
  "meta": {"date": "...", "model": "...", "conditions": ["A", "B", "C"]},
  "trials": [
    {
      "repo_id": "fastapi",
      "task_id": "B01",
      "condition": "B",
      "prompt": "add rate limiting",
      "quality": 4,
      "hallucinated_file": false,
      "correct_primary": true,
      "input_tokens": 312,
      "output_tokens": 142,
      "latency_s": 1.4
    }
  ],
  "aggregate": {
    "quality_A": 2.7,
    "quality_B": 3.8,
    "quality_C": 3.7,
    "hallucination_A_pct": 68.0,
    "hallucination_B_pct": 2.0,
    "tokens_B_avg": 450,
    "tokens_C_avg": 210
  }
}
```
