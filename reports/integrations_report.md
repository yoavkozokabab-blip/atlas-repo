# Integrations Reliability Report

- current_score: 100.0%
- target_score: 60.0%
- gap: 0.0%
- pass_rate: 100.0% (1/1 active, 4 skipped)

## Acceptance Results
- [SKIP] summarize_inbox (0.01 ms) — SKIP: email_mode='mock' (no live credentials)
- [SKIP] urgent_emails (0.0 ms) — SKIP: email_mode='mock'
- [SKIP] summarize_calendar (0.0 ms) — SKIP: calendar_mode='mock' (no live credentials)
- [SKIP] find_conflicts (0.0 ms) — SKIP: calendar_mode='mock'
- [PASS] read_only_guard (0.01 ms) — read-only interface confirmed

## Primary Blockers
- Live email/calendar adapters not connected (4 data cases SKIPPED — no OAuth credentials).

## Recommended Actions
- Set INTEGRATIONS_EMAIL_MODE=gmail_readonly and INTEGRATIONS_CALENDAR_MODE=gcal_readonly with valid OAuth tokens to enable live acceptance testing.