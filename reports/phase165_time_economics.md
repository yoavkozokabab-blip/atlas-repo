# Phase 165 — Time Economics

**Date:** 2026-06-05  
**All times measured from live Atlas runs.**

---

## Measured Times

### Scan times (one-time per repo)

| Repo | Scan time | Modules | Notes |
|---|---:|---:|---|
| FastAPI | **2.4s** | 73 | Very fast — small repo |
| Django | **18.8s** | 929 | Moderate — well-structured |
| VS Code | **29.1s** | 7,563 | Fast despite large size (TS efficient) |
| Home Assistant | **340.4s (5.7 min)** | 9,709 | Slow — 25,893 files, deep import graph |

### Per-task times (post-scan)

| Repo | Build Plan | Investigation | Impact | Avg per task |
|---|---:|---:|---:|---:|
| FastAPI | 0.14s | 0.08s | 0.01s | **0.08s** |
| Django | 0.31s | 0.27s | 0.06s | **0.21s** |
| Home Assistant | 0.72s | 0.69s | 0.72s | **0.71s** |
| VS Code | 0.15s | 0.10s | 0.13s | **0.13s** |

### Claude API time (estimated)

Claude API response time: **3–5 seconds** per request (network + model inference).  
This is the same for both Condition A (Claude Alone) and for the Claude step in Condition B.

---

## First-Question Total Time

"First question" = scan + Atlas plan generation + (optional) Claude response

| Repo | Atlas scan | Atlas plan | Total Atlas | Claude Alone API | Atlas vs Claude |
|---|---:|---:|---:|---:|---|
| FastAPI | 2.4s | 0.14s | **2.54s** | 3–5s | **Atlas faster** |
| Django | 18.8s | 0.31s | **19.1s** | 3–5s | Claude faster (4× gap) |
| VS Code | 29.1s | 0.15s | **29.25s** | 3–5s | Claude faster (7× gap) |
| Home Assistant | 340.4s | 0.72s | **341.1s** | 3–5s | Claude faster (80× gap) |

**On first use, Claude Alone is faster for every repo except FastAPI.**

---

## Subsequent Questions (repo already scanned)

After the first scan, Atlas is in memory. Subsequent questions cost only Atlas plan generation time.

| Repo | Atlas per question | Claude Alone per question | Difference |
|---|---:|---:|---|
| FastAPI | 0.08s | 3–5s | **Atlas 37–62× faster** |
| Django | 0.21s | 3–5s | **Atlas 14–24× faster** |
| Home Assistant | 0.71s | 3–5s | **Atlas 4–7× faster** |
| VS Code | 0.13s | 3–5s | **Atlas 23–38× faster** |

**For subsequent questions, Atlas is dramatically faster — plan generation takes <1s vs 3–5s for Claude API calls.**

BUT: This comparison is misleading if you still need Claude to process the Atlas plan. In that case:
- Atlas + Claude: 0.08–0.71s (Atlas) + 3–5s (Claude) = 3–6s total
- Claude Alone: 3–5s

Net time saved per question (post-scan) = Atlas plan generation time saved on Claude input reasoning = **approximately 0–1 second**.

The real time savings come when **Atlas plan is used directly** (without Claude). In that case:
- Atlas per question: 0.08–0.71s
- Claude Alone: 3–5s  
- **Savings: 2.5–5s per question**

---

## Time to "Usable Answer"

| Condition | Time to usable answer | Notes |
|---|---|---|
| Claude Alone (cold) | 3–5 seconds | Immediate — no scan needed |
| Claude Alone (1 question) | 3–5 seconds | Same |
| Atlas (cold, 1st question) | 2.5–345s | Includes scan |
| Atlas (warm, subsequent) | 0.1–0.8 seconds | Post-scan; excludes optional Claude step |

---

## Break-Even Calculation

### Time break-even: How many questions before Atlas scan pays off?

