# Phase 146A - Beta Blocker Revalidation

Date: 2026-06-04

Scope: revalidate every blocker reported in
`reports/phase145_beta_validation.md`. Validation only. No Atlas source code,
features, detectors, routing, or product behavior were modified.

## Final Verdict

NO-GO for a 10-user private beta.

Phase 146 beta polish improved onboarding and support copy, and the happy-path
API workflows still run. However, several Phase 145 release blockers remain
unresolved:

- default startup readiness still fails on this machine;
- the same default-data targeted beta test command still fails;
- no installer artifact is present;
- sample Impact quick-start still points to `core/util.py` and returns a mock
  target-not-found result;
- feedback/support is still local-only with no configured support destination;
- export packets still say `JARVIS REPOSITORY CONTEXT`;
- Atlas/JARVIS branding remains mixed;
- CDN graph dependency remains.

## Commands Run

### Startup readiness - default data

```powershell
py -3 - <startup_checks default>
```

Result:

```text
ready=false
data_dir=C:\Users\babi2\.jarvis_desktop
directories=false
detail=data (writable): [Errno 13] Permission denied:
C:\Users\babi2\.jarvis_desktop\.write_test
```

### Startup readiness - redirected temp data

```powershell
$env:JARVIS_DESKTOP_DATA = Join-Path $env:TEMP 'atlas_phase146a_desktop_data'
$env:ATLAS_USAGE_DATA_DIR = Join-Path $env:TEMP 'atlas_phase146a_usage_data'
py -3 - <startup_checks temp>
```

Result:

```text
ready=true
version=phase146-beta-polish
```

### API workflow revalidation

```powershell
$env:JARVIS_DESKTOP_DATA = Join-Path $env:TEMP 'atlas_phase146a_desktop_data'
$env:ATLAS_USAGE_DATA_DIR = Join-Path $env:TEMP 'atlas_phase146a_usage_data'
py -3 - <sample + requests workflow smoke>
```

Result summary:

| Check | Result |
|---|---|
| Product version | `phase146-beta-polish` |
| Demo packs | PASS, small/medium/large available |
| Small demo scan | PASS, 6 files, 5 modules, 4 edges, 3 subsystems, 0.02s |
| Demo Build Plan: `add rate limiting` | PARTIAL, `intent=general`, no first files, repo evidence not found |
| Demo Investigation: duplicate events | PARTIAL/FAIL quality, likely area `ring/x.py`, concept `EMA` |
| Demo Impact quick-start: `core/util.py` | FAIL quality, `mock=true`, target not found |
| Demo Impact alternate: `core/hub.py` | PASS, 2 direct importers |
| Demo Export | PASS technically, still contains `JARVIS REPOSITORY CONTEXT` |
| Support status after demo | PASS with temp data, startup_ready=true |
| Support bundle after demo | PASS, `atlas_support_bundle_20260604_153509.zip`, 2766 bytes |
| Requests scan | PASS, 125 files, 20 modules, 66 edges, 25 subsystems, 0.68s |
| Requests Build Plan: `add rate limiting` | PARTIAL, files returned but `intent=general` |
| Requests Investigation: connection pool leak | PARTIAL, likely area good, evidence still partly weak |
| Requests Impact: `src/requests/sessions.py` | PASS, high risk, 2 direct importers |
| Requests Export | PASS technically, still contains `JARVIS REPOSITORY CONTEXT` |

