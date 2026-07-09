# First-User Feedback System

## Onboarding script
Install → (note SmartScreen behaviour) → connect one agent → scan a repo the user knows
→ ask the 3 questions → **watch silently**, logging every point you had to help (each
intervention = a defect to fix before public launch).

## Feedback questions (open-ended)
- What did you expect to happen at each step?
- Where did it surprise you (good or bad)?
- Did it find the right files?
- Faster than doing it yourself?
- Most confusing moment?
- One thing that would make you use it daily?

## The 3 test questions (use a repo the tester knows)
1. Retrieval: "Use Atlas to find where `<a feature you know>` is implemented."
2. Impact: "Use Atlas: what breaks if I change `<a core file you know>`?"
3. Root cause: "Use Atlas to find the root cause of this error: `<paste a real trace>`."

## Bug report template
```
Title:
OS / Atlas version / agent + version:
Repo size (rough LOC):
Steps to reproduce:
Expected / Actual:
Logs (Atlas data dir / mcp_server.log):
Severity (blocks first value? Y/N):
```

## Success criteria (per user)
- Reached first context pack **without founder help**.
- ≥2 of 3 questions returned the correct file(s).
- Still active at 7 days, unprompted.

## "Would you pay?" questions
- If the local tool stays free but a shared/governed team version is $19/mo/seat, would
  your team pay?
- What would it need to do for you to expense it?
- What do you pay today for tools in this category?

## When to IGNORE feedback
- Single-user requests that contradict the wedge (large/complex repos).
- "Add feature X" before the core value lands.
- Small-repo users (not the ICP) asking for things that dilute large-repo focus.
- Aesthetic preferences with no retention signal.

## When to CHANGE the product
- The same friction blocks ≥3 of the first 10 users at the **same** step.
- Retained users converge on one missing capability tied to why they keep it.
- The "no-founder" test fails repeatedly at one step — fix that step before any public push.
