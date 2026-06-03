# Phase 133 Codex Validation - Home Assistant Real Repo

Date: 2026-06-03

## Verdict

**FAIL / NO-GO for demo-safe Home Assistant behavior.**

Atlas is live and can accept the Home Assistant repository path, but the scan does not build a usable graph. The resulting Home Assistant graph has **1 module**, **0 dependency edges**, and the top architectural-risk module is `.prettierrc.js`. That fails the Phase 133 acceptance criteria and pollutes Impact, Investigation, and Build Plan behavior.

## Commands Run

```text
Invoke-RestMethod http://127.0.0.1:8777/api/health
Invoke-RestMethod http://127.0.0.1:8777/api/repositories/scan -Method POST -Body {"path":"C:\\J.A.R.V.I.S\\local_jarvis\\external_repos\\home_assistant"}
Invoke-RestMethod http://127.0.0.1:8777/api/repositories/current/summary
Invoke-RestMethod http://127.0.0.1:8777/api/repositories/current/graph?view=module
Invoke-RestMethod http://127.0.0.1:8777/api/repositories/current/graph?view=subsystem
Invoke-RestMethod http://127.0.0.1:8777/api/repositories/current/build-full-graph -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/copilot/ask -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/planning/investigate -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/planning/change -Method POST
py -3 -m pytest tests/test_phase133_home_assistant_real_repo.py -q
py -3 -m pytest benchmarks jarvis_desktop/tests -q
py -3 -c "from builder_core.bug_intelligence import depgraph; ..."
```

`py -3 run_jarvis_desktop.py` was not started a second time because Atlas was already serving `http://127.0.0.1:8777` and `/api/health` reported `product=ATLAS`, `version=phase127-atlas-knowledge-engine`, `repo_name=home_assistant`.

## Scan Numbers

| Metric | Result |
| --- | ---: |
| Repo path | `C:\J.A.R.V.I.S\local_jarvis\external_repos\home_assistant` |
| Files indexed | 25,893 |
| Total files estimated | 25,941 |
| Code files estimated | 17,474 |
| Estimated modules | 11,358 |
| Modules built | 1 |
| Dependency edges | 0 |
| Subsystems | 12 |
| API scan duration | 23.66s |
| Client elapsed for cached scan | 3.73s |
| Graph scope | `degraded` |
| Graph detail | `imports` |
| Graph health | `partial` |
| Module graph visible nodes | 1 |
| Module graph links | 0 |
| Subsystem graph visible nodes | 1 |
| Full graph build result | still 1 module |

Acceptance threshold failed:

- `modules <= 500`: **failed** (`1`)
- `edges <= 500`: **failed** (`0`)
- graph one node only: **failed** (`1 node`)

## Functional Checks

| Area | Prompt | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
| Impact | `what breaks if I remove websocket support` | Mention `websocket_api` or websocket handlers; not only unresolved target | Answer: `Name a file or module to analyze...`; limitation: `No target path could be resolved from the question.` | FAIL |
| Impact | `what breaks if I remove the event bus` | Mention `EventBus`, `core.py`, `async_fire`, `async_listen`, or helpers/event | Answer: `Name a file or module to analyze...`; limitation: `No target path could be resolved from the question.` | FAIL |
| Investigate | `why are duplicate events being fired` | Focus event bus/listeners/automation/dispatcher/setup lifecycle | Top hypothesis: `Defect originates in .prettierrc.js`; most likely source `.prettierrc.js` | FAIL |
| Build | `add distributed tracing` | Target logging/request/API/websocket/event/service boundaries | Suggested `homeassistant/components/automation/__init__.py`, `homeassistant/bootstrap.py`, `homeassistant/auth/auth_store.py`; polluted by `.prettierrc.js` risk and root subsystem | FAIL |
| Build | `add rate limiting` | Target API/websocket/auth/request boundaries | Partially mentioned `homeassistant/components/assist_pipeline/websocket_api.py`, but also selected unrelated `loader.py`, `amazon_polly/tts.py`, `vad.py`, and remained polluted by `.prettierrc.js` | PARTIAL / FAIL |

## Automated Tests

```text
py -3 -m pytest tests/test_phase133_home_assistant_real_repo.py -q
```

Result:

```text
ERROR: file or directory not found: tests/test_phase133_home_assistant_real_repo.py
```

```text
py -3 -m pytest benchmarks jarvis_desktop/tests -q
```

Result:

```text
2 failed, 290 passed, 2 warnings, 114 errors in 82.56s
```

Most errors are pytest temp-directory permission failures:

```text
PermissionError: [WinError 5] Access is denied: C:\Users\babi2\AppData\Local\Temp\pytest-of-babi2
```

There were also real failures:

```text
FAILED jarvis_desktop/tests/test_phase108_real_dependency_graph.py::test_local_jarvis_graph_is_non_trivial
assert 18 >= 50

FAILED jarvis_desktop/tests/test_phase111_cinematic_repository_universe.py::test_server_routes_phase111
assert "stops" in {"error": "No repository scanned yet.", ...}
```

## Screenshots

No screenshots were captured. The in-app browser route was unavailable in this session, Windows browser capture timed out while reading the active Edge window, and the isolated hidden Edge audit launch required desktop approval. API and live-server checks were completed instead.

## Suspected Root Cause

The failure appears to be graph construction for very large Python repositories under the current Atlas massive-repo path:

- The estimator correctly sees Home Assistant as Python-heavy: 17,471 `.py` code files and 11,358 estimated modules.
- Direct depgraph validation with a 20s import budget kept 8,261 production files but produced **0 module nodes** before timing out.
- The desktop scan/cache path then preserved a degraded graph with one JavaScript module: `.prettierrc.js`.
- Downstream systems consume that degraded graph as if it were the repository boundary, causing `.prettierrc.js` hallucination in investigation and risk output.

This is not demo-safe because Atlas can make confident-looking recommendations from a graph that represents essentially none of Home Assistant.

## Pass / Fail Table

| Requirement | Status |
| --- | --- |
| Atlas starts / is reachable | PASS |
| Home Assistant graph has many modules and edges | FAIL |
| Graph is not one node only | FAIL |
| Impact resolves websocket semantic target | FAIL |
| Impact resolves event bus semantic target | FAIL |
| Investigation avoids dotfile/config hallucination | FAIL |
| Build Plan localizes distributed tracing plausibly | FAIL |
| Build Plan localizes rate limiting plausibly | PARTIAL / FAIL |
| Existing requested Phase 133 test exists and passes | FAIL |
| Existing benchmark + desktop tests pass | FAIL |

## Final Assessment

**Home Assistant behavior is not demo-safe.**

Do not present Atlas as working on Home Assistant until the graph build path produces a substantial Python module graph and downstream planning/impact systems refuse or strongly fence degraded one-node scans instead of routing through `.prettierrc.js`.
