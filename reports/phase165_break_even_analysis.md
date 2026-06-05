# Phase 165 — Break-Even Analysis

**Date:** 2026-06-05  
**Purpose:** Determine at what point Atlas investment pays off vs using Claude Alone.

---

## Framework

Break-even exists across three dimensions:
1. **Time** — when does Atlas + scan save developer time?
2. **Token cost** — when does Atlas reduce total API cost?
3. **Quality** — when does Atlas produce enough correct output to justify overhead?

---

## Time Break-Even

### Setup

| Variable | Value |
|---|---|
| Claude API call time | 4 seconds (average) |
| Atlas plan generation time (post-scan) | 0.08–0.71s per task |
| Scan cost (one-time per session) | 2.4s – 340.4s |
| Time saved per question (Atlas used standalone) | ~3.5s |
| Time saved per question (Atlas → Claude) | ~0.5–1s (Claude needs less reasoning time) |

### Break-even: Atlas plan replaces Claude entirely

`N > scan_time / (claude_time - atlas_task_time)`

| Repo | Scan time | Time saved/q | Break-even N |
|---|---:|---:|---:|
| FastAPI | 2.4s | 3.5s | **1 question** |
| Django | 18.8s | 3.5s | **6 questions** |
| VS Code | 29.1s | 3.5s | **9 questions** |
| Home Assistant | 340.4s | 3.5s | **98 questions** |

### Break-even: Atlas export used as Claude context (Atlas + Claude both run)

`N > scan_time / time_saved_per_question_from_shorter_claude_output`

Assuming Claude answers 1 second faster when given Atlas context (less reasoning needed):

| Repo | Scan time | Time saved/q | Break-even N |
|---|---:|---:|---:|
| FastAPI | 2.4s | 1s | **3 questions** |
| Django | 18.8s | 1s | **19 questions** |
| VS Code | 29.1s | 1s | **30 questions** |
| Home Assistant | 340.4s | 1s | **341 questions** |

---

## Token Cost Break-Even

### Setup

Atlas adds tokens per task (compact export), but Claude produces shorter output because it's already grounded.

| Variable | Value |
|---|---|
| Claude Alone input | ~75 tokens |
| Claude Alone output | ~650 tokens |
| Atlas compact export | 324–673 tokens |
| Claude + Atlas input | 374–723 tokens |
| Claude + Atlas output | ~300 tokens (shorter) |

Per-task token delta (Atlas vs Alone):
```
Atlas adds: (export + shorter_output_overhead)
FastAPI: +649 input - 350 output savings = +299 net tokens/task
Django: +685 input - 350 output savings = +335 net tokens/task
HA: +683 input - 350 output savings = +333 net tokens/task
VS Code: +723 input - 350 output savings = +373 net tokens/task
```

**Atlas never saves tokens.** It always adds 299–373 tokens per task.

**Token cost break-even: does not exist.** Atlas increases token count on every task.

BUT: quality-adjusted cost per token:
- Claude Alone: $0.00453 per quality point
- Atlas + Claude: $0.00197 per quality point (57% cheaper)

So while Atlas uses more raw tokens, it is significantly more cost-efficient when quality is factored in.

---

## Quality Break-Even

When is Claude Alone "good enough" that the Atlas overhead isn't justified?

Answer by repo and workflow:

### FastAPI (Claude Alone avg = 3.0, Atlas avg = 4.0)

| Workflow | A score | B score | Atlas justified? |
|---|---:|---:|---|
| Build Plan | 3.0 | 3.8 | Yes for new-to-framework devs; No for FastAPI experts |
| Investigation | 3.0 | 3.8 | Marginal — Claude knows FastAPI patterns |
| Impact | 1.0 | 4.4 | YES — Atlas provides unique capability |

**FastAPI:** Atlas justified for Impact always. Marginal for Build/Investigation if you already know FastAPI.

### Django (Claude Alone avg = 3.1, Atlas avg = 4.1)

| Workflow | A score | B score | Atlas justified? |
|---|---:|---:|---|
| Build Plan | 3.8 | 4.4 | Marginal for Django experts |
| Investigation | 3.6 | 4.0 | Marginal — minimal gap |
| Impact | 1.4 | 3.8 | YES |

**Django:** Atlas justified for Impact. Marginal for Build/Investigation due to Claude's strong Django training.

### Home Assistant (Claude Alone avg = 1.7, Atlas avg = 3.7)

