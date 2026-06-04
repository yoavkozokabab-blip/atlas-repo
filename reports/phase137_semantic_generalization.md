# Phase 137 — Semantic Generalization Completion

## Executive summary

Phase 137 adds a framework-agnostic concept lexicon and generic resolver fallback (`impact_engine/concept_lexicon.py`, `resolve_generic_concept`) so cross-cutting concepts resolve from each repository's own structure. Home Assistant curated mappings are preserved; copilot impact accepts semantic hits outside the import graph.

## Current scores (priority repositories)

| Repository | Impact (before → after) | Overall | Status |
|---|---:|---:|---|
| Home Assistant | 100.0 → **100.0** (+0.0) | **100.0** | ok |
| Django | 65.1 → **100.0** (+34.9) | **100.0** | ok |
| FastAPI | 23.2 → **85.8** (+62.6) | **94.0** | ok |
| VS Code | 0.0 → **100.0** (+100.0) | **100.0** | ok |
| Atlas (local_jarvis) | 62.5 → **62.5** (+0.0) | **88.8** | ok |
| QuixBugs | 24.6 → **24.6** (+0.0) | **64.9** | ok |

### Success criteria

| Criterion | Result |
|---|---|
| VS Code impact > 80 | **PASS** (100.0) |
| FastAPI impact > 80 | **PASS** (85.8) |
| Django impact > 90 | **PASS** (100.0) |
| Home Assistant no regression | **PASS** (100.0) |

## Leaderboard (all scored repositories)

| Rank | Repository | Understanding | Impact | Investigation | Build | **Overall** |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Django | 100.0 | 100.0 | 100.0 | 100.0 | **100.0** |
| 2 | Home Assistant | 100.0 | 100.0 | 100.0 | 100.0 | **100.0** |
| 3 | VS Code | 100.0 | 100.0 | 100.0 | 100.0 | **100.0** |
| 4 | FastAPI | 93.0 | 85.8 | 100.0 | 100.0 | **94.0** |
| 5 | Atlas (local_jarvis) | 100.0 | 62.5 | 100.0 | 100.0 | **88.8** |
| 6 | QuixBugs | 65.0 | 24.6 | 100.0 | 81.2 | **64.9** |

## Semantic probe — 20 concept coverage matrix

| Concept | Coverage % | Success % | Failure % | Resolution failures |
|---|---:|---:|---:|---|
| configuration | 100.0 | 100.0 | 0.0 | — |
| routing | 100.0 | 100.0 | 0.0 | — |
| authorization | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| caching | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| database | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| middleware | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| logging | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| messaging | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| background_jobs | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| extensions | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| websockets | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| api_layer | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| persistence | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| validation | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| serialization | 83.3 | 83.3 | 16.7 | semantic_routing_failure:1 |
| authentication | 66.7 | 66.7 | 33.3 | semantic_routing_failure:2 |
| events | 66.7 | 66.7 | 33.3 | semantic_routing_failure:2 |
| scheduling | 66.7 | 66.7 | 33.3 | semantic_routing_failure:2 |
| state_management | 66.7 | 66.7 | 33.3 | semantic_routing_failure:2 |
| plugins | 66.7 | 66.7 | 33.3 | semantic_routing_failure:2 |

**Mean concept coverage:** 80.8% across probed repositories.

## Per-concept detail

### authentication

- **Success repos:** Atlas (local_jarvis), Django, Home Assistant, VS Code
- **Failed repos:** FastAPI, QuixBugs
- **Why it failed:** Fallback on 2 repo(s) — concept vocabulary or path signals did not match `authentication` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `authentication` (+5–10% coverage).

### events

- **Success repos:** Atlas (local_jarvis), Django, Home Assistant, VS Code
- **Failed repos:** FastAPI, QuixBugs
- **Why it failed:** Fallback on 2 repo(s) — concept vocabulary or path signals did not match `events` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `events` (+5–10% coverage).

### scheduling

- **Success repos:** Atlas (local_jarvis), Django, Home Assistant, VS Code
- **Failed repos:** FastAPI, QuixBugs
- **Why it failed:** Fallback on 2 repo(s) — concept vocabulary or path signals did not match `scheduling` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `scheduling` (+5–10% coverage).

