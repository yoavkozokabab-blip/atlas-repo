# Phase 173B — Abandonment Points

**Date:** 2026-06-05  
**Method:** Funnel analysis from install → Claude paste  
**Estimates:** Based on Phase 147 audit, Phase 155/146 polish, and this friction pass (no live telemetry in report)

---

## Funnel overview

```
Install          ████████████████████ 100%
Open browser     ████████████████░░░░  ~85%  (Python/SmartScreen)
Past Welcome     ██████████████░░░░░░  ~75%  (overlay fatigue)
Load sample OR   ████████████░░░░░░░░  ~60%  (path-picker trap)
  valid scan
Scan complete    ██████████░░░░░░░░░░  ~55%
Create plan      ████████░░░░░░░░░░░░░░  ~45%
Copy for Claude  ██████░░░░░░░░░░░░░░░░  ~35%  ← value realization
Paste in Claude  █████░░░░░░░░░░░░░░░░░  ~30%  (out of product)
```

**Golden path conversion (Load Sample clickers):** ~**65–75%** reach Copy for Claude.  
**Cold start conversion:** ~**25–35%** within 5 minutes.

---

## Abandonment points (ranked by severity)

### AP-1 — Install never opens browser
| Field | Detail |
| --- | --- |
| **Problem** | Python missing, `py` launcher fails, or user closes terminal |
| **Impact** | **100% abandon** — no product contact |
| **Location** | `Launch Atlas.bat`, pre-flight |
| **Exact fix** | Installer bundle; startup self-test with browser error page |
| **Priority** | **P0** |
| **Est. drop-off** | 15–25% of source-mode users |

---

### AP-2 — Welcome / onboarding fatigue
| Field | Detail |
| --- | --- |
| **Problem** | Two overlays + dense Home before any action |
| **Impact** | Close tab; “I’ll try later” |
| **Location** | `#welcomeScreen`, `#onboarding` |
| **Exact fix** | Single screen, one primary button |
| **Priority** | **P0** |
| **Est. drop-off** | 10–15% of browser opens |

---

### AP-3 — “I need a path first” trap
| Field | Detail |
| --- | --- |
| **Problem** | User chooses own repo → faces path, Validate, scope, demo packs |
| **Impact** | Never discovers sample; abandons during path paste |
| **Location** | Home `#repoPath`, `#scanBtn` disabled |
| **Exact fix** | Prominent “Try sample first (no path)” sticky banner |
| **Priority** | **P0** |
| **Est. drop-off** | 20–30% of users who skip sample |

---

### AP-4 — Scan button appears broken
| Field | Detail |
| --- | --- |
| **Problem** | Scan disabled until Validate; no explanation |
| **Impact** | Click spam then leave |
| **Location** | `#scanBtn` |
| **Exact fix** | Tooltip on disabled: “Click Validate first” or auto-validate |
| **Priority** | **P1** |
| **Est. drop-off** | 10% of own-repo attempts |

---

### AP-5 — Browse folder failure
| Field | Detail |
| --- | --- |
| **Problem** | Native browse unsupported → manual path |
| **Impact** | Windows users without path ready abandon |
| **Location** | `browseRepoFolder()` |
| **Exact fix** | Path helper + recent repos prominent |
| **Priority** | **P1** |
| **Est. drop-off** | 15% of own-repo attempts |

---

### AP-6 — Scan wait + jargon anxiety
| Field | Detail |
| --- | --- |
| **Problem** | 7 technical stage labels; large repo long wait |
| **Impact** | Cancel scan or assume hang |
| **Location** | `#view-scan`, `STAGES` |
| **Exact fix** | Plain labels + elapsed time + “safe to wait” note |
| **Priority** | **P1** |
| **Est. drop-off** | 5–15% (higher on large repos) |

---

### AP-7 — Scan success without clear next step
| Field | Detail |
| --- | --- |
| **Problem** | Success screen offers 3 equal buttons; user picks Map |
| **Impact** | Tourist mode; never creates plan |
| **Location** | `#scanSuccess` buttons |
| **Exact fix** | Single primary: **Create Change Plan**; secondary links muted |
| **Priority** | **P1** |
| **Est. drop-off** | 10–20% of scan completers |

---

### AP-8 — Codebase Map rabbit hole
| Field | Detail |
| --- | --- |
| **Problem** | 3D graph + Copilot feels like main product |
| **Impact** | 10+ minutes exploring, no export |
| **Location** | `#view-center` |
| **Exact fix** | First-run banner: “Tip: start with Change Plan”; defer 3D |
| **Priority** | **P1** |
| **Est. drop-off** | 15% of users who open Map first |

