# Phase 127 — Atlas Knowledge Engine

**Version:** `phase127-atlas-knowledge-engine`

## Summary

Atlas now ships a **standalone local knowledge base** at `jarvis_desktop/atlas_knowledge/` that loads **without any repository scan**. The Phase 125 inline registry is preserved as legacy seed data; **1,573+ pack concepts** plus curated YAML (EMA, JWT) provide broad coverage.

## Architecture

```
atlas_knowledge/
  concepts/          # Curated YAML (high authority detail)
  packs/             # Generated JSON packs (scale)
  taxonomy/          # Domain taxonomy
  indexes/           # alias_index.json (built at load)
  cache/             # Retrieved/cached concepts (reuse)
  schema.py          # ConceptRecord + validation
  loader.py          # Load order: legacy → packs → YAML → cache
  engine.py          # Classify, map, enrich, prompt sections
  retrieval.py       # Local-first policy (web stub, disabled)
  tools/generate_catalog.py
```

## Resolution order

1. **Local knowledge** — alias match score ≥ 2.0 → use catalog only  
2. **Cached knowledge** — `cache/*.json` from prior retrieval  
3. **Trusted retrieval** — stub only; disabled unless explicitly enabled; blocklist for EMA/JWT/OAuth/etc.

## Concept schema

Every concept includes: `concept_id`, `name`, `aliases`, `domain`, `category`, `description`, `requirements`, `common_implementations`, `risks`, `failure_modes`, `verification`, `testing`, `related_concepts`, `references`, `confidence`.

Validators reject weak entries (missing risks/failure_modes/testing/verification, duplicate aliases).

## Coverage (domains)

Software Architecture, Backend, Frontend, Databases, Cloud, DevOps, Networking, Security, AuthN/Z, APIs, Messaging, Distributed Systems, Observability, Data Engineering, ML, AI Infra, Mobile, Trading, Quant Finance, Testing, Build, CI/CD, Performance.

**Loaded concept count:** ~1,584 (run `get_engine().concept_count` after reload).

## Build / Investigate output

- **Build:** Concept, meaning, requirements, risks, failure modes, verification, testing, repository roles, implementation strategy, files  
- **Investigate:** Domain failure modes, verification checklist, knowledge-backed prompts  
- **Exports:** `DOMAIN KNOWLEDGE` section in Claude/Cursor/Codex prompts  

## Expand catalog

```bash
py -3 jarvis_desktop/atlas_knowledge/tools/generate_catalog.py
```

Add curated concepts as YAML under `concepts/<domain>/`.

## Limitations

- Pack-expanded concepts use template descriptions (valid but not RFC-deep); curated YAML overrides for critical concepts  
- No live web retrieval in this release (stub only)  
- Path mapping remains heuristic (no AST)  

## Tests

`test_phase127_knowledge_engine.py` — scale, EMA/JWT, retrieval blocklist, prompts, grounded paths.
