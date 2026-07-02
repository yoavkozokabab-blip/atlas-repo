# 10 — Fixes Made (this night pass)

**Date:** 2026-06-20. Tiny, safe, audit-driven only. No retrieval/ranking/MCP-runtime/billing/feature/refactor changes.

## Fixed
1. **Desktop register — raw validation blob → friendly message.**
   `jarvis_desktop/accounts_routes.py`: a non-string error `detail` (a pydantic validation array) was `str()`-ed and shown to the user as `[{'type':'literal_error',…}]`. Now renders **"Please check the form fields and try again."** Removes an internal-leak / unreadable error (the worst user-facing message). Error-copy handling only — no auth logic changed.

## Already fixed in the immediately-prior pass (committed `6f13c9065`), re-verified here
- Download page: added the "Or connect your AI agent directly (MCP)" block with the **verify-via-`atlas_health`** prompt.
- Docs: `NEXT_PUBLIC_SUPPORT_EMAIL` example aligned to `support@useatlas.dev`.
- `/api/health` Supabase diagnostic (hostname + validation_passed).

## Intentionally NOT changed (out of scope / not a tiny-safe fix)
- **Hiding the stale desktop beta-application form** in website mode — a flow change, not a copy edit → P1 (report 05/09).
- **server.py catch-all 500 format** (`{ExcType}: {msg}`) — a safety-net; altering it is logic, and it rarely fires on a happy path.
- **Support email value / password-reset email delivery / unsigned installer / prod env / domain** — all owner/env, not code.
- Website copy — already clean; no broken links, fake buttons, or paid overclaims found.
