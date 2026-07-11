# Gold Answer: task_001

## Expected Core Answer

Authentication is split across the controlled reference repo:

- `auth/login.py` exposes `login(user, password)` and delegates session creation to `create_session`.
- `auth/session.py` defines `create_session(user)`.
- `auth/middleware.py` defines `authenticate_jwt(token)` and `auth_middleware(request, next_handler)`.
- `api/routes.py` mounts authentication into request handling by importing `auth_middleware` and calling `app.use(auth_middleware)` inside `register_routes(app)`.

The answer should distinguish login/session creation from request-time middleware.

## Required Files

- `benchmarks/repos/atlas_reference/auth/login.py`
- `benchmarks/repos/atlas_reference/auth/session.py`
- `benchmarks/repos/atlas_reference/auth/middleware.py`
- `benchmarks/repos/atlas_reference/api/routes.py`

## Optional Supporting Files

- `benchmarks/repos/atlas_reference/tests/test_auth.py`

## Unacceptable Hallucinations

- Claiming password validation exists in this repo.
- Claiming JWT verification validates signatures or expiry; the implementation only checks that a token is not `None`.
- Claiming auth is mounted in a framework-specific router not present in the controlled repo.

## Expected Caveats

- The controlled repo is intentionally tiny and simplified.
- `login(user, password)` ignores the password argument in the current implementation.
- `auth_middleware` calls `authenticate_jwt` but does not branch on the result.

## Scoring Notes

- Full correctness requires both implementation and mounting paths.
- File citation accuracy requires all four required files or an explicit explanation of why one is not relevant.
- Hallucination avoidance is important because this repo looks like a real service but has deliberately shallow behavior.