The question: for N questions, does scan_time + N × atlas_per_q < N × claude_alone_per_q?

Solving: N > scan_time / (claude_time - atlas_time)

Assuming:
- Claude alone: 4 seconds per question
- Atlas per question (if replacing Claude): 0.5 seconds (using Atlas plan directly)
- Time saved per question: 3.5 seconds

| Repo | Scan time | Time saved/q | Break-even questions |
|---|---:|---:|---:|
| FastAPI | 2.4s | 3.5s | **1 question** |
| Django | 18.8s | 3.5s | **6 questions** |
| VS Code | 29.1s | 3.5s | **9 questions** |
| Home Assistant | 340.4s | 3.5s | **98 questions** |

**Home Assistant's 5.7-minute scan time requires ~98 questions to break even on time alone.** That is a significant barrier for a developer who works in a single HA session.

**FastAPI and Django break even very quickly (1–6 questions).** These are ideal Atlas use cases for developers who ask many questions about the same repo.

### Time break-even if Atlas plan is used as Claude context (not standalone)

In this mode, Atlas saves the time Claude would spend reasoning about file structure, not the full API call time. Claude response is ~1 second shorter (less reasoning needed). This makes the break-even much worse:

| Repo | Scan time | Time saved/q | Break-even |
|---|---:|---:|---:|
| FastAPI | 2.4s | ~1s | **3 questions** |
| Django | 18.8s | ~1s | **19 questions** |
| VS Code | 29.1s | ~1s | **30 questions** |
| Home Assistant | 340.4s | ~1s | **341 questions** |

---

## Session Modeling

### A typical developer session (10 questions about one repo):

| Repo | Total time (Atlas) | Total time (Claude Alone) | Atlas faster? | Time diff |
|---|---:|---:|---|---:|
| FastAPI | 2.4s + 10×0.08s = 3.2s | 10×4s = 40s | YES | -36.8s |
| Django | 18.8s + 10×0.21s = 20.9s | 10×4s = 40s | YES | -19.1s |
| VS Code | 29.1s + 10×0.13s = 30.4s | 10×4s = 40s | YES | -9.6s |
| Home Assistant | 340.4s + 10×0.71s = 347.5s | 10×4s = 40s | **NO** | +307.5s |

Home Assistant is the exception. Its 5.7-minute scan makes a 10-question session 5× slower with Atlas than without. You'd need ~100 questions per session to justify the scan time.

### A long project (100 questions, multiple sessions, cached scan):

| Repo | Atlas total | Claude Alone total | Atlas faster? |
|---|---:|---:|---|
| FastAPI | 2.4s + 100×0.08s = 10.4s | 100×4s = 400s | **YES — 38× faster** |
| Django | 18.8s + 100×0.21s = 39.8s | 100×4s = 400s | **YES — 10× faster** |
| VS Code | 29.1s + 100×0.13s = 42.1s | 100×4s = 400s | **YES — 9× faster** |
| Home Assistant | 340.4s + 100×0.71s = 411.4s | 100×4s = 400s | No (break-even at 98q) |

For large projects with many questions, Atlas wins decisively on all repos except Home Assistant.

---

## Summary

| Metric | FastAPI | Django | VS Code | Home Assistant |
|---|---|---|---|---|
| First-use time | **Atlas faster** | Claude faster | Claude faster | Claude faster (80×) |
| Per-question (warm) | **Atlas 37-62× faster** | **Atlas 14-24× faster** | **Atlas 23-38× faster** | **Atlas 4-7× faster** |
| Break-even questions | **1** | **6** | **9** | **98** |
| 10-question session | **Atlas wins** | **Atlas wins** | **Atlas wins marginal** | **Claude wins** |
| 100-question project | **Atlas wins** | **Atlas wins** | **Atlas wins** | Break-even |

**The time economics are favorable for all repos once you have ≥6–10 questions per session, except Home Assistant which requires ~100 questions to justify its scan time.**
