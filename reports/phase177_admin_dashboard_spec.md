# Phase 177 — Admin Dashboard Specification

**Date:** 2026-06-06  
**Design only. No billing. No user accounts. No enterprise.**  
**Purpose:** Give the Atlas builder a clear view of what 5–20 beta users are doing.

---

## Design Constraints

- All data is **local-first** — collected in `~/.jarvis_desktop/` on each user's machine
- No server. No database. No cloud sync. Atlas is local software.
- Beta operations works by the user **sending their support bundle** to the builder
- The admin view is what the builder sees when they open `admin.html` on their own machine **after aggregating support bundles** from users

This is fundamentally different from a SaaS dashboard. The builder cannot query live users. The data model is: **each user sends their bundle, the builder reads it.**

---

## Data Sources

| Source | Content | Location |
|--------|---------|----------|
| `analytics.jsonl` | All product events with timestamps | `~/.jarvis_desktop/analytics.jsonl` |
| `billing/repository_scans.jsonl` | Per-scan metadata (modules, edges, duration) | `~/.jarvis_desktop/billing/repository_scans.jsonl` |
| `billing/usage_events.jsonl` | Workflow events (build_plan, impact, investigation) | `~/.jarvis_desktop/usage_events.jsonl` |
| `feedback.jsonl` | In-app feedback submissions | `~/.jarvis_desktop/feedback.jsonl` |
| `launcher.log` | Startup events, crash events | `~/.jarvis_desktop/launcher.log` |
| `self_test.json` | Install self-test results | `~/.jarvis_desktop/self_test.json` |
| `memory/` | Repository memory files | `~/.jarvis_desktop/memory/` |

---

## Questions the Admin View Must Answer

### 1. Who installed Atlas?

**Current state:** Every user appears as `user_local_owner` in the usage tracker. There is no user identity.

**For beta operations:** Each support bundle is a "user." The builder assigns a label manually when they receive the bundle: "User-01 (Marcus, staff engineer)." The bundle filename or an added `beta_user_id` field identifies the user.

**Recommended addition to support bundle manifest:**
```json
{
  "bundle_id": "atlas-bundle-20260606-abc123",
  "atlas_version": "0.1.0-beta",
  "build_commit": "ef8df6cbe",
  "platform": "win32",
  "python_version": "3.13.0"
}
```

The `bundle_id` acts as a de-facto user identifier for beta ops.

---

### 2. Last launch

**Data available:** `launcher.log` contains lines like:
```
2026-06-06T13:18:30 startup ready=True
```
**Extract:** Last `startup ready=True` timestamp = last launch.

---

### 3. Last scan

**Data available:** `analytics.jsonl` contains:
```json
{"ts": 1780751609.5, "event": "scan_completed", "demo": false, "modules": 73}
```
**Extract:** Latest `scan_completed` event where `demo: false` = last real-repo scan.  
Latest `scan_completed` event (any) = last activity.

---

### 4. Repo language

**Current gap:** The analytics event for `scan_completed` does not include language. The `repository_scans.jsonl` includes `files_scanned` but not language breakdown.

**Add to `scan_completed` event:**
```json
{"event": "scan_completed", "primary_language": "python", "ts_files": 73, "js_files": 12}
```

**Workaround until then:** Infer from `module_count` vs `file_count`. If module_count is ≥ 80% of code file count, likely Python. If much lower, likely TypeScript or mixed.

---

### 5. Repo size

**Data available:** `billing/repository_scans.jsonl` contains:
```json
{"files_scanned": 2753, "modules_indexed": 73, "edges_indexed": 159, "size_bucket": "medium"}
```
`size_bucket` maps to: small (<10k LOC), medium (10k–300k), large (>300k).

---

### 6. Atlas version

**Data available:** `analytics.jsonl` events include `"product": "0.1.0-beta"`. Support bundle `version.txt` contains the exact version.

---

### 7. Crash count

**Current gap:** No structured crash log exists. `launcher.log` may contain traceback-related lines but they're not classified.

**Required addition (before beta):** Write `crashes.jsonl` at the install location:
```json
{"ts": 1780751609.5, "exc_type": "OSError", "exc_msg": "port 8777 in use", "atlas_version": "0.1.0-beta"}
```

The crash handler (Phase 173A MS-03) should be implemented before the first user installs.

---

### 8. Feedback count

**Data available:** `feedback.jsonl` — each line is one feedback submission.

**Extract:** Count lines. Group by `category` field:
- `bug`: count of bug reports
- `confusing_ui`: count of UX confusion reports
- `missing_feature`: count of feature requests
- `general`: count of general feedback

---

### 9. Active beta users

For the 5-user supervised beta, "active" = launched Atlas in the last 7 days. Extract from `launcher.log` startup timestamps.

---

## Admin Dashboard Layout (Design)

