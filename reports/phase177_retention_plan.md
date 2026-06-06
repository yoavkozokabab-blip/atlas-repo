# Phase 177 — Retention Measurement Plan

**Date:** 2026-06-06  
**Design only. No invasive tracking. Privacy-first.**  
**Goal:** Understand whether beta users return, without building surveillance infrastructure.

---

## Design Philosophy

Atlas is local software. No server receives usage data. The product's trust model is "code never leaves your machine." Retention measurement must respect this:

1. **All measurement is local** — Atlas never sends usage data anywhere automatically
2. **All reporting is user-initiated** — usage data is in support bundles that users send
3. **All events are coarse** — "user ran a scan" not "user opened file X at 14:23:17"
4. **No PII in events** — no names, no emails, no IP addresses

The result is an opt-in model: beta users who send support bundles tell you what's happening. Users who don't send bundles are invisible. This is intentional — it means only engaged users generate visibility, which is itself a signal.

---

## Events Already Tracked (analytics.jsonl)

Every event in `analytics.jsonl` has a Unix timestamp (`ts`), which enables all retention calculations. The following events are already emitted:

| Event | Emitted when |
|-------|-------------|
| `scan_completed` | Any scan (demo or real) finishes |
| `demo_loaded` | User loads a demo pack |
| `change_plan_created` | User generates a Change Plan |
| `investigation_plan_created` | User generates an Investigation |
| `impact_analyzed` | User runs What breaks? |
| `export_created` | User copies to Claude/Cursor/Codex |
| `copilot_question` | User asks the Repository Copilot a question |

And in `launcher.log`:
- `startup ready=True` = app launch event

---

## Day 1 Retention

**Definition:** User opened Atlas again within 24 hours of first launch.

**Measurement:**
```python
events = load_analytics("analytics.jsonl")
launches = [(e["ts"], e) for e in events if "startup" in str(e)]
first_launch = min(t for t,_ in launches)
day_1_launches = [t for t,_ in launches if first_launch < t <= first_launch + 86400]
day_1_retained = len(day_1_launches) > 0
```

**What it means:**
- Day 1 retention = user found enough value to return
- Minimum target: 3/5 beta users return on day 2 without prompting

**Proxy (before launch log is available):** Any event with `ts > first_ts + 86400` where `first_ts` is the first recorded event.

---

## Day 7 Retention

**Definition:** User has at least one Atlas event 6–8 days after first launch.

**Measurement:**
```python
events_by_day = group_events_by_calendar_day(events)
first_day = min(events_by_day.keys())
day_7_window = [d for d in events_by_day if 6 <= (d - first_day).days <= 8]
day_7_retained = len(day_7_window) > 0
```

**What it means:**
- Day 7 retention = Atlas became part of the user's workflow
- Target: 2/5 users active in week 2 without prompting

---

## Repeat Scans

**Definition:** User has scanned the same repository (non-demo) more than once.

**Measurement:**
```python
from collections import Counter
repo_scans = Counter(
    e.get("repo_name") 
    for e in events 
    if e.get("event") == "scan_completed" and not e.get("demo")
)
repeat_scan_repos = {repo: count for repo, count in repo_scans.items() if count > 1}
```

**What it means:**
- Repeat scans = the user is actively developing and returning to Atlas for each change
- A user who scans the same repo 5+ times in a week has integrated Atlas into their workflow

**Note:** `repo_name` is stored (not `repo_path`) — it's the basename of the folder. Privacy-preserving.

---

## Repeat Exports (Copy to Claude)

**Definition:** User has used "Copy for Claude/Cursor/Codex" more than once.

**Measurement:**
```python
exports = [e for e in events if e.get("event") == "export_created"]
export_days = set(day_from_ts(e["ts"]) for e in exports)
repeat_exporter = len(export_days) > 1
export_count = len(exports)
```

**What it means:**
- One export = user tried Atlas
- Five exports = user uses Atlas regularly before editing
- Ten exports = Atlas is in the workflow

**The metric that matters most:** Average exports per week, not total. A user with 10 exports in day 1 (experimenting) is different from a user with 2 exports/day for 5 days (working).

---

## Repeat Claude Usage (Inferred)

**Challenge:** Atlas does not know what happens after the user clicks "Copy for Claude." The conversation is outside Atlas's scope.