### Targeted tests - same default-data command as Phase 145

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase139_beta_readiness.py jarvis_desktop/tests/test_phase141_private_beta_launch.py jarvis_desktop/tests/test_phase143_installer_and_support.py -q -p no:cacheprovider --basetemp $env:TEMP\atlas_phase146a_pytest_default
```

Result:

```text
15 passed, 3 failed
```

Failures:

- `test_health_reports_phase141_version`: expects `phase141`, current version is
  `phase146-beta-polish`.
- `test_startup_checks_pass_in_dev`: startup readiness false in default data dir.
- `test_startup_status_route`: startup route reports ready=false in default data dir.

Warnings still include analytics write permission failures under
`C:\Users\babi2\.jarvis_desktop\analytics.jsonl`.

### Targeted tests - redirected temp data plus Phase 146 tests

```powershell
$env:JARVIS_DESKTOP_DATA = Join-Path $env:TEMP 'atlas_phase146a_desktop_data_tests'
$env:ATLAS_USAGE_DATA_DIR = Join-Path $env:TEMP 'atlas_phase146a_usage_data_tests'
py -3 -m pytest jarvis_desktop/tests/test_phase139_beta_readiness.py jarvis_desktop/tests/test_phase141_private_beta_launch.py jarvis_desktop/tests/test_phase143_installer_and_support.py jarvis_desktop/tests/test_phase146_beta_polish.py -q -p no:cacheprovider --basetemp $env:TEMP\atlas_phase146a_pytest_tempdata
```

Result:

```text
22 passed, 1 failed
```

Remaining failure:

- `test_health_reports_phase141_version`: stale Phase 141 expectation.

### Static rechecks

Commands included:

```powershell
Test-Path installer\output\Atlas_Setup.exe
rg -n "JARVIS|jarvis_feedback|feedback saved|Stored locally|public contact channel|https://unpkg.com|core/util.py" ...
```

Relevant results:

- `installer/output/Atlas_Setup.exe`: `False`
- `jarvis_desktop/static/app.js`: Impact example still `core/util.py`
- `jarvis_desktop/static/atlas_beta.js`: guided impact fallback still `core/util.py`
- `jarvis_desktop/api.py`: export header still `# JARVIS REPOSITORY CONTEXT`
- `jarvis_desktop/static/feedback.js`: feedback still stored in localStorage key
  `jarvis_feedback`
- `jarvis_desktop/static/contact.html`: public contact channel still not
  configured
- `jarvis_desktop/static/index.html`: graph scripts still loaded from unpkg CDN
- `jarvis_desktop/README.md`, `run_jarvis_desktop.py`,
  `installer_build.ps1`, feedback/demo/gallery/admin pages still include
  user-facing JARVIS branding

## Workflow Revalidation

| Workflow | Phase 146A status | Evidence |
|---|---|---|
| Startup readiness | NOT RESOLVED | Default data startup still `ready=false`; temp redirect works |
| Sample repository workflow | PARTIALLY RESOLVED | Demo loads fast; first Build funnel improved; demo investigation/impact still weak |
| Demo impact workflow | NOT RESOLVED | `core/util.py` quick-start still returns `mock=true`, target not found |
| Build Plan workflow | PARTIALLY RESOLVED | Phase 146 first-build funnel exists; `add rate limiting` still `intent=general` |
| Investigation workflow | PARTIALLY RESOLVED | Real Requests symptom localizes better; demo duplicate-events still maps to EMA/trading |
| Export workflow | PARTIALLY RESOLVED | Export works; copied packet still says JARVIS, not Atlas |
| Feedback workflow | NOT RESOLVED | Feedback still localStorage-only, no real outbound destination |
| Support workflow | PARTIALLY RESOLVED | Support FAQ improved and bundle works; no real destination and default startup still fails |

## Phase 145 Top 20 Blocker Revalidation