---

### AP-9 — Send to AI tab before plan
| Field | Detail |
| --- | --- |
| **Problem** | User copies repo context packet, skips plan |
| **Impact** | Claude gets generic graph, not task — **value not discovered** |
| **Location** | `#view-export`, nav position |
| **Exact fix** | Lock or redirect to “Create a plan first” |
| **Priority** | **P0** |
| **Est. drop-off** | 10% of curious clickers |

---

### AP-10 — Plan generated but no copy
| Field | Detail |
| --- | --- |
| **Problem** | Dense plan card; Copy for Claude below fold / lost in detail |
| **Impact** | User reads plan in Atlas, manually retypes for Claude |
| **Location** | `#buildOut`, `sendToAiPanel` |
| **Exact fix** | Sticky **Copy for Claude** top of result; collapse details |
| **Priority** | **P0** |
| **Est. drop-off** | 15–25% of plan creators |

---

### AP-11 — “Planning only” mistrust
| Field | Detail |
| --- | --- |
| **Problem** | User expects Atlas to write code like Cursor |
| **Impact** | “This product doesn’t work” after first plan |
| **Location** | Home beta notice, About |
| **Exact fix** | Positive framing: prepares prompts **for** Claude |
| **Priority** | **P1** |
| **Est. drop-off** | 5–10% post-plan |

---

### AP-12 — Low confidence / refusal misread
| Field | Detail |
| --- | --- |
| **Problem** | Impact refusal or medium-low confidence feels like error |
| **Impact** | Trust collapse; user leaves |
| **Location** | Impact workflow, trust blocks |
| **Exact fix** | Explain refusals: “Atlas won’t guess — try a file path from the map” |
| **Priority** | **P1** |
| **Est. drop-off** | 5% on impact-first users |

---

### AP-13 — Support / rebuild fear
| Field | Detail |
| --- | --- |
| **Problem** | User hits minor glitch → Support → clicks Clear cache |
| **Impact** | Broken session; confusion |
| **Location** | `support.html` |
| **Exact fix** | Hide destructive actions behind Troubleshooting |
| **Priority** | **P2** |
| **Est. drop-off** | Low volume, high severity |

---

## Abandonment heatmap by journey choice

| User path | 5-min value? | Main drop step |
| --- | --- | --- |
| Load Sample → Plan → Copy | **YES** | AP-10 (miss copy) |
| Guided walkthrough | **YES** (if completes) | AP-2 (length) |
| Own repo + paste path | **MAYBE** | AP-4, AP-5, AP-6 |
| Explore Map first | **NO** | AP-8 |
| Send to AI first | **NO** | AP-9 |
| Dismiss all → read hero only | **NO** | AP-3 |

---

## Hesitation moments (not full abandon)

| Moment | User thought | Fix |
| --- | --- | --- |
| Locked grey nav | “Broken?” | Tooltip: “Unlocks after scan” |
| Beginner/Advanced | “Which am I?” | Hide Advanced first week |
| Compact vs Verbose | “Which packet?” | Remove from beginner path |
| Demo pack sizes | “Which sample?” | Default Small; hide picker |
| Validate vs Scan | “Two steps?” | Merge UX |
| Download Markdown vs Copy | “Which for Claude?” | Label: “Copy = Claude; Download = save” |

---

## Misunderstandings that kill trust

| Misunderstanding | Reality | Fix location |
| --- | --- | --- |
| “Atlas writes code” | Plans only | Welcome + hero |
| “Send to AI = my task prompt” | Repo-wide context | Rename tab + empty state |
| “Scan failed” (partial graph) | Usable with caveats | Scan result copy |
| “Confidence = AI surety” | Graph grounding score | Trust legend |
| “Code uploaded to cloud” | Local scan | Reinforce at scan + export |

---

## Target funnel (after P0 fixes)

```
Install          100%
Welcome → Sample  90%
Plan created      80%
Copy for Claude   72%
```

**Enables:** ≥70% of sample clickers discover value **within 5 minutes**.

---

## Final answer

**Can a random developer discover Atlas value within 5 minutes?**

| Segment | Answer |
| --- | --- |
| **Clicks Load Sample** | **YES** (~3–4 min to Copy for Claude) |
| **Random self-serve, no docs** | **NO** (~35% reach value; most lost at Home path or Map) |
| **After P0 UX fixes** | **YES for ~70%** of first sessions |

**Bottom line:** Value exists and is fast on rails; **rails are not the default path** today. Collapse onboarding, unify export, and simplify the first plan card to make 5-minute discovery the norm—not the exception.