The builder opens `admin.html` with a special mode that reads aggregated data from multiple support bundles. The current `admin.html` is tied to the local user's data; this spec defines a separate **Beta Operations View** accessible at `admin.html?mode=beta`.

### Screen 1: User Cohort Overview

```
ATLAS BETA OPERATIONS — 0.1.0-beta
====================================

Users active last 7 days:    3/5
Total support bundles received:  4
Total feedback items:         12

USER TABLE
Name        | Version    | Last launch | Last scan  | Repo size | Crashes | Feedback |
------------|------------|-------------|------------|-----------|---------|----------|
User-01     | 0.1.0-beta | 2026-06-05  | 2026-06-05 | medium    | 0       | 3        |
User-02     | 0.1.0-beta | 2026-06-04  | 2026-06-03 | large     | 1       | 1        |
User-03     | 0.1.0-beta | 2026-06-06  | 2026-06-06 | medium    | 0       | 5        |
User-04     | (no bundle)| —           | —          | —         | —       | —        |
User-05     | 0.1.0-beta | 2026-06-02  | never      | —         | 2       | 3        |
```

Red flags: User-05 launched but never scanned. User-04 never sent a bundle. User-02 has 1 crash.

---

### Screen 2: Workflow Funnel

```
WORKFLOW FUNNEL (aggregated across all users)
============================================

Installs:                    5
Launched Atlas:              4  (80%)
Loaded demo/scanned repo:   3  (60%)
Generated first Change Plan: 3  (60%)
Copied to Claude:            2  (40%)  ← value realization
Returned next day:           2  (40%)
```

---

### Screen 3: Scan Statistics

```
SCAN STATISTICS
==============

Total scans (real repos):    8
Total scans (demo):         12
Demo/Real ratio:            1.5 : 1  (users scanning demo more than real repos)

Repo size distribution:
  small  (<10k LOC):    1 scan
  medium (10k-300k):    5 scans
  large  (>300k LOC):   2 scans

Primary language:
  Python:    6 scans
  TS/JS:     2 scans

Graph health distribution:
  healthy:   4 (50%)
  watch:     3 (37%)
  partial:   1 (13%)
```

---

### Screen 4: Feedback Log

```
FEEDBACK LOG
============
Filter: [All] [Bug] [UX] [Feature] [General]

2026-06-06 User-03  [confusing_ui]
"I don't understand what 'insertion confidence' means. Is this telling me 
to insert code somewhere? Or is it a confidence score?"
Version: 0.1.0-beta | Module count: 73 | Graph: watch

2026-06-05 User-01  [bug]
"The impact list shows 'function:api/handlers.py' — is that a bug? 
It looks like a file path but with weird prefix."
Version: 0.1.0-beta | Module count: 17 | Graph: healthy

[... more feedback ...]
```

---

### Screen 5: Crash Log (once implemented)

```
CRASH LOG
=========

Total crashes: 3

2026-06-04 User-02  OSError
Port 8777 was already in use. The process exited.
Atlas version: 0.1.0-beta | Platform: win32

2026-06-05 User-05  OSError  
Same issue — port conflict.
[2 occurrences of this crash across 2 users → P0 confirmed]
```

---

## Implementation Path

### Phase 1: Support bundle aggregation (manual, for 5 users)

No new code. Receive 5 support bundle zip files. Extract each to a folder named `user_01/`, `user_02/`, etc. Open `analytics.jsonl` and `feedback.jsonl` from each and manually review.

**Cost:** 10–15 minutes per user per week.

### Phase 2: Simple aggregation script (for 20 users)

A 50-line Python script that reads all bundle folders and produces a CSV:
```python
# bundle_aggregate.py
import json, os, csv
from pathlib import Path

bundles = list(Path("bundles/").glob("*/analytics.jsonl"))
rows = []
for bundle in bundles:
    user_id = bundle.parent.name
    events = [json.loads(l) for l in bundle.open()]
    last_launch = max((e["ts"] for e in events if "startup" in e.get("event","")), default=None)
    build_plans = sum(1 for e in events if e.get("event") == "change_plan_created")
    # ... etc
    rows.append({"user": user_id, "last_launch": last_launch, "build_plans": build_plans})

with open("beta_ops_report.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
```

### Phase 3: Dedicated admin page (for public beta)

A proper `beta_admin.html` page that loads and aggregates bundle data client-side using the File API drag-and-drop. No server required. The builder drags bundle zip files onto the page and sees the aggregated view.

---

## What the Admin View Must NOT Show

| Data | Reason |
|------|--------|
| Repository file paths | Privacy |
| Repository file contents | Privacy |
| User's real name | Only use the label assigned by the builder |
| Feedback message text without context | Always show version + graph_health alongside |
| Individual keystroke or interaction data | Not collected; too invasive |
| AI conversation content | Never collected |
