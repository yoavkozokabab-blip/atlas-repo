# Gold: pilot_004 — Impact of auth/session.py change

## Expected core answer

`auth/session.py` defines `create_session(user)`. Direct/immediate consumers:

- `auth/login.py` imports `create_session` — login breaks if signature/return shape changes

Downstream/indirect:

- Anything assuming session dict shape `{"user": user}` from login flow
- `auth/middleware.py` is separate (JWT header) but auth subsystem tests in `tests/test_auth.py` may fail

Unlikely affected: `trading/*`, `billing/*`, `indicators/*` (no direct import of session.py in reference repo).

## Required files

- `auth/session.py`
- `auth/login.py`

## Optional supporting files

- `tests/test_auth.py`
- `auth/middleware.py` (related auth area)

## Unacceptable hallucinations

- Claiming trading/execution imports session.py directly (false in this repo)
- Database migration required (no DB session store)
- All API routes break without evidence

## Expected caveats

- Impact is localized to auth login path unless session contract is shared wider
- Graph-based impact may surface test files

## Scoring rubric (0–5 each)

| Dimension | 5 | 0 |
|---|---|---|
| Correctness | login.py direct dependency | Claims unrelated subsystems |
| Completeness | Direct + test/related auth files | Only session.py repeated |
| File citation accuracy | login.py cited correctly | Invents consumers |
| Evidence quality | Import/call relationship stated | Speculation only |
| Hallucination avoidance | No trading-wide blast radius | Overclaims |
| Actionability | Lists files to retest | Vague "auth might break" |