| # | Phase 145 blocker | Status | Phase 146A evidence |
|---:|---|---|---|
| 1 | Default startup readiness fails on this machine | NOT RESOLVED | Default `startup_checks.ready=false`, permission denied writing `.write_test` |
| 2 | Targeted beta tests fail | PARTIALLY RESOLVED | Temp-data run improved to 22 passed / 1 failed; default run still 15 passed / 3 failed |
| 3 | Fresh install entry point is unclear | PARTIALLY RESOLVED | `docs/ATLAS_QUICKSTART.md` exists; root README still leads with JARVIS `main.py` |
| 4 | No installer artifact present | NOT RESOLVED | `installer/output/Atlas_Setup.exe` is absent |
| 5 | Atlas self-scan times out | NOT RESOLVED | No new self-scan evidence found; Phase 145/overnight timeout remains the latest evidence |
| 6 | Sample Impact example is broken | NOT RESOLVED | `core/util.py` still returns `mock=true`; UI quick-start still uses `core/util.py` |
| 7 | Feedback/support is local-only but looks sent | NOT RESOLVED | `feedback.js` still stores `jarvis_feedback` in localStorage and says feedback saved |
| 8 | No configured contact/support channel | NOT RESOLVED | `contact.html` still says public contact channel is not configured |
| 9 | Atlas/JARVIS branding is inconsistent | PARTIALLY RESOLVED | Product version/primary UI use Atlas; README, export, feedback/demo/admin/studio text still say JARVIS |
| 10 | CDN graph dependency can break offline first impression | NOT RESOLVED | `index.html` still loads Three.js and 3d-force-graph from `https://unpkg.com` |
| 11 | Build Plan quality is weakest repeated workflow | PARTIALLY RESOLVED | First-build funnel improved; prior benchmark score issue not remeasured as fixed |
| 12 | Build Plan can look specific while intent is generic | NOT RESOLVED | `add rate limiting` still returns `intent=general` on demo and Requests |
| 13 | Investigation can use unrelated domain knowledge | NOT RESOLVED | Demo duplicate-events investigation still reports concept `EMA`, domain Trading Systems |
| 14 | Weak/no-edge graphs still produce successful downstream outputs | NOT RESOLVED | No evidence of fixed gating; prior QuixBugs/LangChain/Qdrant graph failure evidence still stands |
| 15 | Large repo scans can feel frozen | PARTIALLY RESOLVED | Support/Home copy improved; no new large-repo scan evidence or performance fix |
| 16 | Unresolved import UX is hard to trust | PARTIALLY RESOLVED | Summary explains internal/external split; Requests raw unresolved ratio still 73.71% while health is healthy |
| 17 | Legacy mock impact path remains reachable | NOT RESOLVED | `_impact_mock` path still exists and returns `ok=true` for unresolved legacy impact |
| 18 | Support hint is too generic for data-dir failure | NOT RESOLVED | Default failure still says repair/reinstall, not exact writable data-dir fix |
| 19 | Export still says JARVIS context | NOT RESOLVED | Demo and Requests exports both contain `JARVIS REPOSITORY CONTEXT` |
| 20 | Installer docs contradict runtime reality | PARTIALLY RESOLVED | Quickstart clarifies Python/no-pip; installer README still calls installer self-contained and references JARVIS uninstall |

## What Improved Since Phase 145

- `PRODUCT_VERSION` is now `phase146-beta-polish`.
- `docs/ATLAS_QUICKSTART.md` exists and clearly says:
  - Atlas does not write/apply code;
  - do not run monorepo `requirements.txt`;
  - use `python3 run_atlas.py` on macOS/Linux;
  - paste Export packets into Claude/Codex/Cursor.
- Home UI includes a Planning-only banner.
- Phase 146 added `atlas_polish.js` with first Build Plan funnel helpers.
- Support page now includes beta FAQ guidance for Python, no-pip, huge repos,
  sample path, and planning-only expectations.
- Support bundle generation still works.
- Under redirected writable app data, Phase 139/141/143/146 tests are down to
  one stale-version failure.

## Remaining Release Blockers

Critical:

- Default startup readiness still fails on this machine.
- Default targeted beta tests still fail.
- Installer artifact cannot be validated because no `Atlas_Setup.exe` exists.
- First-minute sample Impact can still show a fake-looking target-not-found
  result.
- Feedback/support has no actual external destination for beta users.

High:

- Export and several static pages still use JARVIS branding.
- Graph still depends on CDN scripts for the premium first impression.
- Build and Investigation can still produce generic or unrelated evidence while
  looking polished.
- Weak/no-edge and large-repo blocker evidence has not been superseded by new
  passing measurements.

## Safety Confirmation

No Atlas source files were modified. The only intended workspace change from
this validation pass is this report:

- `reports/phase146a_beta_blocker_revalidation.md`

## Final Assessment

For an operator-guided internal demo: GO.

For a 10-user private beta: NO-GO.

Reason: the Phase 146 polish improves the onboarding funnel, but does not clear
the critical self-serve blockers. A 10-user private beta will still generate
avoidable install/startup/support tickets and can expose first-time users to
mock/heuristic or brand-inconsistent outputs in the first session.
