# Website Benchmark Section Refresh

**Date:** 2026-06-04
**Scope:** Marketing website only (`jarvis_landing` / deploy repo `C:\jarvis_landing` → `github.com/yoavkozokabab-blip/atlas-website`). No Atlas product code, Builder Core, or scan logic changed.
**Section updated:** "Tested on real repositories" (`#repos`) + hero metric cards (kept consistent).

---

## 1. Summary

The benchmark section was rebuilt around the **measured** Phase 137 + overnight
validation evidence. The old section showed 3 repositories (FastAPI, Django, VS Code)
with Phase 116G numbers that understated Atlas's scale. The new section adds:

- A **headline metrics row** (8 aggregate measurements).
- **4 repository cards** (Home Assistant, Django, VS Code, FastAPI) showing files,
  modules, dependency edges, scan time, context reduction, unresolved imports, graph
  health, and impact score.
- A **before/after impact visual** proving cross-language generalization (Phase 136 →
  Phase 137).
- A **benchmark CTA** with the measured module/edge range.

Every number is traceable to a source file (Section 4). No numbers were invented.
Honesty is preserved: all four graphs are labelled **Partial**, unresolved imports are
shown per repo, and no 100% import-resolution claim is made.

---

## 2. Old section (before)

Captured live from the running site prior to the change.

**Header:** eyebrow "VERIFIED BENCHMARK", title "Tested on real repositories".

**3 cards:**

| Repo | Health | Scan | Modules | Edges | Unresolved |
|------|--------|-----:|--------:|------:|-----------|
| FastAPI | Partial | 2.1s | 73 | 159 | 560 · 78% |
| Django | Watch | 14.3s | 929 | 2,916 | 1,377 · 32% |
| VS Code | Partial | 6.4s | 7,551 | 13,224 | 67,164 · 84% |

**Old hero metric cards:** VS Code 7,551 mod · 13,224 edges · 6.4s; Django 929 · 2,916 · 14.3s; FastAPI 73 · 159 · 2.1s.

> Note on screenshots: the environment's image-capture tool times out on every render
> (renderer stays responsive to JS throughout — confirmed repeatedly across sessions).
> "Screenshots" in this report are therefore exact live DOM/text captures rather than
> PNGs. To produce images, open `jarvis_landing/index.html` in a browser or run a
> headless Chromium pass against the local server (`npx serve`).

---

## 3. New section (after)

Captured live from the running site after the change.

**Header:** eyebrow "VERIFIED BENCHMARK · 17 REPOSITORIES", title "Tested on real repositories".

**Headline metrics row (8):**

`17 Repositories tested` · `96,713 Files analyzed` · `10M+ Lines of code analyzed` ·
`27,459 Modules discovered` · `63,792 Dependency edges mapped` · `97.9% Avg context
reduction` · `9.55× Impact speedup (post-scan)` · `8.77× Investigation speedup`

**4 repository cards:**

| Repo | Health | Files | Modules | Edges | Scan | Context reduction | Unresolved | Impact |
|------|--------|------:|--------:|------:|-----:|------------------:|-----------:|-------:|
| Home Assistant | Partial | 25,893 | 9,709 | 36,013 | 494.8s | 98.73% | 59,473 · 62% | 100 |
| Django | Partial | 6,870 | 929 | 2,915 | 21.5s | 99.23% | 1,377 · 32% | 100 |
| VS Code | Partial | 14,892 | 7,563 | 13,228 | 33.2s | 98.65% | 67,338 · 84% | 100 |
| FastAPI | Partial | 2,753 | 73 | 159 | 2.9s | 99.32% | 560 · 78% | 85.8 |

**Before/after impact (Phase 136 → Phase 137):**

| Repo | Before | After | Δ |
|------|------:|-----:|---:|
| FastAPI | 23.2 | 85.8 | +62.6 |
| VS Code | 62.0 | 100 | +38.0 |
| Django | 65.1 | 100 | +34.9 |
| Home Assistant | 87.3 | 100 | +12.7 |

