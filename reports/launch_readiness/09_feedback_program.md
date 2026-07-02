# 09 — Beta Feedback Program

**Date:** 2026-06-20. Atlas already has NPS + categorized feedback wired to the accounts service and an in-app support bundle — use them. Goal: turn 10 beta users into a tight learning loop.

## Beta interview (30 min, 5 of the first 10 users)
Discovery + observation. Ask, then *watch them use it*:
1. What were you doing before Atlas — how did you give your AI agent context about your codebase?
2. Walk me through installing + connecting. (Watch silently; note every pause/confusion.)
3. Ask Atlas the auth question — what did you expect vs get?
4. Was the answer *useful*? Would you have found those files faster yourself?
5. What almost made you quit?
6. What would make this a daily tool?
7. Would you pay for it? At what price would it be a no-brainer / too expensive?
8. Who else do you know who needs this?

## Survey (async, all users, <3 min)
- Role / primary AI tool (Claude/Cursor/Codex) / repo size.
- Did you complete: install? connect? first answer? (funnel self-report)
- 1–5: setup ease · answer usefulness · trust.
- Biggest friction (free text). Best moment (free text).

## NPS flow
- Trigger after the **3rd successful Atlas answer** (not on day 1 — too early).
- "How likely are you to recommend Atlas to another developer? (0–10)" + one follow-up: "What's the main reason?"
- Route 0–6 → personal email + interview invite; 9–10 → ask for a referral/testimonial.

## Bug reporting
- In-app: Support → Download support bundle (redacted) → email. Tag: crash / wrong-answer / setup / other.
- For "wrong/weak answer" reports, capture the task + repo type (no source) so you can improve retrieval later (not now).

## Feature requests
- Single backlog list; tag by frequency + by user segment. Don't build during beta — *count* them.
- Weekly: pick the one highest-frequency friction, fix it, and **tell the users you fixed it** (closes the loop, drives retention + word-of-mouth).

## Cadence
- Per user: welcome → (auto) activation check → NPS after 3 answers → interview if willing.
- Weekly (you): review NPS + bugs + requests; ship one friction fix; post a short "this week in Atlas beta" note to the beta channel.
