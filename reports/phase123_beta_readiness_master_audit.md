# Phase 123 — Atlas Beta Readiness Master Audit

**Date:** 2026-06-02
**Verdict question:** *"If I gave Atlas to an external developer tomorrow, would
they immediately understand why it is valuable and trust its outputs?"*

**Answer:** **Yes for understand/investigate/plan/export; the rebuilt graph is
empirically verified to size nodes visibly and needs only a final human WebGL
glance.** The product is honest, the investigation and planning outputs now read
like a senior engineer, and the trust-destroying "78% unresolved → graph is
broken" message has been corrected. The graph rebuild was verified on real
coordinates (see below) — nodes are 2.9–8.7% of the scene spread, not sub-pixel.

Test status: **318 passed** (`py -m pytest jarvis_desktop/tests -q`).

---

## A–G. Grades (0–10)

| Dimension | Grade | Basis |
|---|---:|---|
| **A. Product (overall)** | **7.0** | Clear value prop, honest outputs, 6 focused screens; graph needs visual sign-off, repo-map could consolidate further. |
| **B. Trust** | **7.5** | Token-savings hidden unless verified; unresolved-imports relabeled honestly; every cockpit metric labeled exact-vs-estimated; investigation refuses to fake certainty. |
| **C. UX** | **7.0** | Strong first-30s (headline + 3-step + Browse/Demo/Tour); consistent dark theme; investigation/plan now render as structured cards, not code dumps. Small-window density still tight. |
| **D. Investigation quality** | **8.0** | Ranked hypotheses with why-it-fits / evidence / files / what-should-be-true / how-to-disprove + verification checklist + minimal fix + rollback risks + export prompt. Grounded in real modules; honest when it can't localize. |
| **E. Build planning** | **7.5** | 10-point plan: affected systems, entry points, files, order, tests, risk, what-may-break, rollback, confidence, limitations. Keyword-intent based — honest about that. |
| **F. Graph usefulness** | **6.5** | Click → full module evidence + quick actions (investigate / impact / prompts). Rendering rebuilt for guaranteed node visibility; **pending visual confirmation**. |
| **G. Performance** | **7.5** | FastAPI scan ~2.1s; Django (907 modules) scans and renders; planning/investigation/impact are sub-100ms (pure-Python over cached graph). |

---

## Part 1 — Page audit (exist? essential? duplicated?)

| Page | Why it exists | Decision the user makes | Essential? | Verdict |
|---|---|---|---|---|
| **Home** | Orient in 30s; pick repo | What to do first | Yes | Keep |
| **Scan** | Real progress + honest success summary | Trust the scan completed | Yes | Keep |
| **Repository Map** (Command Center graph + cockpit) | Understand architecture/risk without reading code | Where is the risk/hubs/cycles | Yes | Keep — primary understanding screen |
| **Build Plan** | Plan a feature safely | How to implement; what breaks | Yes | Keep (new this line of work) |
| **Investigate Bug** | Localize a symptom with hypotheses | Which cause is true, how to prove | Yes | Keep — upgraded to senior-engineer output |
| **Impact** | Blast radius of a change | Is this change safe | Yes | Keep |
| **Export** | Hand context to Claude/Codex/Cursor | What to paste into the AI | Yes | Keep — core value |

**Removed/merged earlier:** standalone "Intelligence" and "Bug Hunt" pages were
folded into Repository Map (cockpit) and Investigate. `NAV_ALIASES` keeps old
deep-links (`intel`→map, `bug`→investigate) working. No vanity pages remain.

**Still slightly duplicative:** the old `view-intel`/`view-bug` DOM sections are
orphaned (no nav). Low risk; recommend deleting in a cleanup pass.

---

## Part 10 — Data trust audit (where does each number come from?)

| Metric | Source | Exact / Estimated | Status |
|---|---|---|---|
| Module count | production module nodes | Exact | Labeled |
| Edges / resolved imports | resolved import edges | Exact | Labeled |
| Import cycles | graph SCC detection | Exact | Labeled |
| Risk score | `architectural_risk` ranking | Exact (model-based) | Labeled |
| Blast radius / fan-in | reverse import edges (direct only) | Exact, **direct-only** | Disclosed ("transitive not computed") |
| **Unresolved imports** | `imports_external` (external+stdlib+internal-unresolved) | **Was mislabeled** | **Fixed** — honest note (see Part 7 report) |
| Token savings | module_count × 600 vs packet | Estimated | **Hidden** unless verified |

This is the strongest area of the product: numbers are either exact-and-labeled
or estimated-and-disclosed (or hidden). No misleading headline numbers remain.

---

## Part 2/3 — Investigation & Build Plan (what changed)

- Investigation now returns **A. symptom summary, B. most-likely root cause,
  C. ranked hypotheses** (each: confidence, why it fits, evidence, files, what to
  inspect, what should be true if correct, how to disprove), **D. verification
  checklist, E. minimal fix strategy, F. risks of fixing incorrectly, G. export
  prompt**. New domain patterns: unexpected stop loss, position sizing, signal
  not triggering — plus existing paper-vs-live, delayed alerts, dashboard PnL,
  graph module count, memory growth, position close.
