# Ask Atlas — Checkpoint Review

**Continued from:** `43c5d5949da9c14ddb26b777675b32f1e605974d`
**Scope:** Redesign **Ask Atlas only.** No changes to Home, persistence, MCP, repository scanning, backend logic, routing, installer, or website.
**Goal:** Make an Ask Atlas answer read like a senior engineer's analysis report — GitHub Security / Linear / Raycast AI / Stripe Dashboard — never a chat.

---

## 1. How this was done without touching the backend

The `/api/copilot/ask` response already carries a rich, structured `report` object (executive summary, direction items, confidence, evidence, ranked files, `cannot_conclude`, `next_action`) for the analysis modes, plus mode-specific fields for `comparison` and `impact`. The old front-end under-used it: one flat `renderStructuredReportHtml()` printed cyan-labelled sections with plain `<li>` lists.

So this is a **pure front-end presentation change**, delivered as two new, fully-scoped files:

| File | Role |
|---|---|
| `atlas_desktop/static/ask_report.js` | Overrides the **Ask-only** globals (`renderCopilotAnswer`, staged loading, empty state) *after* `app.js` loads. Consumes the existing response verbatim. Degrades to the plain answer on any error — never throws. |
| `atlas_desktop/static/ask_report.css` | All styling, namespaced under `.axr` / `#copilotAnswer` so it cannot leak into Home or other views. |

`index.html` gains **4 additive lines** (two `<link>`, one `<script>`, and the pre-existing `premium.css` link). **Zero** changes to `app.js`, `atlas_zero_friction.js`, or any Python. The shared `renderStructuredReportHtml()` (used by Plan/Debug/Impact views) is deliberately left untouched. Reverting is deleting two files and four lines.

> **Screenshots:** the sandboxed browser pane in this environment cannot rasterize (`screenshot`/`zoom` time out, though the page is fully script-responsive). Rather than paste fabricated images, every "after" claim below is backed by **live computed-DOM measurements** read from the running app against a real loaded repository (the Medium demo, 18 files / 6 subsystems) and synthetic fixtures for each mode. Section 8 lists exactly what was measured.

---

## 2. Part 1 — Information hierarchy (implemented)

Every answer now renders in this fixed order, top to bottom:

1. **Executive Summary** — one paragraph, 19px, ink-strong. The sentence the eye lands on first.
2. **Verdict** — confidence pill (High/Med/Low) + risk pill (High/Med/Low), color-coded, with an expandable "Why this verdict".
3. **Key Findings** — 3–8 bullets from `report.direction.items`.
4. **Evidence** — strongest 3 as cards, the rest behind "N more evidence".
5. **Relevant Files** — ranked cards (top 4 + "N more files").
6. **Dependency Relationships** — *only if applicable* (comparison → shared/different/missing; impact → risk dashboard).
7. **Unknowns** — `cannot_conclude` / limitations, amber-marked.
8. **Recommended Next Step** — the single `next_action`, with **exactly one** primary CTA.

Mode-aware suppression avoids duplication: `comparison` hides Key Findings and Unknowns (they live in the comparison columns); `impact` swaps the dependency block for a dashboard.

## 3. Part 2 — Visual hierarchy

- Borders reduced to **hairlines between sections only**; the old per-section boxes are gone.
- Card padding `clamp(20px,3vw,34px)`; 24px section rhythm; content capped at **74ch** for readability.
- Type hierarchy: 19px summary → 15px next-step → 14.5px body → 11px small-caps eyebrows.
- Secondary detail (extra evidence, extra files, verdict reasoning) is hidden in native `<details>` until expanded.

## 4. Part 3 — Evidence cards

Each evidence item is a card showing **File** (mono), **Symbol** (parsed from the signal), **Why it matters**, and a **Copy path** control. Signals like `path.py: symA, symB` are parsed into file + symbol. Cards lift on hover; the copy control confirms inline ("Copied").

*(There is no OS file-open without a backend change, so "quick open" copies the exact path — honest and directly useful, since Atlas is a companion to coding agents that take pasted paths.)*

## 5. Part 4 — Relevant files

Ranked **cards**, not chips: two-digit rank · path (mono) · reason · risk tag · Copy. Importance is the rank order from `ranked_files`.

## 6. Part 5 — Comparison answers

`comparison` mode renders three columns — **Shared logic**, **Different logic**, **Missing evidence** — built from `res.comparison.shared_modules` / `only_a` / `only_b` and `report.cannot_conclude`, with descriptive notes plus mono module chips. Collapses to one column on mobile.

## 7. Part 6 — Risk answers

`impact` mode renders a **dashboard**: four stat tiles (Risk · Blast radius · Direct importers · Confidence, color-coded), then Affected modules and Highest-risk areas as chips, then the single recommendation.

## 8. Parts 7–9 — Loading, empty state, micro-interactions

