# 05 — Local Desktop UX QA (the beta-form ISE)

**Date:** 2026-06-20. Ran the source desktop at `127.0.0.1:8777` (local auth mode) and probed the account flow.

## What works
- Desktop server boots; `/api/accounts/state` returns cleanly (`unauthenticated`, "Sign in to activate Atlas").
- The **local accounts service starts** (`/api/accounts/service-status` → `{"running": true}`) — so the "service unavailable" path is NOT the issue.
- Scan / diagnostics / support routes are present (`server.py`).

## The beta-application form failure — diagnosed
Reproduced: `POST /api/accounts/register` with a beta profile returns a **raw pydantic validation blob** when the questionnaire enum values don't match the schema, e.g.:
```
"error": "[{'type': 'literal_error', 'loc': ['body','beta_profile','project_use'],
 'msg': \"Input should be 'personal', 'work' or 'both'\", ...}, …]"
```
The desktop surfaced this raw array verbatim (it `str()`-ed a non-string detail). The user-reported **"Internal Server Error"** is the same family — when the local accounts service returns a 500/422, its body is shown raw. **The local service itself is healthy; the failure is bad error surfacing + a schema mismatch / stale form.**

## Is the beta form still part of the intended flow?
**No — it is stale onboarding.** Analysis:
- The desktop UI (`atlas_accounts.js`) shows a **beta-application questionnaire** (project_use, company_size, developer_experience, primary_role, coding_tools, repo_size, atlas_help) submitting to a **local** accounts service — the OLD local-accounts model.
- The current architecture makes the **website** the signup/identity authority; the packaged desktop authenticates to it. The local beta-application form **conflicts with website signup** and is unnecessary.
- The UI does **not** gate the form by auth mode, so a packaged (website-mode) beta user can still hit this stale path.

## Recommendation (P0/P1 — not done here; it's a flow change, not a tiny fix)
In website-auth mode the desktop should present **"Sign in" to your Atlas (website) account** only, and **hide the local beta-application questionnaire**. Until that flow change ships, steer users to the **MCP path** (which never touches this form).

## Fix made this pass (tiny + safe)
`jarvis_desktop/accounts_routes.py`: stop surfacing the raw validation blob — non-string error detail now renders **"Please check the form fields and try again."** (no internal leak). This does not change auth logic.
