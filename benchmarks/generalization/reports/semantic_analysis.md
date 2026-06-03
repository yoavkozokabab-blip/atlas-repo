# Phase 136 — Semantic Generalization Analysis

Probed **20 canonical concepts** against **6 repositories** (Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code) through the real impact route.

## Every semantic resolution failure

| Prompt | Repository | Expected subsystem | Actual resolution result | Category |
|---|---|---|---|---|
| `what breaks if I remove middleware` | Atlas (local_jarvis) | middleware pipeline | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the logging layer` | Atlas (local_jarvis) | logging subsystem | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the event system` | Atlas (local_jarvis) | event bus / dispatcher | fallback — no target | semantic_routing_failure |
| `what breaks if I remove messaging` | Atlas (local_jarvis) | message queue / pub-sub | fallback — no target | semantic_routing_failure |
| `what breaks if I remove background jobs` | Atlas (local_jarvis) | task / worker queue | fallback — no target | semantic_routing_failure |
| `what breaks if I remove scheduling` | Atlas (local_jarvis) | scheduler | fallback — no target | semantic_routing_failure |
| `what breaks if I remove state management` | Atlas (local_jarvis) | state store | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the plugin system` | Atlas (local_jarvis) | plugin loader | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the api layer` | Atlas (local_jarvis) | API / endpoint layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove authorization` | Django | access control / permissions | fallback — no target | semantic_routing_failure |
| `what breaks if I remove caching` | Django | cache layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove configuration` | Django | config system | fallback — no target | semantic_routing_failure |
| `what breaks if I remove routing` | Django | router / URL dispatch | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the logging layer` | Django | logging subsystem | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the event system` | Django | event bus / dispatcher | fallback — no target | semantic_routing_failure |
| `what breaks if I remove messaging` | Django | message queue / pub-sub | fallback — no target | semantic_routing_failure |
| `what breaks if I remove background jobs` | Django | task / worker queue | fallback — no target | semantic_routing_failure |
| `what breaks if I remove scheduling` | Django | scheduler | fallback — no target | semantic_routing_failure |
| `what breaks if I remove state management` | Django | state store | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the plugin system` | Django | plugin loader | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the api layer` | Django | API / endpoint layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove request validation` | Django | input validation | fallback — no target | semantic_routing_failure |
| `what breaks if I remove authentication` | FastAPI | auth / identity | fallback — no target | semantic_routing_failure |
| `what breaks if I remove caching` | FastAPI | cache layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove configuration` | FastAPI | config system | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the logging layer` | FastAPI | logging subsystem | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the event system` | FastAPI | event bus / dispatcher | fallback — no target | semantic_routing_failure |
| `what breaks if I remove messaging` | FastAPI | message queue / pub-sub | fallback — no target | semantic_routing_failure |
| `what breaks if I remove background jobs` | FastAPI | task / worker queue | fallback — no target | semantic_routing_failure |
| `what breaks if I remove scheduling` | FastAPI | scheduler | fallback — no target | semantic_routing_failure |
| `what breaks if I remove state management` | FastAPI | state store | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the plugin system` | FastAPI | plugin loader | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the api layer` | FastAPI | API / endpoint layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove persistence` | FastAPI | ORM / storage | fallback — no target | semantic_routing_failure |
| `what breaks if I remove request validation` | FastAPI | input validation | fallback — no target | semantic_routing_failure |
| `what breaks if I remove routing` | Home Assistant | router / URL dispatch | fallback — no target | semantic_routing_failure |
| `what breaks if I remove middleware` | Home Assistant | middleware pipeline | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the logging layer` | Home Assistant | logging subsystem | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the event system` | Home Assistant | event bus / dispatcher | fallback — no target | semantic_routing_failure |
| `what breaks if I remove background jobs` | Home Assistant | task / worker queue | fallback — no target | semantic_routing_failure |
| `what breaks if I remove scheduling` | Home Assistant | scheduler | fallback — no target | semantic_routing_failure |
| `what breaks if I remove state management` | Home Assistant | state store | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the plugin system` | Home Assistant | plugin loader | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the api layer` | Home Assistant | API / endpoint layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove persistence` | Home Assistant | ORM / storage | fallback — no target | semantic_routing_failure |
| `what breaks if I remove request validation` | Home Assistant | input validation | fallback — no target | semantic_routing_failure |
| `what breaks if I remove authentication` | QuixBugs | auth / identity | fallback — no target | semantic_routing_failure |
| `what breaks if I remove authorization` | QuixBugs | access control / permissions | fallback — no target | semantic_routing_failure |
| `what breaks if I remove caching` | QuixBugs | cache layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove configuration` | QuixBugs | config system | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the database layer` | QuixBugs | persistence / database | fallback — no target | semantic_routing_failure |
| `what breaks if I remove routing` | QuixBugs | router / URL dispatch | fallback — no target | semantic_routing_failure |
| `what breaks if I remove middleware` | QuixBugs | middleware pipeline | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the logging layer` | QuixBugs | logging subsystem | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the event system` | QuixBugs | event bus / dispatcher | fallback — no target | semantic_routing_failure |
| `what breaks if I remove messaging` | QuixBugs | message queue / pub-sub | fallback — no target | semantic_routing_failure |
| `what breaks if I remove background jobs` | QuixBugs | task / worker queue | fallback — no target | semantic_routing_failure |
| `what breaks if I remove scheduling` | QuixBugs | scheduler | fallback — no target | semantic_routing_failure |
| `what breaks if I remove state management` | QuixBugs | state store | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the plugin system` | QuixBugs | plugin loader | fallback — no target | semantic_routing_failure |
| `what breaks if I remove extensions` | QuixBugs | extension system | fallback — no target | semantic_routing_failure |
| `what breaks if I remove websocket support` | QuixBugs | websocket transport | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the api layer` | QuixBugs | API / endpoint layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove persistence` | QuixBugs | ORM / storage | fallback — no target | semantic_routing_failure |
| `what breaks if I remove request validation` | QuixBugs | input validation | fallback — no target | semantic_routing_failure |
| `what breaks if I remove serialization` | QuixBugs | (de)serialization layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove authorization` | VS Code | access control / permissions | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the logging layer` | VS Code | logging subsystem | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the event system` | VS Code | event bus / dispatcher | fallback — no target | semantic_routing_failure |
| `what breaks if I remove background jobs` | VS Code | task / worker queue | fallback — no target | semantic_routing_failure |
| `what breaks if I remove scheduling` | VS Code | scheduler | fallback — no target | semantic_routing_failure |
| `what breaks if I remove state management` | VS Code | state store | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the plugin system` | VS Code | plugin loader | fallback — no target | semantic_routing_failure |
| `what breaks if I remove the api layer` | VS Code | API / endpoint layer | fallback — no target | semantic_routing_failure |
| `what breaks if I remove persistence` | VS Code | ORM / storage | fallback — no target | semantic_routing_failure |
| `what breaks if I remove request validation` | VS Code | input validation | fallback — no target | semantic_routing_failure |

## Top 20 semantic concepts — coverage across repositories

| Concept | Expected subsystem | Coverage % | Succeeds in | Fails in |
|---|---|---:|---|---|
| database | persistence / database | 83.3% | Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code | QuixBugs |
| extensions | extension system | 83.3% | Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code | QuixBugs |
| websockets | websocket transport | 83.3% | Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code | QuixBugs |
| serialization | (de)serialization layer | 83.3% | Atlas (local_jarvis), Django, FastAPI, Home Assistant, VS Code | QuixBugs |
| authentication | auth / identity | 66.7% | Atlas (local_jarvis), Django, Home Assistant, VS Code | FastAPI, QuixBugs |
| authorization | access control / permissions | 50.0% | Atlas (local_jarvis), FastAPI, Home Assistant | Django, QuixBugs, VS Code |
| caching | cache layer | 50.0% | Atlas (local_jarvis), Home Assistant, VS Code | Django, FastAPI, QuixBugs |
| configuration | config system | 50.0% | Atlas (local_jarvis), Home Assistant, VS Code | Django, FastAPI, QuixBugs |
| routing | router / URL dispatch | 50.0% | Atlas (local_jarvis), FastAPI, VS Code | Django, Home Assistant, QuixBugs |
| middleware | middleware pipeline | 50.0% | Django, FastAPI, VS Code | Atlas (local_jarvis), Home Assistant, QuixBugs |
| messaging | message queue / pub-sub | 33.3% | Home Assistant, VS Code | Atlas (local_jarvis), Django, FastAPI, QuixBugs |
| persistence | ORM / storage | 33.3% | Atlas (local_jarvis), Django | FastAPI, Home Assistant, QuixBugs, VS Code |
| validation | input validation | 16.7% | Atlas (local_jarvis) | Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| logging | logging subsystem | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| events | event bus / dispatcher | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| background_jobs | task / worker queue | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| scheduling | scheduler | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| state_management | state store | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| plugins | plugin loader | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |
| api_layer | API / endpoint layer | 0.0% | — | Atlas (local_jarvis), Django, FastAPI, Home Assistant, QuixBugs, VS Code |

**Mean concept coverage across repositories: 36.7%.**

## Per-repository concept resolution

| Repository | Concepts resolved | Resolution % |
|---|---:|---:|
| Atlas (local_jarvis) | 11/20 | 55.0% |
| VS Code | 10/20 | 50.0% |
| Home Assistant | 9/20 | 45.0% |
| Django | 7/20 | 35.0% |
| FastAPI | 7/20 | 35.0% |
| QuixBugs | 0/20 | 0.0% |

## Semantic Generalization Roadmap

Each technique's gain is an estimated lift to the **impact capability** score (the lowest-confidence capability); they stack with diminishing overlap.

### Quick wins (<1 day)

- **Concept alias/synonym expansion (logging↔logger↔log, ws↔websocket, db↔orm)** — _+4 impact pts._ Most fallbacks are vocabulary misses, not missing code — cheap dictionary + stemming.
- **Path-pattern auto-discovery (derive concept→dir patterns from the repo's own tree)** — _+6 impact pts._ Replace the fixed HA slash-anchor list with patterns mined from each repo's folders (auth/, cache/, routing/, middleware/, events/).

### Medium effort (1-3 days)

- **Concept clustering (group modules by shared imports/names into concept buckets)** — _+8 impact pts._ Lets a query land on a cluster centroid even when no single file name matches.
- **Architecture symbol mining (index classes/decorators/calls → concepts)** — _+10 impact pts._ Mine @app.middleware, Router, Session, Cache, EventBus etc. so resolution uses real symbols, not just paths — directly fixes FastAPI/VSCode where structure ≠ HA.

### Major effort (>3 days)

- **Framework-aware adapters (Django/FastAPI/React/NestJS conventions)** — _+12 impact pts._ Per-framework priors (Django apps, FastAPI routers/Depends, React reconciler) for the highest-traffic ecosystems.
- **Cross-repo semantic learning (concept→structure priors transferred across repos)** — _+15 impact pts._ An unseen repo inherits learned concept signatures, so coverage no longer depends on a hand-curated, HA-shaped map.

### Estimated impact-score gain by tier

| Tier | Techniques | Est. impact gain |
|---|---|---:|
| Quick wins | alias expansion + path-pattern discovery | +10 |
| Medium | concept clustering + architecture symbol mining | +18 |
| Major | framework adapters + cross-repo semantic learning | +27 |
| **Cumulative (capped at ~90)** | all of the above | **up to +55** |

### Projected per-repository impact lift

Projection: quick+medium tiers raise low-coverage repos toward the resolution rate Home Assistant already enjoys; majors close the rest. Targets are deliberately conservative (70+/85+/80+), not 100.

| Repository | Current impact | Target impact | Lever |
|---|---:|---:|---|
| FastAPI | 23.2 | 70+ | path-pattern + symbol mining (clear router/Depends conventions) |
| Django | 65.1 | 85+ | framework adapter (apps/ORM/middleware are highly conventional) |
| VS Code | 62.0 | 80+ | symbol mining (extension host / command registry are named symbols) |
| Home Assistant | 87.3 | ~87 (already) | not a target — goal is generalization, not HA |

**Goal restated:** maximise cross-repository generalization. The win condition is lifting FastAPI/Django/VS Code/React/NestJS — not nudging Home Assistant higher.
