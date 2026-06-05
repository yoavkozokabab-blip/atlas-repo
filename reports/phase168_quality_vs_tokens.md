# Phase 168 — Quality vs Tokens

## Quality contribution by section class (Phase 165/167 calibration)

| Class | Weight | Loss if removed | Examples |
| --- | ---: | ---: | --- |
| A Required | 55% | 45% | File paths, direct importers, root cause, confidence |
| B Helpful | 25% | 12% | Implementation order, H2 hypothesis, indirect impact |
| C Redundant | 12% | 3% | Domain prose, duplicate lists, evidence dumps |
| D Unused | 8% | 0% | Safety footer, rollback, HOW TO USE |

## Highest-quality-per-token sections

1. **Files to inspect / direct_impact** — eliminates 75–100% hallucination (Phase 165).
2. **Confidence + limitations** — prevents overconfident Claude answers.
3. **Top hypothesis / semantic target** — routes investigation and impact.
4. **Compact repo context (once)** — replaces per-question subsystem essays.

## Lowest-quality-per-token sections

1. Domain `concept_understanding` paragraphs (catalog text).
2. Rollback + safety footers (never referenced in Claude outputs).
3. Duplicate file lists (inspect vs likely-change vs must_inspect).
4. Generic test hints (`test_{subsystem}*`).

## Compression vs quality tradeoff

| Target size | Est. quality | Est. grounding | Est. Impact quality |
| --- | ---: | ---: | ---: |
| 100% (current) | 100% | 100% | 100% |
| 50% | 89–97% (build 90%, impact 97%) | 97% | 96% |
| 25% | 81–90% | 92% | 90% |
| 10% | 78–90% | 85% | 82% |

**Sweet spot:** ~45–50% of current export size retains **≥95% quality** for Impact, Investigate, and Understanding. Build plans are prose-heavy — **50% compression ≈ 90% quality**; use minimal spec (280-token budget) to stay above 95% by dropping C+D only.

## Projected 20-question economics (Phase 167 + minimal export)

| Repo | Claude Alone | Atlas (current) | Atlas (compressed) | Quality retained |
| --- | ---: | ---: | ---: | ---: |
| FastAPI | 17,550 | 22,031 (+25%) | 13,867 (**−21%**) | 96% |
| Django | 17,550 | 23,325 (+33%) | 14,511 (**−17%**) | 96% |
| VS Code | 17,550 | 47,379 (+170%) | 25,623 (+46%) | 96% |
| Home Assistant | 17,550 | 31,930 (+82%) | 18,631 (+6%) | 96% |

Quality-adjusted efficiency (`quality / tokens × 1000`) improves **40–80%** for all repos under compression because token count drops faster than the small quality dip.

## Final answer

**Can Atlas keep 90–95% quality while reducing export size 50%+?**

**Yes**, with workflow-specific minimal exports:

- **Impact:** 50%+ reduction at **≥96%** quality (highest ROI — paths + direct importers are compact).
- **Investigate:** 50%+ reduction at **≥93%** quality (keep H1 + root cause; trim H3+ prose).
- **Build:** 50% reduction at **~90%** quality; **45% reduction (minimal spec)** at **~95%** by removing duplicate lists and domain essays only.
- **Session-level:** Send compact context once → saves **6,000–12,800 tokens** per 20-question session (Phase 167 measured).