### state_management

- **Success repos:** Atlas (local_jarvis), Django, Home Assistant, VS Code
- **Failed repos:** FastAPI, QuixBugs
- **Why it failed:** Fallback on 2 repo(s) — concept vocabulary or path signals did not match `state_management` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `state_management` (+5–10% coverage).

### plugins

- **Success repos:** Atlas (local_jarvis), Django, Home Assistant, VS Code
- **Failed repos:** FastAPI, QuixBugs
- **Why it failed:** Fallback on 2 repo(s) — concept vocabulary or path signals did not match `plugins` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `plugins` (+5–10% coverage).

### authorization

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `authorization` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `authorization` (+5–10% coverage).

### caching

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `caching` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `caching` (+5–10% coverage).

### database

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `database` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `database` (+5–10% coverage).

### middleware

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `middleware` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `middleware` (+5–10% coverage).

### logging

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `logging` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `logging` (+5–10% coverage).

### messaging

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `messaging` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `messaging` (+5–10% coverage).

### background_jobs

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `background_jobs` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `background_jobs` (+5–10% coverage).

### extensions

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `extensions` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `extensions` (+5–10% coverage).

### websockets

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `websockets` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `websockets` (+5–10% coverage).

### api_layer

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `api_layer` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `api_layer` (+5–10% coverage).

### persistence

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `persistence` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `persistence` (+5–10% coverage).

### validation

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `validation` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `validation` (+5–10% coverage).

### serialization

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code
- **Failed repos:** QuixBugs
- **Why it failed:** Fallback on 1 repo(s) — concept vocabulary or path signals did not match `serialization` in those layouts.
- **Improvement opportunity:** Expand lexicon aliases / platform path priors for `serialization` (+5–10% coverage).

### configuration

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code
- **Failed repos:** —
- **Why it failed:** —
- **Improvement opportunity:** Low — already generalizes well.

### routing

- **Success repos:** Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code
- **Failed repos:** —
- **Why it failed:** —
- **Improvement opportunity:** Low — already generalizes well.

## Failure taxonomy

- **semantic_routing_failure** — copilot fallback; concept not matched or no modules returned.
- **resolver_failure** — matched concept but empty module list.
- **Honest miss** — repository genuinely lacks the concept (expected on QuixBugs).

## Improvement roadmap (ROI-ranked)

| Priority | Improvement | Est. impact gain | ROI |
|---:|---|---:|---|
| 1 | Expand lexicon aliases / platform path priors for `authentication` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 2 | Expand lexicon aliases / platform path priors for `events` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 3 | Expand lexicon aliases / platform path priors for `scheduling` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 4 | Expand lexicon aliases / platform path priors for `state_management` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 5 | Expand lexicon aliases / platform path priors for `plugins` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 6 | Expand lexicon aliases / platform path priors for `authorization` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 7 | Expand lexicon aliases / platform path priors for `caching` (+5–10% coverage). | Medium | Quick lexicon / path priors |
| 8 | Expand lexicon aliases / platform path priors for `database` (+5–10% coverage). | Medium | Quick lexicon / path priors |

**Cross-repo targets:** lift mean concept coverage toward 85%; keep Home Assistant at 100% impact.

## Expected gains (next phases)

| Lever | Expected impact lift |
|---|---:|
| Lexicon alias expansion (authorization, messaging) | +4–8 pts mean impact |
| Platform path priors (prefer `src/vs/platform` over extensions) | +5–10 pts on TS repos |
| Framework adapters (Django/FastAPI/NestJS) | +8–12 pts |
| Cross-repo semantic learning | +10–15 pts long-term |

## Tests

```text
py -3 -m pytest jarvis_desktop/tests/test_phase137_semantic_generalization.py -q
py -3 -m pytest jarvis_desktop/tests/test_semantic_target_resolution.py -q
```

## Confirmation

- No billing / usage / pricing / admin changes in this phase.
- No Stripe or payment infrastructure touched.
- Semantic generalization only — resolver + copilot impact wiring + benchmarks.
