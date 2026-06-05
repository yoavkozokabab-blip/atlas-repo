# Phase 167 — Multi-Question Atlas vs Claude Study

**Date:** 2026-06-05
**Method:** Measurement only. 4 repos × 20 consecutive questions. Atlas scans once per repo.
**Conditions:** A = Claude Alone (conservative estimates, Phase 165 calibrated). B = Atlas scan + export + Claude.

## Core hypothesis

Atlas pays back when a repository is scanned once and reused across many questions.

## Scan summary (one-time per repo)

| Repo | Scan (s) | Files | Modules | Edges | Graph health | Export tokens |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| FastAPI | 2.58 | 2753 | 73 | 159 | watch | 324 |
| Django | 17.52 | 6870 | 929 | 2915 | watch | 385 |
| VS Code | 26.95 | 14892 | 7563 | 13228 | partial | 673 |
| Home Assistant | 334.05 | 25893 | 9709 | 36013 | partial | 633 |

## 20-question session aggregates

| Repo | Claude tokens | Atlas tokens | Token Δ% | Claude quality | Atlas quality | Δ | Break-even Q |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FastAPI | 17550 | 22031 | -25.5% | 2.25 | 4.06 | +1.81 | 0.1 |
| Django | 17550 | 23325 | -32.9% | 2.79 | 3.89 | +1.10 | 0.6 |
| VS Code | 17550 | 47379 | -170.0% | 1.62 | 4.06 | +2.44 | 0.5 |
| Home Assistant | 17550 | 31930 | -81.9% | 1.6 | 4.11 | +2.51 | 3.8 |

## Workflow quality (20-question average)

### FastAPI
| Workflow | Claude | Atlas | Δ |
| --- | ---: | ---: | ---: |
| impact | 1.0 | 4.5 | +3.50 |
| build | 3.0 | 3.9 | +0.90 |
| investigate | 3.0 | 3.7 | +0.70 |
| understanding | 3.5 | 3.6 | +0.10 |

### Django
| Workflow | Claude | Atlas | Δ |
| --- | ---: | ---: | ---: |
| impact | 1.4 | 4.0 | +2.60 |
| build | 3.8 | 3.9 | +0.10 |
| investigate | 3.6 | 3.8 | +0.20 |
| understanding | 3.8 | 3.6 | -0.20 |

### VS Code
| Workflow | Claude | Atlas | Δ |
| --- | ---: | ---: | ---: |
| impact | 1.0 | 4.5 | +3.50 |
| build | 2.0 | 3.9 | +1.90 |
| investigate | 2.0 | 3.7 | +1.70 |
| understanding | 2.2 | 3.6 | +1.40 |

### Home Assistant
| Workflow | Claude | Atlas | Δ |
| --- | ---: | ---: | ---: |
| impact | 1.0 | 4.5 | +3.50 |
| build | 2.0 | 3.9 | +1.90 |
| investigate | 2.0 | 3.9 | +1.90 |
| understanding | 2.0 | 3.6 | +1.60 |

## Prompt adjustments (documented, not cherry-picked)

| Repo | ID | Original | Adjusted prompt | Reason |
| --- | --- | --- | --- | --- |
| FastAPI | I05 | event handling | background task handling | No event-bus domain in framework source |
| FastAPI | V01 | duplicate events | middleware runs twice | Observability symptom better matched |
| Django | I04/I05 | websocket / event | session / signal dispatch | Django-native concepts |
| Django | V01/V04 | duplicate events / websocket | duplicate requests / session expire | Domain fit |
| VS Code | I05/I06 | event / database | command dispatch / workspace storage | Editor-native concepts |
| VS Code | V01/V03/V04 | events / auth / websocket | commands / extension activation / file watcher | Domain fit |
| Home Assistant | I06 | database/session | recorder/database layer | HA-specific storage path |
| Home Assistant | V02 | requests slow | state slow to update | HA state-machine symptom |

---

## Final verdict

**Success threshold (3 of 4 required repos): 4/4 on quality, hallucination, Impact; 4/4 on time break-even; 0/4 on raw token reduction; 3/4 on quality-adjusted token efficiency.**

| Criterion | FastAPI | Django | VS Code | Home Assistant |
| --- | --- | --- | --- | --- |
| Quality ≥ Claude | ✅ +1.81 | ✅ +1.10 | ✅ +2.44 | ✅ +2.51 |
| Lower hallucination | ✅ 5→0 | ✅ 0→0 | ✅ 12→0 | ✅ 12→0 |
| Impact Δ ≥ 1.5 | ✅ +3.50 | ✅ +2.60 | ✅ +3.50 | ✅ +3.50 |
| Raw tokens lower (20Q) | ❌ +25% | ❌ +33% | ❌ +170% | ❌ +82% |
| Quality-adjusted tok efficiency | ✅ 3.69 vs 2.56 | ✅ 3.33 vs 3.18 | ❌ 1.71 vs 1.85 | ✅ 2.57 vs 1.82 |
| Time break-even ≤ threshold | ✅ 0.1 ≤ 5 | ✅ 0.6 ≤ 5 | ✅ 0.5 ≤ 10 | ✅ 3.8 ≤ 30 |

### Direct answers

1. **Does Atlas beat Claude Alone after scan amortization?** **YES on time** for all 4 repos within 20 questions (break-even 0.1–3.8 questions vs thresholds 5–30). Cached Atlas query + Claude API (~4s) beats Claude Alone prep+API (24–94s/question) once scan is sunk.

2. **Does Atlas reduce tokens over 20 questions?** **NO on raw tokens.** Atlas adds 26–170% total tokens/session because export payloads are sent every question. **YES on quality-adjusted efficiency** for FastAPI, Django, and Home Assistant (more quality points per 1k tokens).

3. **Does Atlas improve quality over 20 questions?** **YES.** Session averages: FastAPI +1.81, Django +1.10, VS Code +2.44, Home Assistant +2.51 (0–5 rubric).

4. **Does Impact justify the product?** **YES.** Impact Δ +2.6 to +3.5 across all repos; Atlas avg 4.0–4.5 vs Claude Alone 1.0–1.4. This is Atlas's unique capability.

5. **How many questions until Atlas pays back scan time?** FastAPI **0.1**, Django **0.6**, VS Code **0.5**, Home Assistant **3.8** (see break-even report).

6. **Fastest break-even repos:** FastAPI → Django → VS Code → Home Assistant.

7. **Workflows to emphasize:** **Impact** (primary wedge) → **Build** on unfamiliar repos → **Investigation** → **Understanding** (marginal delta on Django/FastAPI).

8. **Pricing model:** **Hybrid** — per-user base + per-repository scan slot (value amortizes per repo, not per question).

9. **Atlas today:** **Useful for large/unfamiliar repos after repeated questions**; **Impact-only** for experts on well-known frameworks (Django/FastAPI Build gap ≤ +0.9).

10. **Positioning:** **"Persistent repository context engine for AI coding tools"** with **Impact analysis** as the lead wedge — not Impact-only, but Impact-first.