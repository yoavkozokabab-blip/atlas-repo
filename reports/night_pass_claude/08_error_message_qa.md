# 08 — Error Message QA

**Date:** 2026-06-20. Inventory of user-facing error strings (website + desktop).

## Website (clear + actionable)
| Message | Where | Actionable | Leaks internals? |
|---|---|---|---|
| "Invalid email or password." | login | yes | no (anti-enumeration) |
| "An account with this email already exists." | signup | yes | no |
| "Password must be at least 8 characters." | signup | yes | no |
| "Enter a valid email address." | signup | yes | no |
| "Something went wrong. / Please try again." | form catch-all (e.g. 500) | partly (generic) | no |
| "Too many attempts. Please try again later." | rate limit | yes | no |
| "Waitlist temporarily unavailable. Please try again." | waitlist 503 | yes | no |
| "No installer available." | /download/atlas (URL unset) | n/a (owner) | no |

## Desktop
| Message | Where | Actionable | Leaks internals? |
|---|---|---|---|
| "Sign in to activate Atlas." | account state | yes | no |
| "The Atlas accounts service isn't available right now. Please restart Atlas…" | login when service down | yes | no |
| "Complete the required beta profile fields." | beta form | yes | no |
| **(was) raw pydantic blob `[{'type':'literal_error',…}]`** | beta register | **no** | **yes** → **FIXED this pass** → "Please check the form fields and try again." |
| "{ExcType}: {msg}" (server.py:261 catch-all 500) | any unhandled desktop route error | partly | **mild** (shows exception type) — rare safety net; left as-is (changing the catch-all is logic) |

## Worst 3 (and disposition)
1. **Raw pydantic validation blob** on the desktop beta form — the single worst (unreadable + leaks schema). **FIXED** (`accounts_routes.py`).
2. **Stale beta-application form 500/ISE** — root issue is the stale form itself (report 05); recommend hiding it in website mode (P0/P1 flow change, not a tiny fix).
3. **Generic "Something went wrong."** on backend 500 — acceptable; once prod env is healthy it rarely fires. Left as-is (improving it risks masking the real cause; the diagnostic is `/api/health`).

## Fixes this pass
1 fix: desktop register now shows a friendly message instead of the raw validation blob. The other two are flow/owner items, not safe tiny copy edits.
