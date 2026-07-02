# 04 — Support System

**Date:** 2026-06-20. Atlas already has: in-app **support bundle** (redacted .zip), a **feedback** path (NPS + category) wired to the accounts service, and a contact page (env-driven support email — must be a real monitored inbox, currently a suspicious personal gmail).

## 1 user (now)
- **Channel:** founder's direct email + a screen-share offer. You personally watch the first installs.
- **Bug reports:** "in the app → Support → Download support bundle → email it to me." (Bundle is redacted; no source/secrets.)
- **Feedback:** a 15-min call after their first session.
- **SLA:** same-day, by you.

## 10 users
- **Shared inbox:** `support@useatlas.dev` (set `NEXT_PUBLIC_SUPPORT_EMAIL` to it — fix the current personal-gmail value). Tag emails: bug / question / feature / billing.
- **Beta Discord (or a single email thread):** one channel for real-time "is anyone else seeing…". Cheap, high-signal.
- **Bug reports:** support bundle attached; you trace via `reports/jarvis_logs` / the bundle.
- **Feature requests:** capture in a single Notion/issue list; tag by frequency.
- **Beta interviews:** schedule 5 of the 10 (see feedback program).
- **SLA:** 24 h.

## 100 users
- **Lightweight ticketing** (shared inbox + tags, or a simple helpdesk) — don't over-build; tags + a saved-replies doc is enough.
- **FAQ / docs** covering the top 10 recurring issues (SmartScreen, config path, "tools not showing", path format, uninstall).
- **Status page** (`/api/health`-backed) + a one-line incident channel.
- **Office hours:** a weekly 30-min open call for beta users.
- **Escalation:** a triage rule — crashes (support bundle) → you; config/usage → FAQ + saved reply.
- **SLA:** 48 h first response; crashes prioritized.

## Feedback loops (all tiers)
- Every support touch → log the root cause → fold the top items into the FAQ + the onboarding page.
- Weekly: review feedback + NPS, pick the single highest-frequency friction, fix it, tell users you fixed it (closes the loop, builds loyalty).
