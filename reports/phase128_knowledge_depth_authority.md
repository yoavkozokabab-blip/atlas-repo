# Phase 128 — Knowledge Depth and Authority Upgrade

## Summary

Phase 128 upgrades the Atlas Knowledge Engine from broad template packs (~1,584 concepts) to **154 architect-grade curated concepts** without adding thousands of new generated entries. Curated YAML under `atlas_knowledge/concepts/<domain>/` **overrides** JSON pack templates at load time (YAML loads after packs).

## Deliverables

| Item | Result |
|------|--------|
| Curated / upgraded concepts | **154** YAML files |
| Source-backed concepts | **52** (`concept_quality_score: source_backed`) |
| Curated deep | **102** |
| Quality tiers | `generated_template`, `curated_basic`, `curated_deep`, `source_backed` |
| Override behavior | Pack concepts tagged `generated_template`; curated YAML wins on same `concept_id` |
| UI | Build/Investigate domain panel shows **Local generated** / **Curated** / **Source-backed** pills |
| Build plan | Tie-break prefers higher quality; exports include knowledge quality line |
| Investigate | Adds limitation when match is template-only |
| Web retrieval | **Disabled** (unchanged from Phase 127) |

## Architecture

```
Load order: legacy → packs (generated_template) → YAML concepts (curated) → cache
```

- `atlas_knowledge/quality.py` — ranks, UI labels, confidence boost, shallow detection
- `atlas_knowledge/concept_builder.py` — structured concept dict builder
- `atlas_knowledge/phase128_catalog.py` — 150+ concept definitions (source-backed + curated-deep)
- `atlas_knowledge/tools/generate_phase128_curated.py` — exports catalog to per-domain YAML
- `schema.py` — `concept_quality_score`, `when_to_use`, `implementation_strategies`, security/performance risks
- `engine.py` — quality-aware matching, `knowledge_block` fields, investigate warnings, prompt sections

## Top domains covered (sample)

- **Security:** JWT, OAuth2, RBAC, CSRF, XSS, SQL injection, secrets, TLS
- **Backend / APIs:** REST, GraphQL, gRPC, rate limiting, webhooks, idempotency, health checks
- **Databases:** PostgreSQL, migrations, indexes, pooling, transactions, Redis
- **Distributed systems:** circuit breaker, retries, queues, sagas, CQRS, event sourcing
- **Observability:** structured logging, tracing, metrics, monitoring
- **Cloud / CI:** Docker, Kubernetes, Terraform, Helm, Lambda, CI/CD pipelines
- **Trading:** EMA, backtest/live divergence, indicators
- **AI:** OpenAI API, RAG pipeline
- **Testing:** unit, integration

## References policy

Source-backed concepts cite **official documentation, RFCs, or vendor docs** only (no blog URLs). Examples: RFC 7519 (JWT), OAuth 2.0 IETF drafts, PostgreSQL docs, Stripe API reference, Kubernetes docs.

## Regeneration

From `local_jarvis`:

```powershell
py -3 jarvis_desktop/atlas_knowledge/tools/generate_phase128_curated.py
```

Manifest: `atlas_knowledge/curated_manifest_phase128.json`

## Tests

`jarvis_desktop/tests/test_phase128_knowledge_depth.py` — manifest counts, YAML override, quality ranking, deep concept fields, build/investigate integration.

## Acceptance checklist

- [x] ≥150 curated concepts
- [x] ≥50 source-backed concepts
- [x] Curated overrides packs
- [x] Generated concepts remain with lower-depth marking
- [x] No live web retrieval / API calls in this phase
- [x] UI and exports show knowledge quality
