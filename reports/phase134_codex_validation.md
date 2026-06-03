# Phase 134 Codex Validation - Architectural Intelligence

Date: 2026-06-03

Repository under test:

```text
C:\J.A.R.V.I.S\local_jarvis\external_repos\home_assistant
```

## Verdict

**FAIL / NO-GO for first demo-safe Phase 134 architectural intelligence on Home Assistant.**

The current implementation can build and analyze a large Home Assistant graph, and the fresh in-process architecture path now distinguishes top hubs from top risks. However, the required semantic Impact prompts still fail through the Copilot route, one Phase 134 regression test fails, the benchmark file does not work as the requested pytest command, and the full desktop suite does not finish cleanly.

## Scope Note

This was a verification pass, not an implementation pass. I did not change production code. During validation, concurrent uncommitted Phase 134 files were already present in the worktree; this report records the behavior of that current worktree.

## Startup / UI Access

Requested startup command:

```text
py -3 run_jarvis_desktop.py
```

Atlas health endpoint responded at:

```text
http://127.0.0.1:8777
```

Observed health:

```text
product=ATLAS
version=phase127-atlas-knowledge-engine
repository_open=true
repo_name=home_assistant
```

Screenshots were not captured. The Codex in-app browser route was unavailable, and live HTTP verification was complicated by multiple local Atlas listeners on port 8777. To avoid stale-server evidence, the final functional checks below use a clean in-process `jarvis_desktop.api` run from the current worktree.

## Exact Commands Run

```text
py -3 run_jarvis_desktop.py --no-browser
```

```text
py -3 -m pytest jarvis_desktop/tests/test_phase134_architectural_intelligence.py -q
```

```text
py -3 -m pytest benchmarks/real_repos/home_assistant_architecture_validation.py -q
```

```text
py -3 benchmarks/real_repos/home_assistant_architecture_validation.py
```

```text
py -3 -m pytest jarvis_desktop/tests -q
```

I also ran a clean in-process API validation that reset `_STATE`, scanned Home Assistant, and issued the exact Impact, Build, and Investigation prompts listed by the task.

## Scan Metrics

Fresh in-process scan, cache disabled:

| Metric | Result |
| --- | ---: |
| scan duration | 233.64s |
| files indexed | 25,893 |
| modules | 9,709 |
| edges | 36,013 |
| subsystems | 1,512 |
| visible module nodes | 5,000 |
| visible module links | 19,436 |
| total module graph modules | 9,709 |
| total module graph edges | 36,013 |
| resolved imports | 36,013 |
| unresolved imports | 59,473 |
| unresolved internal imports | 20,853 |
| unresolved external / stdlib imports | 33,271 |
| unresolved dynamic / optional imports | 45 |
| unresolved internal ratio | 0.3667 |
| unresolved ratio | 0.6228 |
| graph health label | `partial` |
| graph health basis | `internal_unresolved` |

Graph health notice:

```text
Graph health reflects 20853 unresolved INTERNAL import(s) (37% of internal imports).
The 33271 external/stdlib import(s) are expected dependencies, not defects.
```

This satisfies the large-graph and honest-partial-coverage requirements.

## Repository Map Check

| Check | Result | Evidence |
| --- | --- | --- |
| graph visible | PASS | module graph returns 5,000 visible nodes, capped from 9,709 |
| many nodes | PASS | 9,709 modules |
| top hubs shown | PASS | top hub is `homeassistant/const.py`, fan-in 4,794 |
| top risks shown | PASS | top risk is `homeassistant/auth/__init__.py`, score 91.1 |
| top hubs and top risks are not identical | PASS | hubs are fan-in modules; risks are auth/recorder/http/setup/service boundaries |
| `.prettierrc` absent from top risk/hub | PASS | no dotfile/config formatting file appeared in top hub or risk lists |
| `const.py` not blindly highest risk | PASS | `const.py` remains top hub, not top risk, in the fresh in-process path |
| unresolved imports categorized | PASS | external, optional, dynamic, internal_missing, relative_resolution_issue, namespace_package, test_or_dev_only |