**CTA:** "Atlas was validated on real repositories ranging from **73 modules** to
**9,709 modules** and **36,013 dependency edges**."

---

## 4. Exact source of every displayed metric

All paths relative to `C:\J.A.R.V.I.S\local_jarvis\`.

### Headline metrics row

| Displayed | Value | Source |
|-----------|-------|--------|
| Repositories tested | 17 | `reports/atlas_evidence_package.md` L9 ("Repositories measured: 17") |
| Files analyzed | 96,713 | `atlas_evidence_package.md` L17 (Executive Evidence) |
| Lines of code | 10M+ (10,099,509) | `atlas_evidence_package.md` L17 |
| Modules discovered | 27,459 | `atlas_evidence_package.md` L17 |
| Dependency edges mapped | 63,792 | `atlas_evidence_package.md` L17 |
| Avg context reduction | 97.9% (97.91%) | `atlas_evidence_package.md` L21 |
| Impact speedup | 9.55× | `atlas_evidence_package.md` L23 (conservative, post-scan) |
| Investigation speedup | 8.77× | `atlas_evidence_package.md` L24 (conservative, post-scan) |

### Repository cards

Files / Modules / Edges / Scan time / Context reduction — from the Benchmark
Leaderboard table (`atlas_evidence_package.md` L116–L119) and cross-checked against
each `benchmarks/overnight_validation/raw/<repo>.json` (`scan_metrics`, `time_metrics`).
Unresolved imports + ratio — from `raw/<repo>.json` (`scan_metrics.unresolved_imports`,
`scan_metrics.unresolved_ratio`). Impact — Phase 137 generalization (see below).

| Repo | Metric | Value | Source |
|------|--------|-------|--------|
| Home Assistant | Files / Modules / Edges / Scan / Reduction | 25,893 / 9,709 / 36,013 / 494.804s / 98.73% | `atlas_evidence_package.md` L119; `raw/home_assistant.json` |
| | Unresolved / ratio | 59,473 / 0.6228 | `raw/home_assistant.json` L24, L27 |
| Django | Files / Modules / Edges / Scan / Reduction | 6,870 / 929 / 2,915 / 21.467s / 99.23% | `atlas_evidence_package.md` L117; `raw/django.json` |
| | Unresolved / ratio | 1,377 / 0.3208 | `raw/django.json` L24, L27 |
| VS Code | Files / Modules / Edges / Scan / Reduction | 14,892 / 7,563 / 13,228 / 33.238s / 98.65% | `atlas_evidence_package.md` L118; `raw/vscode.json` |
| | Unresolved / ratio | 67,338 / 0.8358 | `raw/vscode.json` L24, L27 |
| FastAPI | Files / Modules / Edges / Scan / Reduction | 2,753 / 73 / 159 / 2.934s / 99.32% | `atlas_evidence_package.md` L116; `raw/fastapi.json` |
| | Unresolved / ratio | 560 / 0.7789 | `raw/fastapi.json` L24, L27 |

Scan times are displayed rounded to one decimal (494.8s, 21.5s, 33.2s, 2.9s).

### Impact scores (cards + before/after)

The **after** value shown on each card and in the before/after visual is the **Phase 137
generalization impact score**:

| Repo | Before (Phase 136) | After (Phase 137) | Source |
|------|------:|-----:|--------|
| Home Assistant | 87.3 | 100.0 | `atlas_evidence_package.md` §4 L159 |
| Django | 65.1 | 100.0 | `atlas_evidence_package.md` §4 L160 |
| FastAPI | 23.2 | 85.8 | `atlas_evidence_package.md` §4 L161 |
| VS Code | 62.0 | 100.0 | `atlas_evidence_package.md` §4 L162 |

The "after" values are independently confirmed in `reports/phase137_semantic_generalization.md`
(leaderboard L31–L34: Django 100, Home Assistant 100, VS Code 100, FastAPI 85.8).

### CTA

| Displayed | Source |
|-----------|--------|
| "73 modules" (min) | FastAPI, `atlas_evidence_package.md` L116 |
| "9,709 modules … 36,013 dependency edges" (max) | Home Assistant, `atlas_evidence_package.md` L18 + L119 |

---

## 5. Graph health — how it was determined honestly

The overnight campaign's raw records contain **`"graph_health_label": null`** for every
repository (e.g. `raw/fastapi.json` L28) — the field was not populated in this run.
Rather than invent a tiered label, the website shows **Partial** for all four repos,
which is the measured reality: each has a non-zero unresolved-import ratio (32%–84%),
so none achieved full import resolution. The exact unresolved count and ratio are shown
on every card as the quantitative health signal.

This is consistent with the evidence package's own trust notes
(`atlas_evidence_package.md` L139, L197): "Unresolved imports remain a trust concern,
especially VS Code, Home Assistant, LangChain, OpenBB."

---

## 6. Honesty preservation

- **Graph health shown** — every card carries a Partial badge.
- **Unresolved imports shown** — exact count + ratio per repo, with a progress bar.
- **No 100% resolution claim** — the honesty note explicitly states Atlas does *not*
  claim 100% import resolution.
- **Weaknesses not hidden** — the note calls out that large repos (VS Code, Home
  Assistant) resolve fewer imports, and that Home Assistant is the slowest scan at
  494.8s (the slowest successful scan in the campaign, `atlas_evidence_package.md` L20).
- **Impact is the conservative generalization score** — FastAPI is shown as **85.8**,
  not the overnight proxy `impact_score` of 100 (`raw/fastapi.json` L43). The lower,
  more rigorous Phase 137 number was chosen deliberately.

---

## 7. Known source discrepancy (documented, not hidden)

The two evidence sources disagree on two **before** baselines:

- `atlas_evidence_package.md` §4: Home Assistant 87.3 → 100, VS Code 62.0 → 100.
- `reports/phase137_semantic_generalization.md` L11/L14: Home Assistant 100 → 100,
  VS Code 0.0 → 100.

The website uses the **evidence-package §4** baselines (87.3 and 62.0). They are the
consolidated package figures and match the values specified for this refresh. The
**after** values (100 / 100 / 85.8 / 100) are identical in both sources, so the headline
"after" capability is unambiguous.

---

## 8. Consistency changes made alongside the section

To avoid the page contradicting itself, these were updated to the same measured numbers:

- **Hero metric cards** → Home Assistant (9,709 / 36,013 / 494.8s), VS Code (7,563 /
  13,228 / 33.2s), FastAPI (73 / 159 / 2.9s); note now reads "across 17 repositories".
- **Gallery UI-preview mocks** (`index.html`, `js/app.js`) → VS Code 7,563 / 13,228;
  Django edge count 2,915; Django mock badge "watch" → "partial".
- **README.md** benchmark table → replaced Phase 116G table with the measured Phase
  137 + overnight numbers and aggregate line.

No other sections, product code, or scan logic were changed.

---

## 9. Success criteria check

A visitor now immediately sees:

1. **Tested on real repositories** — 17-repo headline row + 4 named open-source repos. ✓
2. **Scales to large codebases** — Home Assistant 9,709 modules / 36,013 edges; VS Code 7,563 modules. ✓
3. **Reduces context dramatically** — 97.9% average; 98–99% per repo. ✓
4. **Improved significantly between benchmarks** — before/after visual, +12.7 to +62.6. ✓
5. **Reports limitations honestly** — Partial badges, unresolved ratios, slowest-scan and no-100%-resolution disclosures. ✓

---

## 10. Deployment status

Changes are applied in the working copy (`C:\Users\babi2\jarvis_landing`) and synced to
the deploy repo (`C:\jarvis_landing`), where they are **staged but not committed/pushed**
(this refresh did not request deployment). Files changed in the deploy repo:
`index.html`, `css/style.css`, `js/app.js`, `README.md`. A commit + push to
`origin/main` will trigger the Vercel deployment when you give the go-ahead.

This report: `reports/website_benchmark_refresh.md`.