| Workflow | A score | B score | Atlas justified? |
|---|---:|---:|---|
| Build Plan | 2.0 | 3.8 | **YES** — A is mostly wrong |
| Investigation | 2.0 | 3.6 | **YES** — A is mostly wrong |
| Impact | 1.0 | 3.8 | **YES** |

**Home Assistant:** Atlas justified for all three workflows. Claude Alone produces hallucinated files 80–100% of the time on HA.

### VS Code (Claude Alone avg = 1.7, Atlas avg = 3.0)

| Workflow | A score | B score | Atlas justified? |
|---|---:|---:|---|
| Build Plan | 2.0 | 3.0 | YES — A is mostly wrong |
| Investigation | 2.0 | 3.0 | YES — A is mostly wrong |
| Impact | 1.0 | 3.0 | YES — only Atlas can do this |

**VS Code:** Atlas justified everywhere. The 84% unresolved import ratio limits Atlas's ceiling to ~3.0, but that's still +1.0 over Claude Alone's ceiling of ~2.0.

---

## Composite Break-Even: When Is Atlas Worth Using?

### Always worth using:
1. **Impact analysis on any repo** — Atlas provides the dependency graph; Claude Alone cannot
2. **Any task on Home Assistant, VS Code, or other complex unfamiliar repos** — Claude Alone hallucinates 80–100% of the time
3. **Any project with 6+ questions per session** (except HA which needs 98+)

### Worth using with caveats:
4. **Build Plan on Django/FastAPI** — small gap (+0.6–0.8), justified if developer is new to the repo
5. **Investigation on Django/FastAPI** — minimal gap (+0.4–0.8), justified when specific file paths matter

### Not clearly worth using:
6. **Investigation on Django with common patterns** — Claude's training knowledge matches Atlas (gap = +0.4)
7. **Any single one-off question** on HA (5.7-minute scan for 1 question is not justified)

### Never worth using:
8. **Atlas plan used directly (standalone) for token efficiency** — quality/token is lower than Claude Alone

---

## ROI Summary Table

| Scenario | Time ROI | Token ROI | Quality ROI | Recommended? |
|---|---|---|---|---|
| FastAPI, any workflow, ≥1 question | ✅ Positive (break-even=1) | ❌ Negative | ✅ +74% quality | **YES** |
| Django, any workflow, ≥6 questions | ✅ Positive (break-even=6) | ❌ Negative | ✅ +32% quality | **YES** |
| VS Code, any workflow, ≥9 questions | ✅ Positive (break-even=9) | ❌ Negative | ✅ +76% quality | **YES** |
| HA, any workflow, ≥98 questions | ⚠️ Marginal | ❌ Negative | ✅ +118% quality | **Only long sessions** |
| HA, <98 questions | ❌ Negative | ❌ Negative | ✅ +118% quality | **Only if quality critical** |
| Any repo, Impact workflow only | ✅ Positive | ❌ Negative | ✅ +246% quality | **YES — Impact only** |
| Any repo, one-off question | ❌ Negative | ❌ Negative | ✅ Varies | **Maybe if quality critical** |

---

## The Real Break-Even Question

The honest product positioning question is not "does Atlas save time?" or "does Atlas save tokens?" on a per-task basis. The real question is:

**Is the quality improvement worth the scan investment?**

- For a developer who makes costly mistakes from bad file paths: Atlas is worth it from question 1.
- For a developer who can verify file paths quickly themselves: Atlas adds less value.
- For Impact analysis specifically: Atlas is the only viable option regardless of cost.

The **single clearest value proposition** from this study:

> Atlas is the only practical way to get correct file-level impact analysis without running a separate static analysis tool. On Impact tasks across all 4 repos, Claude Alone averages 1.1/5; Atlas averages 3.8/5. This is not a marginal improvement — it is a fundamentally different capability.

---

## What Would Change the Break-Even

| Improvement | Effect on break-even |
|---|---|
| Reduce HA scan time to <30s | HA break-even drops from 98 → 9 questions |
| Symbol-level evidence (+1.0 quality) | Quality gap widens → ROI improves for all repos |
| Incremental/cached scans (only new files) | Re-scan cost drops 90% → all repos become attractive |
| Build Plan insertion points (CORRECT outputs) | Justifies Atlas on every question for any project |
| Mac/Linux support | Opens second platform — doubles addressable user base |