- **Loading:** a `MutationObserver` on the loading element cycles **"Understanding repository… → Finding evidence… → Building report…"** with per-stage done/active states and a spinner (no wrapping of the fetch, so it's robust to early returns).
- **Empty state:** teaching copy + capability chips (Understand · Locate · Impact · Compare · Risk) + **5 example-prompt cards** that dispatch real questions on click.
- **Micro-interactions:** card hover-lift, keyboard-operable cards (`<button>`), one consistent focus ring, inline copy confirmation, native expand/collapse.

### What was verified live (against the running app)

| Check | Result |
|---|---|
| Section order (real `repository_understanding`) | Exec → Verdict → Key findings → Evidence → Relevant files → Next step ✓ |
| Real `repository_understanding` query | 3 evidence cards, 8 ranked file cards, verdict "High confidence / Low risk", 1 CTA ✓ |
| `comparison` fixture | 3 columns (Shared/Different/Missing); Key Findings suppressed ✓ |
| `impact` (synthetic) | Tiles Risk=High · Blast radius=20 · Direct=12 · Confidence=Medium ✓ |
| `impact` (real, unresolved target) | Degrades gracefully to dashboard + Unknowns + Next step ✓ |
| Empty state | 5 example cards + 5 capability chips + lead ✓ |
| Staged loading | 3 staged messages + spinner ✓ |
| Exactly one primary | Next-step CTA is action-blue; follow-up actions demoted to transparent ✓ |
| Mobile (375px) | Comparison & evidence grids → 1 col; **no horizontal overflow**; card fits ✓ |
| 1024px + 125% zoom | No overflow; layout holds ✓ |
| Dark surface | `rgb(18,22,27)` (`--atlas-surface-1`); app is dark-native ✓ |
| Guest mode | Renderer has no auth dependency; identical output ✓ |
| Tests | `grounded_analysis`, `copilot`, `copilot_impact_routing`, `grounding` → **58 passed, 6 skipped**; `home_state` + `launch_readiness` → **10 passed** ✓ |

## 9. Part 10 — Before / After

| Aspect | Before | After |
|---|---|---|
| Overall form | One flat "beginner-plan" card, cyan uppercase labels | 8-section analyst document with clear hierarchy |
| Verdict | A line of text | Color-coded confidence + risk pills, expandable reasoning |
| Evidence | Plain `<li>` bullets | Clickable cards: file · symbol · why · copy |
| Relevant files | Bulleted paths / chips | Ranked cards: rank · path · reason · risk · copy |
| Comparison | One long paragraph | Shared / Different / Missing columns |
| Impact | Flat hierarchy list | 4-tile risk dashboard + chips |
| Loading | Static "Analyzing repository…" | 3 staged premium messages + spinner |
| Empty state | Placeholder sentence | Teaching state + 5 example-prompt cards |
| Primary action | Several equal buttons | Exactly one primary CTA; rest demoted |
| Reads like | ChatGPT answer | Linear / Stripe / GitHub Security report |

---

## 10. Remaining weaknesses

1. **"Open file" is copy-path**, not a true editor open — that needs a backend/OS bridge, which is out of scope. Honest and useful, but not a real jump-to-definition.
2. **Symbol extraction is heuristic.** Evidence signals aren't a structured file/symbol pair, so parsing is best-effort; some cards show the signal as the file with an empty symbol.
3. **Key Findings depth varies.** Non-comparison modes supply 2–3 `direction.items`; the report shows what's grounded rather than padding to 8.
4. **Dependency graph is textual.** Section 6 lists shared/divergent modules but does not draw the edges — a small inline graph would raise it further.
5. **No rasterized screenshots** in this environment; a designer should do a final eyes-on pass on real hardware.
6. **Impact in Ask mode has no `report`**, so its verdict reasoning is thinner than the analysis modes (dashboard only).

## 11. Estimated improvement in first impression

On the specific "does this feel like a senior engineer's report vs. a chatbot" axis:

| | Before | After |
|---|---:|---:|
| Looks like an analysis report (not chat) | 3 / 10 | 9 / 10 |
| Scannability / hierarchy | 4 / 10 | 9 / 10 |
| Trust (verdict + honest unknowns) | 5 / 10 | 9 / 10 |
| Evidence usefulness (clickable, cited) | 4 / 10 | 8 / 10 |
| One obvious next action | 4 / 10 | 9 / 10 |
| **First-impression premium feel** | **4 / 10** | **9 / 10** |

**Net:** a developer's first Ask Atlas answer now opens with a bold executive summary, a color-coded verdict, cited evidence cards, ranked files, and a single clear next step — a document a senior engineer would hand you, not a chat reply. The remaining distance to 10 is a real editor-open bridge and an inline dependency graph, both of which require capabilities beyond this presentation-only checkpoint.

## 12. What changed on disk

- **New:** `atlas_desktop/static/ask_report.js`, `atlas_desktop/static/ask_report.css`
- **Edited:** `atlas_desktop/static/index.html` (4 additive `<link>`/`<script>` lines)
- **Untouched:** all JavaScript logic, all backend, routing, scanning, persistence, MCP, Home, installer, website.
