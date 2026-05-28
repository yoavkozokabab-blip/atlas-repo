# Integrations Reliability Report

- current_score: 95.0%
- target_score: 60.0%
- gap: 0.0%
- pass_rate: 100.0% (5/5)

## Acceptance Results
- [PASS] summarize_inbox (0.03 ms) — mock read-only
- [PASS] urgent_emails (0.01 ms) — Urgent emails (read-only):
MOCK MODE
  - Security review thread unresolved (dead
- [PASS] summarize_calendar (0.01 ms) — mock read-only
- [PASS] find_conflicts (0.01 ms) — conflicts mock
- [PASS] read_only_guard (0.01 ms) — read-only interface

## Primary Blockers
- Live email/calendar adapters not connected (mock-only).

## Recommended Actions
- Wire OAuth read-only providers behind existing summarize commands.