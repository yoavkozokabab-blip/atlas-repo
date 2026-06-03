# Phase 134.2 — Route Copilot Impact Prompts Through the Semantic Resolver

**Date:** 2026-06-03
**Commit:** `phase134-2: route Copilot impact prompts through semantic target resolver`

---

## Root cause (confirmed)

The semantic resolver (`target_resolver.py`) and impact engine
(`impact_engine.analyze_impact`) worked when called directly, but the
**user-facing Copilot route did not invoke them**:

`api._answer_impact()` (reached from `/api/copilot/ask` → `copilot_ask` →
impact intent) did:
1. `target = _resolve_module_path(question)` — extracts only a literal `*.py`
   path or a module name that already appears in the text. For a concept prompt
   ("what breaks if I remove event bus") there is no path → returns `None`.
2. On `None` → returns the fallback `"Name a file or module…"`.
3. Even with a target, it called the OLD `impact()` (direct-importers only), not
   `change_impact_simulation()` (which runs exact → semantic-concept →
   architecture-symbol resolution).

So concepts never reached the resolver. A second, layout bug compounded it: the
concept keywords are slash-anchored (`/auth/`, `/recorder/`) and only matched
nested paths (`homeassistant/auth/…`), silently failing on top-level packages.

## Fix

1. **Prompt parsing** (`_extract_impact_concept`): strips the question wrapper so
   the resolver receives the bare concept. Handles: *what breaks if I remove/
   delete/change/disable X*, *what happens if I change X*, *impact of changing X*,
   *what depends on X*, *blast radius of X*, *remove/change/disable X*. Leading
   articles are stripped; "websocket support" is preserved as the concept.
2. **Route** (`_answer_impact` rewrite): builds candidate seeds `[literal_path,
   concept_text]` and calls `change_impact_simulation(seed)` for each (which runs
   exact → `resolve_concept_target` → `resolve_architecture_symbol`). Falls back
   only when **no** seed resolves. The fallback message now also names concepts.
3. **Intent routing**: `classify_copilot_question` also routes `remove/delete/
   disable/what depends on/get rid of` to impact.
4. **Layout-agnostic matching** (`target_resolver`): paths are slash-wrapped
   (`/{path}/`) before keyword matching, so `/auth/` matches both
   `homeassistant/auth/__init__.py` and `auth/middleware.py`.
5. **UI response** (`_copilot_envelope` `extra=`): the impact answer now carries
   `semantic_label`, `resolved_modules`, `resolved_symbols`, `direct_impact`,
   `indirect_impact`, `architectural_blast_radius`, `confidence_explanation`,
   `risky_areas`, `safe_areas`, `target`.

## Before / after

**Before** — 4/4 concept prompts failed via the Copilot route:
```
what breaks if I remove websocket support  → "Name a file or module…"
what breaks if I remove event bus          → "No target path could be resolved"
what breaks if I remove config entries     → fallback
what breaks if I remove recorder           → fallback
```

**After** — reference repo (top-level packages), via `/api/copilot/ask`:
```
what breaks if I remove authentication
  mode=impact  fallback=False  semantic_label="authentication"
  target=auth/middleware.py  resolved_modules=[auth/middleware.py, auth/session.py, auth/login.py]
  direct=2 indirect=0
```
(authentication resolving on a top-level `auth/` repo proves the slash-anchoring fix.)

**After** — Home Assistant, the exact user-facing prompts (`ATLAS_RUN_HA=1`, **6/6 pass**):

| Prompt | Resolves to |
|--------|-------------|
| what breaks if I remove websocket support | `components/websocket_api` |
| what breaks if I remove event bus | `core.py` / `helpers/event.py` (EventBus) |
| what breaks if I remove config entries | `config_entries.py` |
| what breaks if I remove recorder | `components/recorder` |
| what breaks if I remove authentication | `auth/*` |
| what breaks if I disable automations | `components/automation` |

Each returns `mode=impact`, **no fallback**, a `semantic_label`, non-empty
`resolved_modules`, and non-empty direct/indirect impact.

> A second resolver bug surfaced during HA validation: concept `symbols` include
> ubiquitous lifecycle methods (`async_setup_entry`, `async_register`,
> `async_unload_entry`) that match *every* integration, and the symbol bonus
> dominated the path keywords — so `recorder` and `config entries` first resolved
> to random components. Fixed in `resolve_semantic_target`: a module qualifies
> only via a **path signal** (keyword/anchor/related) when the concept has path
> keywords; symbols are a tiebreak bonus, with symbol-only fallback used only when
> no path candidate exists. (No concepts were added or removed.)

## Tests

`jarvis_desktop/tests/test_phase134_2_copilot_impact_routing.py`:
- pure `_extract_impact_concept` parsing + intent routing (fast),
- full Copilot route via `server.dispatch("/api/copilot/ask")` on the reference
  repo (fast, no HA scan needed),
- the exact Home Assistant prompts (opt-in: `ATLAS_RUN_HA=1`).

Run:
```bash
py -3 -m pytest jarvis_desktop/tests/test_phase134_2_copilot_impact_routing.py -q
# Home Assistant (slow):
set ATLAS_RUN_HA=1 && py -3 -m pytest jarvis_desktop/tests/test_phase134_2_copilot_impact_routing.py -q
```

## Limitations

- Concepts outside the curated `CONCEPT_TARGET_MAP` (e.g. "cache layer" on a repo
  with no cache concept) still fall back — by design, no new concepts were added.
- Resolution is static (import graph + symbol index); dynamic/string imports are
  not followed.
