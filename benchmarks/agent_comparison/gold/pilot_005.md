# Gold: pilot_005 — Debugging auth middleware AttributeError

## Expected core answer

Error: `AttributeError: 'NoneType' object has no attribute 'get'` in `auth/middleware.py` on Authorization handling.

Likely cause: `request.headers` is `None` (or request object missing headers), so `.get("Authorization")` fails.

Code path: `auth_middleware` → `request.headers.get("Authorization")` without guarding headers.

First files to inspect:

1. `auth/middleware.py` — failing line
2. Callers/tests constructing request objects — `tests/test_auth.py`
3. `api/routes.py` — how middleware is registered

## Required files

- `auth/middleware.py`

## Optional supporting files

- `tests/test_auth.py`
- `api/routes.py`

## Unacceptable hallucinations

- Blaming `auth/session.py` without evidence
- Database connection errors
- JWT crypto library failures (no crypto lib present)

## Expected caveats

- Stack trace is synthetic/hypothetical; answer should match code structure
- May suggest defensive `getattr(request, "headers", {})` fix

## Scoring rubric (0–5 each)

| Dimension | 5 | 0 |
|---|---|---|
| Correctness | None headers → .get failure | Unrelated root cause |
| Completeness | middleware + test/caller inspection | Single file mention |
| File citation accuracy | middleware.py correct | Wrong file |
| Evidence quality | Points to headers.get line | Generic debugging |
| Hallucination avoidance | No invented stack frames | Fabricates unrelated bugs |
| Actionability | Inspect order listed | No next steps |