**Proxy metric:** Export count × quality score from the Phase 177 live validation. If Atlas produces high-quality exports and the user repeatedly copies, we can infer the Claude answers are useful.

**Better proxy:** Ask directly in the Day 7 check-in:
> "After you copy from Atlas and paste into Claude, do you find Claude's responses more useful than without Atlas?"
> Scale: Much more useful / Somewhat more useful / About the same / Less useful

This is qualitative but honest. It's the only ethical way to measure "repeat Claude usage" without instrumenting Claude.

---

## Retention Dashboard (for 5 users)

For 5 supervised users, retention is a **manual weekly review**, not an automated dashboard:

```
WEEK 1 RETENTION SNAPSHOT — 2026-06-13

User-01 (Marcus):
  Launched: 4 times
  Scans (real repo): 3 × "myproject"
  Build plans: 5
  Exports: 8
  Day 1: YES  Day 7: YES
  Notes: Scans same repo daily before making changes. HIGH VALUE.

User-02 (Sarah):
  Launched: 2 times
  Scans (real repo): 1 × "backend-api"
  Build plans: 2
  Exports: 2
  Day 1: NO  Day 7: UNKNOWN (no second bundle yet)
  Notes: Used demo + one real scan. Silent since day 2. RISK.
  Action: Follow-up DM.

User-03 (James):
  Launched: 6 times
  Scans (real repo): 0 (demo only)
  Build plans: 8 (all on demo)
  Exports: 6 (all on demo)
  Day 1: YES  Day 7: YES
  Notes: Uses Atlas daily on the demo, not their real repo.
  Risk: Value not realized. Real-repo scan blocked by something.
  Action: 30-min call to understand what's blocking them.
```

---

## The One Metric That Tells You Everything

At the Day 7 check-in, ask one question:

> **"How disappointed would you be if Atlas disappeared tomorrow?"**
> Very disappointed / Somewhat disappointed / Not very disappointed / Not disappointed at all

Phase 171 defined the Sean Ellis threshold: 40% "very disappointed" = product-market fit signal.

For 5 users:
- 2+ "very disappointed" = promising, keep going
- 1 "very disappointed" = understand their profile; recruit more like them
- 0 "very disappointed" = something is fundamentally wrong with either the product or the user profile; do not expand

No retention metric replaces this question. All the analytics above tell you what users did. This question tells you whether it mattered.

---

## What NOT to Track

| What to avoid | Why |
|---------------|-----|
| Keystrokes, typing speed | Too invasive; breaks trust |
| Which files the user opened | Privacy; not needed |
| Time spent on each screen | Useful but requires JS instrumentation that feels like surveillance |
| Whether the user copied the plan to Claude | Atlas cannot know this without tracking clipboard or browser |
| Whether Claude gave a good answer | Outside Atlas scope |
| Any personally identifying information | Explicitly against Atlas's trust model |

---

## Retention Signals in Order of Importance

| Rank | Signal | Measurement | Target |
|------|--------|-------------|--------|
| 1 | "Very disappointed if Atlas disappeared" | Day 7 survey | ≥ 2/5 users |
| 2 | Day 7 retention | analytics.jsonl event in week 2 | ≥ 2/5 users |
| 3 | Real repo scanned (not just demo) | scan_completed with demo:false | ≥ 3/5 users |
| 4 | Repeat exports | export_created count ≥ 3 | ≥ 3/5 users |
| 5 | Day 2 retention | analytics.jsonl event within 24h | ≥ 3/5 users |
| 6 | Repeat scans (same repo) | scan_completed for same repo_name | ≥ 2/5 users |
| 7 | Feedback submitted | feedback.jsonl has entries | ≥ 4/5 users |

**Alarm signals (require immediate follow-up):**
- User launched but never scanned a real repo → Something blocked the first real scan
- User scanned once but never generated a plan → Output confused them or they gave up
- User generated a plan but never exported → Copy button not found or output not trusted
- User has 0 events after day 1 → Silent churn; reach out by Day 3

---

## Measurement Cadence for 5 Users

| Day | Action |
|-----|--------|
| Day 1 | Request analytics.jsonl export or support bundle; confirm install success |
| Day 2 | Check whether any analytics events since install; DM if silent |
| Day 7 | Request Week 1 support bundle; ask disappointment question |
| Day 14 | Request Week 2 support bundle; assess real-repo scan status |
| Day 30 | Final check-in call; full retention analysis |
