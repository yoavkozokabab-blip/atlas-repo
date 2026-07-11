# Gold: pilot_003 — Request lifecycle (atlas_reference)

## Expected core answer

1. **API entry** — `api/routes.py` `register_routes(app)` wires middleware
2. **Auth** — `api/routes.py` applies `auth_middleware` from `auth/middleware.py` (JWT header check via `authenticate_jwt`)
3. **Rate limit** — `api/rate_limit.py` `rate_limit_middleware` registered after auth
4. **Order path** (domain execution) — `trading/order_service.py` `place_order` → `trading/execution.py` `execute_order`

Supporting: `auth/login.py` → `auth/session.py` for login/session creation (parallel to middleware path).

## Required files

- `api/routes.py`
- `auth/middleware.py`
- `trading/order_service.py`
- `trading/execution.py`

## Optional supporting files

- `api/rate_limit.py`
- `auth/login.py`
- `auth/session.py`

## Unacceptable hallucinations

- Full HTTP server framework (Flask/FastAPI) not present
- Database persistence on every request
- Message queue between API and trading

## Expected caveats

- `rate_limit_middleware` is a stub (pass-through)
- No real HTTP server bootstrap in repo — architectural description is module-level

## Scoring rubric (0–5 each)

| Dimension | 5 | 0 |
|---|---|---|
| Correctness | Ordered path routes→auth→order→execution | Invents framework |
| Completeness | ≥4 required files in flow | Only names auth |
| File citation accuracy | All cited paths exist | Fake middleware paths |
| Evidence quality | Connects functions across files | List of dirs only |
| Hallucination avoidance | No invented HTTP stack | Claims REST server file |
| Actionability | Traceable refactor path | Cannot follow flow |