Top hubs:

```text
homeassistant/const.py
homeassistant/helpers/entity_platform.py
homeassistant/helpers/__init__.py
homeassistant/exceptions.py
homeassistant/helpers/typing.py
homeassistant/helpers/update_coordinator.py
homeassistant/components/sensor/__init__.py
homeassistant/helpers/aiohttp_client.py
```

Top risks:

```text
homeassistant/auth/__init__.py
homeassistant/components/recorder/__init__.py
homeassistant/components/recorder/statistics.py
homeassistant/components/http/__init__.py
homeassistant/setup.py
homeassistant/helpers/service.py
homeassistant/components/http/auth.py
homeassistant/helpers/event.py
```

## Impact Checks

| Prompt | Expected | Observed | Result |
| --- | --- | --- | --- |
| `what breaks if I remove the event bus` | EventBus, `core.py`, `async_fire`, `async_listen`, `helpers/event.py`, automation/listeners/service/state, direct and indirect impact, confidence explanation | Copilot answered `Name a file or module to analyze...`; limitation: `No target path could be resolved from the question.` | FAIL |
| `what breaks if I remove websocket support` | `websocket_api`, auth/session, connection handlers, affected integrations/API clients | Copilot answered `Name a file or module to analyze...`; limitation: `No target path could be resolved from the question.` | FAIL |
| `what breaks if I change homeassistant/const.py` | high fan-in / constant blast radius / tests affected, no unsupported runtime claims | Copilot misresolved this to `homeassistant/components/homeassistant/const.py` and reported only 6 direct importers. | FAIL |

Root cause: the impact engine can answer explicit internal targets, but the Copilot impact route still lacks reliable concept/path resolution for semantic targets like event bus and websocket support, and it can choose the wrong same-named path.

## Build Checks

| Prompt | Expected | Observed | Result |
| --- | --- | --- | --- |
| `add distributed tracing` | logging, request/websocket boundaries, event/service boundaries; not random auth/bootstrap only | Suggested websocket, automation, bootstrap, Azure event hub, and auth store files. Contains plausible websocket/event/auth signals, but reports keyword-only limitations. | PARTIAL |
| `add rate limiting` | websocket/API/auth/request boundaries; not random unrelated integrations | Includes `assist_pipeline/websocket_api.py` and API/auth signals, but also unrelated-looking TTS/VAD/integration files such as `amazon_polly/tts.py` and `assist_pipeline/vad.py`. | PARTIAL / FAIL |

## Investigation Check

| Prompt | Expected | Observed | Result |
| --- | --- | --- | --- |
| `why are duplicate events being fired` | event bus, `async_fire`, `async_listen`, `helpers/event`, automation, dispatcher/listener registration | Top hypothesis: `Defect originates in homeassistant/helpers/event.py`; likely files include `helpers/event.py`, `core.py`, `helpers/dispatcher.py`, automation, and related listener/setup files. | PASS |

No `.prettierrc`, `package.json`, `pyproject.toml`, lint config, formatting config, docs, or static file was selected as the top hypothesis.

## Automated Test Results

### Phase 134 pytest

Command:

```text
py -3 -m pytest jarvis_desktop/tests/test_phase134_architectural_intelligence.py -q
```

Result:

```text
1 failed, 10 passed, 2 warnings in 341.16s
```

Failure:

```text
FAILED jarvis_desktop/tests/test_phase134_architectural_intelligence.py::test_unresolved_import_classification_buckets
assert payload["internal_unresolved_count"] >= 1
E assert 0 >= 1
```

This indicates unresolved import classification still fails a small internal/relative mock case.

### Requested benchmark pytest command

Command:

```text
py -3 -m pytest benchmarks/real_repos/home_assistant_architecture_validation.py -q
```

