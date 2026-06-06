# Phase 173B — UX Recommendations

**Date:** 2026-06-05  
**Audience:** Product / engineering — actionable fixes from first-user friction hunt  
**Goal:** Random developer → grounded Claude prompt in **≤5 minutes** without reading docs

---

## North-star UX

**One sentence for new users:** “Load the sample → describe a change → copy one prompt into Claude.”

Everything else is advanced and should unlock **after first successful copy**.

---

## P0 — Do before next beta wave (ship blockers for 5-minute value)

| ID | Problem | Impact | Location | Exact fix |
| --- | --- | --- | --- | --- |
| F-04 | Triple onboarding | Abandon at first screen | Welcome + Onboarding + Home | Merge into **one** Welcome with single primary CTA |
| F-05 | Own-repo path dumps to complex Home | Users think path is required | `dismissWelcomeScreen` → Home | Focused “Scan your repo” sub-flow; hide demo packs |
| F-16 | Plan output too dense | No clear “done” moment | `runChangePlan()` output | Beginner card: Goal, 5 files, order, **Copy for Claude** only |
| F-19 | Two export systems | Wrong paste into Claude | Build panel vs `#view-export` | Rename Send to AI tab; plan copy is default handoff |
| F-01 | Console install failure | Never opens browser | `Launch Atlas.bat` | Push installer; silent launcher; in-browser error page |

### P0 implementation sketch

```
First run:
  Welcome [Try sample — 1 min]  [Scan my repo]
  ↓ sample
  Inline progress on Home (not full Scan jargon view)
  ↓
  Change Plan (pre-filled) → [Create plan] → [Copy for Claude] (primary)
  ↓
  Toast: "Paste into Claude and ask it to implement step by step"
```

---

## P1 — High impact (next sprint)

| ID | Problem | Impact | Location | Exact fix |
| --- | --- | --- | --- | --- |
| F-07 | Label mismatch | Hesitation on primary action | Nav / buttons | Unify **Change Plan** everywhere |
| F-08 | Seven nav items | Choice paralysis | `#nav` | Beginner nav: Home · Change Plan · (locked) More ▾ |
| F-11 | Scan disabled until Validate | “Broken” scan button | `#scanBtn` | Auto-validate on blur or enable with warning |
| F-12 | Jargon scan stages | Wait anxiety | `STAGES[]` | 4 plain-English stages |
| F-15 | Browse fails | Manual path friction | `browseRepoFolder` | Inline path examples + focus Validate |
| F-17 | Impact needs path | Blank field abandon | `#impactTarget` | Module picker from scan |
| F-20 | Export tab misleads | Skips plan workflow | `#view-export` | Empty state points to Change Plan first |
| F-21 | Session/delta wording | Copy confusion | `sendToAiPanel` | “One copy = full prompt for this plan” |
| F-23 | Map toast competes | Distraction post-scan | `finishScanSession` | Defer map nudge until after first plan |
| F-26 | “Planning only” scares | Misread capability | Home beta notice | “Prepares plan; AI writes code” |
| F-29 | Partial scan = failure UI | False failure | `showScanFailed` | Separate “complete with limitations” |
| F-06 | Task cards skip scan | Empty workflow | Home explore cards | Gate cards until scanned |
| F-02 | SmartScreen | Pre-launch abandon | Installer | Welcome card with 3-step Windows note |

---

## P2 — Polish (quality + trust)

| ID | Problem | Impact | Location | Exact fix |
| --- | --- | --- | --- | --- |
| F-03 | ATLAS vs Atlas | Unpolished | Titles / hero | Standardize **Atlas** |
| F-09 | What breaks? naming | Discoverability | Nav impact | **Impact check** + tooltip |
| F-10 | Beginner/Advanced unexplained | Accidental toggle | `#modeToggle` | One-time tooltip |
| F-14 | Extra click after scan | Drop-off | Scan success | Animate primary CTA once |
| F-18 | Investigate placeholders niche | “Not for me” | Textarea placeholder | Neutral examples |
| F-22 | No post-copy affirmation | Unclear completion | Copy handlers | Claude paste instruction toast |
| F-24 | 3D map overwhelm | Tourist trap | Codebase Map | Simple 2D default |
| F-25 | Three AI surfaces | Fragmentation | Map Copilot | Hide until advanced |
| F-27 | Confidence unexplained | Trust confusion | Trust blocks | First-run legend |
| F-28 | Scary Support actions | Fear | `support.html` | Troubleshooting accordion |
| F-30 | Multiple loaders | Feels slow | Boot/scan | Inline sample load on Home |

---

## P3 — Nice to have

| ID | Fix summary |
| --- | --- |
| F-13 | Soften “60 seconds” copy to “usually under a minute” |

---

## Terminology dictionary (recommended in-app)

Ship a **“What the words mean”** drawer (from `quickstart.html` L49–56) inside app — one click from Help:

| User-facing term | Plain definition |
| --- | --- |
| **Change Plan** | Files and steps for a feature you describe |
| **Impact check** | What might break if you edit one file |
| **Investigation** | Best guess at bug cause + how to verify |
| **Copy for Claude** | One paste-ready prompt for your AI tool |
| **Repository context** | Background facts about the whole repo (advanced) |
| **Codebase Map** | Visual graph of how files import each other |

---

## Onboarding speed recommendations

| Current | Recommended |
| --- | --- |
| Welcome → Onboarding → Home | **Welcome only** (sample CTA) |
| 8-step guided tour default offer | Opt-in “Tour (3 min)” |
| Scan view for demo load | **Inline** on Home |
| 7 nav items | **3** until first copy |
| 2 export UIs | **1** primary (plan copy) |

**Target time-to-value:** 180 seconds to first Copy for Claude (sample path).

---

## Cognitive load reduction

**Hide until first success:**
- Advanced scan scope
- Demo pack size picker (default Small)
- Codebase Map 3D controls
- Copilot sidebar
- Rollback / impact simulation on plan card
- Verbose export packets
- Billing nav

**Always visible:**
- Load Sample
- Change Plan input + Generate
- Copy for Claude (after plan)
- “Local only — code not uploaded”

---

## Wording replacements (copy deck)

| Current | Replace with |
| --- | --- |
| Repository Intelligence Platform | *remove from hero; use once in About* |
| Generate Change Plan | **Create Change Plan** |
| Planning only — does not edit files | **Atlas plans; Claude/Cursor implement** |
| Send to AI | **Repository context** (advanced) |
| Building AI context packets | **Preparing summary** |
| Generating verification evidence | **Checking file links** |
| Scan a repository first | **Load a sample or scan your project first** |

---

## Measurement (post-fix)

Track funnel events (local analytics already wired):

1. `welcome_sample_clicked`
2. `scan_completed` (demo vs real)
3. `build_plan_created`
4. `export_copied_claude` (workflow panel)
5. Time deltas between 1→5

**Success metric:** ≥70% of first sessions that click Load Sample reach step 5 within 5 minutes.

---

## Priority summary

| Priority | Count | Theme |
| --- | ---: | --- |
| P0 | 5 | Onboarding collapse, plan simplicity, export unification |
| P1 | 12 | Labels, scan path, handoff clarity |
| P2 | 10 | Map, trust copy, polish |
| P3 | 1 | Timing copy |

**Estimated eng effort for P0+P1:** ~3–5 focused UI days (no intelligence changes).
