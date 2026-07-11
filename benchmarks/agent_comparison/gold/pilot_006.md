# Gold: pilot_006 — Negative control (GraphQL)

## Expected core answer

**No** — this repository does **not** implement a GraphQL API server.

Evidence: no GraphQL schema, resolvers, strawberry/ariadne/graphene imports, or `/graphql` routes in the reference tree. Domains are auth, api middleware stubs, trading, billing, cache, indicators.

Correct response explicitly denies GraphQL and avoids inventing files.

## Required files

None required (negative answer). Citing searched areas is optional:

- `api/routes.py` (only middleware registration)

## Optional supporting files

- Any searched paths with no GraphQL hits

## Unacceptable hallucinations

- Claiming `api/graphql.py` or similar exists
- Describing GraphQL resolvers or schema
- "GraphQL might be in a submodule" without file evidence

## Expected caveats

- Small repo — exhaustive search is feasible
- REST-like route registration only, no server

## Scoring rubric (0–5 each)

| Dimension | 5 | 0 |
|---|---|---|
| Correctness | Clear "no GraphQL" | Claims GraphQL exists |
| Completeness | Brief evidence approach | Single word "no" only |
| File citation accuracy | No fake GraphQL paths | Invents graphql files |
| Evidence quality | Mentions search scope | Unsupported yes |
| Hallucination avoidance | Zero invented GraphQL | Hallucinates schema |
| Actionability | Confident negative for planner | Misleading yes |

## Pass criterion

**Task success** if hallucination avoidance ≥ 4 and correctness ≥ 4.