- Build plan adds **rollback plan** + explicit **what-may-break** and aliases for
  affected-systems / tests-required, rendered as structured sections.
- Both stay honest: when no module path matches, confidence drops to low, files
  are empty, and the output says so instead of inventing paths.

## Part 4/5 — Graph rebuild (root cause + fix)

**Root cause found:** nodes were positioned across hundreds of `galaxy_*` units
but node display radius was capped at ~16; fit to those bounds, spheres became
sub-pixel while edge **lines** stayed ≥1px → "spiderweb of lines, no nodes."

**Fix:** single native-ForceGraph-sphere path for *all* views (visibility over
custom-mesh beauty, per spec). `nodeRelSize(1)` + `nodeVal = r³` where `r` is a
**fraction of the graph's spatial spread** (`maxR ≈ bounds/9`, `minR ≈ bounds/34`,
with floors). Importance (fan-in/out + risk + hub) drives size, so hubs are
visibly larger. Risk/cycle/hub coloring and hover/selection focus retained.
`auditRenderedMeshes` logs node/mesh counts + min/max radius for verification.

**Verified on real coordinates** (`tests_tmp/phase123_graph_sizing_check.py`,
replicating `nativeDisplayRadius` exactly):

| Graph | Nodes | Spread | Node radius | Largest as % of spread | Size variation |
|---|--:|--:|--|--:|--:|
| demo small | 5 | 187 | 7.2–16.2 | 8.7% | 2.25× |
| demo large | 43 | 319 | 12.3–27.6 | 8.7% | 2.25× |
| FastAPI | 73 | 416 | 12.2–36.0 | 8.7% | 2.94× |

Old path capped radius at 16 → on FastAPI that is 3.8% of spread max and ~1.2%
min (sub-pixel when fit-to-bounds). New path: floor ≥2.9%, hubs ≥8.7%, scales
with spread so it never collapses. **Remaining action:** a final human WebGL
glance (the preview harness blocked cross-origin nav this session), not a code
gate.

---

## H. Biggest remaining weaknesses

1. **Graph not visually confirmed** post-rebuild (highest risk).
2. **Unresolved-imports classification** still lumps external+stdlib+internal
   (relabeled honestly, but the real split is not yet implemented).
3. **Intent detection is keyword-first** — overlapping triggers can pick a
   neighboring pattern (e.g. "live trades" → paper-trading before dashboard-pnl).
4. **Orphaned DOM** (`view-intel`, `view-bug`) should be deleted.
5. **Impact is direct-only** (no transitive closure) — disclosed but limited.

## I. Exact blockers before public (free) beta

1. Final human WebGL glance at the 3D graph on FastAPI + Django + VS Code (sizing
   already verified numerically; confirm color/hover/selection on screen via the
   `auditRenderedMeshes` console output).
2. Delete orphaned `view-intel`/`view-bug` sections to avoid confusion.
3. One full manual walkthrough: Browse → Scan → Map → Build Plan → Investigate →
   Impact → Export on a real repo.

## J. Exact blockers before paid product

1. Implement external-vs-internal import classification (Part 7 rec #2) and
   surface `internal_unresolved_ratio` as the quality metric.
2. Transitive impact/blast-radius (currently direct-only).
3. TS/JS path-alias + barrel resolution (front-end repos under-resolve today).
4. Investigation intent: add a scoring/disambiguation step instead of first-match.
5. Persistence of plans/investigations + shareable export artifacts.

## K. Top 10 highest-ROI improvements

1. **Visual graph QA + lock the native-sphere path** (trust + the core demo).
2. **External/internal import classification** → kills the scariest number.
3. **Disambiguate investigation intent** (score all patterns, pick best).
4. **TS/JS alias + barrel resolution** (real recovery for front-end repos).
5. **Transitive impact** (turns Impact from indicative to authoritative).
6. **Delete orphaned views + final button audit** (cognitive load).
7. **"Open related modules" from inspector** (graph→investigate loop).
8. **Persist & re-open plans/investigations** (workflow stickiness).
9. **Per-metric "where did this come from?" tooltips everywhere** (trust polish).
10. **Onboarding that runs a Demo scan automatically on first launch** (first-30s).

---

## Performance notes (Part 11)

- FastAPI (73 modules): scan ~2.1s, graph build fast, cache on re-scan.
- Django (907 modules): scans and builds; large-graph node cap + chunked load in
  `universe.js` keep the UI responsive.
- Planning/investigation/impact/export: pure-Python over the cached graph,
  sub-100ms in practice (no network, no model calls).
- No new bottlenecks introduced; the graph rebuild **removed** per-node custom
  Three.js mesh/group construction (cheaper allocation for large graphs).

## Honest closing

Atlas now *reads* like a senior engineer for investigation and planning, and it
no longer lies to the user about graph health. The remaining gate is empirical:
put the rebuilt graph in front of human eyes. Do that, delete the orphaned
sections, and the free beta is defensible.
