# Phase 167 — Recommendation

## Product hypothesis result

Scan-once / question-many **does** improve Atlas economics versus Claude Alone on:
- **Quality** (all 4 repos, all 20-question sessions)
- **Hallucination rate** (Atlas automated grounding >> Claude Alone on unfamiliar repos)
- **Impact workflow** (largest delta; unique capability)

Scan-once / question-many **does not** reliably improve:
- **Raw token count** (Atlas export overhead persists across 20 questions)
- **First-session time** on Home Assistant and VS Code until break-even question count

## Positioning

Lead with: **"Persistent repository context engine for AI coding tools."**

Wedge workflow: **Impact analysis** (what breaks if I change X).

## Pricing

Hybrid: per-user subscription + per-repository scan slot (value is amortized per repo, not per question).

## Success threshold (Phase 167 criteria)

| Repo | Quality | Hallucination | Impact | Raw tokens | Q-adj tokens | Time BE | Overall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FastAPI | PASS | PASS | PASS | FAIL | PASS | PASS (0.1≤5) | **PASS** |
| Django | PASS | PASS | PASS | FAIL | PASS | PASS (0.6≤5) | **PASS** |
| VS Code | PASS | PASS | PASS | FAIL | FAIL | PASS (0.5≤10) | **PARTIAL** |
| Home Assistant | PASS | PASS | PASS | FAIL | PASS | PASS (3.8≤30) | **PASS** |

**3 of 4 required repos fully pass** (VS Code partial due to token payload size, not quality).

## Verdict on product hypothesis

> *Atlas becomes valuable when a repository is scanned once and reused across many questions.*

**Confirmed for quality and time.** A 20-question session on a scanned repo delivers materially better grounded answers with faster amortized turnaround.

**Not confirmed for raw token reduction.** Export-per-question overhead dominates; the economic case is **quality-adjusted efficiency** and **error avoidance**, not cheaper API bills.

**Strongest evidence:** Impact workflow (+3.5 avg delta) after scan — Claude Alone cannot replicate dependency blast radius without separate tooling.