Result:

```text
exit code 1
1 warning in 0.03s
```

The file is script-style and does not expose pytest tests. Pytest also emitted:

```text
PytestCacheWarning: could not create cache path C:\J.A.R.V.I.S\local_jarvis\.pytest_cache\v\cache\nodeids
```

### Direct benchmark script

Command:

```text
py -3 benchmarks/real_repos/home_assistant_architecture_validation.py
```

Result:

```text
13/13 passed
```

Passing checks included:

```text
graph.modules>9000
graph.edges>30000
top_hubs!=top_risks
unresolved.categorized
unresolved.internal_separate
const.hub_not_top_risk
architecture_summary.components/helpers/core/auth/config_entries
impact.event_bus
impact.websocket
```

Note: the direct script uses `api.change_impact_simulation(...)`, not the user-facing Copilot prompt route that failed above.

### Full desktop tests

Command:

```text
py -3 -m pytest jarvis_desktop/tests -q
```

Result:

```text
2 failed, 308 passed, 2 warnings, 114 errors in 1931.27s (0:32:11)
```

The tool timed out after pytest printed the summary. Most errors are Windows temp/cache permission errors:

```text
PermissionError: [WinError 5] Access is denied: C:\Users\babi2\AppData\Local\Temp\pytest-of-babi2
```

Real failures observed:

```text
FAILED jarvis_desktop/tests/test_phase111_cinematic_repository_universe.py::test_server_routes_phase111
FAILED jarvis_desktop/tests/test_phase116g_external_beta_blockers.py::test_ui_shows_partial_graph_warning_and_resolution_metrics
```

The Phase 116G failure asserted that `jarvis_desktop/static/app.js` does not contain the exact UI text `Unresolved imports`.

## Pass / Fail Table

| Requirement | Status |
| --- | --- |
| Home Assistant graph remains large | PASS |
| modules > 9000 | PASS |
| edges > 30000 | PASS |
| graph is not one node | PASS |
| graph health explains partial coverage honestly | PASS |
| unresolved imports are categorized | PASS |
| top risks are meaningfully different from top hubs | PASS in fresh in-process path |
| `const.py` is not blindly highest architectural risk | PASS in fresh in-process path |
| Impact works on `event bus` semantic target through Copilot | FAIL |
| Impact works on `websocket support` semantic target through Copilot | FAIL |
| Impact works on `homeassistant/const.py` prompt through Copilot | FAIL |
| Build plan for distributed tracing is plausible | PARTIAL |
| Build plan for rate limiting is plausible | PARTIAL / FAIL |
| Investigation avoids dotfile hallucination | PASS |
| Phase 134 pytest passes | FAIL |
| requested benchmark pytest command passes | FAIL |
| direct benchmark script passes | PASS |
| full desktop suite passes | FAIL |

## Root Causes

1. Copilot impact target resolution is not yet Phase 134-ready. It does not map natural-language architecture targets such as event bus and websocket support to known Home Assistant modules.
2. Explicit path resolution can choose the wrong same-named module, as shown by `homeassistant/const.py` resolving to `homeassistant/components/homeassistant/const.py`.
3. Build planning still falls back to keyword matching for some architecture requests, producing noisy file suggestions.
4. The unresolved import classifier has a failing mock internal/relative case.
5. The Home Assistant validation benchmark exists as a script, but the requested `pytest` invocation is not a passing pytest test.
6. The full desktop test suite has unrelated pre-existing failures and Windows temp/cache permission errors.

## Final Assessment

Atlas is **not yet demo-safe on Home Assistant for Phase 134** under the user's acceptance rules.

It is safe to demonstrate that Atlas can build a large Home Assistant graph and separate hubs from risks in the fresh architecture analyzer path. It is not safe to demo user-facing semantic Impact on Home Assistant yet, because the exact prompts still fail through Copilot.
