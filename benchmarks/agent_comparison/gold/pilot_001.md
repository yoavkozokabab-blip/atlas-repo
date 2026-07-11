# Gold: pilot_001 — Authentication location

## Expected core answer

Authentication lives primarily under `auth/`:

- `auth/login.py` — login entry calling session creation
- `auth/session.py` — `create_session(user)` session object
- `auth/middleware.py` — `auth_middleware` and `authenticate_jwt` on requests

API wiring: `api/routes.py` registers `auth_middleware`.

## Required files

- `auth/login.py`
- `auth/session.py`
- `auth/middleware.py`

## Optional supporting files

- `api/routes.py`
- `tests/test_auth.py`

## Unacceptable hallucinations

- Claiming OAuth, SAML, or external IdP integration exists
- Inventing `auth/jwt.py`, `auth/oauth.py`, or similar paths not in repo
- Stating passwords are hashed or validated (not implemented)

## Expected caveats

- JWT validation is minimal (`token is not None`); no full crypto stack
- Session storage is in-memory dict-like return, not persisted DB auth

## Scoring rubric (0–5 each)

| Dimension | 5 | 0 |
|---|---|---|
| Correctness | Names auth/ modules and roles accurately | Wrong subsystem or invents auth stack |
| Completeness | Covers login, session, middleware | Misses middleware or session |
| File citation accuracy | Cites existing auth/ files | Cites nonexistent files |
| Evidence quality | References actual functions | Vague "auth layer" only |
| Hallucination avoidance | No invented providers/files | Invents OAuth or missing files |
| Actionability | Developer can open cited files | No usable file pointers |
