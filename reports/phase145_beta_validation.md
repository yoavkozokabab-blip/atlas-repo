# Phase 145 - Beta Readiness Validation

Date: 2026-06-04

Scope: hostile beta-tester validation of Atlas Desktop readiness. No Atlas code,
features, detectors, routing, or product behavior were modified. This report is
the only intended workspace artifact from the pass.

## Verdict

NO-GO for unsupervised external beta.

Atlas can complete a narrow happy path: startup checks pass when app data is
redirected to a writable temp directory, sample scan works, a small real repo
scan works, and Build / Investigation / Impact / Export APIs return without
crashing.

The beta blockers are product trust and first-run reliability:

- default first launch on this machine reports startup not ready because the
  default data directory is not writable;
- targeted beta tests are currently failing;
- the sample workflow contains a broken Impact example that returns a mock
  target-not-found result;
- several outputs look successful while being heuristic, generic, stale, or
  internally inconsistent;
- support/feedback looks like it sends feedback but actually stores it locally;
- docs and UI still mix Atlas and JARVIS branding;
- large-repository evidence shows serious scan time and trust issues.

## Commands And Evidence

### Repository state

Command:

```powershell
git status --short
```

Result: repository was already very dirty before this validation, including
benchmark outputs, external repositories, Phase 137A runtime directories, and
other untracked reports. This pass did not attempt cleanup.

### Static install and support inspection

Files inspected:

- `README.md`
- `jarvis_desktop/README.md`
- `run_jarvis_desktop.py`
- `run_atlas.py`
- `Launch Atlas.bat`
- `Launch Atlas.vbs`
- `Atlas.bat`
- `installer/README.md`
- `jarvis_desktop/install_support.py`
- `jarvis_desktop/server.py`
- `jarvis_desktop/api.py`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/support.html`
- `jarvis_desktop/static/support.js`
- `jarvis_desktop/static/feedback.html`
- `jarvis_desktop/static/feedback.js`
- `jarvis_desktop/static/contact.html`
- `jarvis_desktop/static/docs.html`
- `jarvis_desktop/static/beta.html`

### API workflow smoke

Executed with isolated temp data:

```powershell
$env:JARVIS_DESKTOP_DATA = Join-Path $env:TEMP 'atlas_phase145_desktop_data'
$env:ATLAS_USAGE_DATA_DIR = Join-Path $env:TEMP 'atlas_phase145_usage_data'
py -3 - <inline API smoke>
```

Summary:

| Area | Result |
|---|---|
| Startup checks with temp data | PASS, ready=true, Python 3.13.0 |
| Empty path validation | PASS, friendly `empty_path` error |
| Missing path validation | PASS, friendly `not_found` error |
| Demo packs | PASS, small/medium/large available |
| Small demo scan | PASS, 6 files, 5 modules, 4 edges, 3 subsystems, 0.01s |
| Demo Build Plan | PASS technically, but low-medium confidence, `intent=general`, no first files |
| Demo Investigation | PASS technically, but misleading domain/topic evidence |
| Demo Impact | FAIL quality, `core/util.py` returned `mock=true`, target not found |
| Demo Export | PASS, compact Codex packet about 288 estimated tokens |
| Support bundle | PASS, zip generated, no crash |
| Requests scan | PASS, 125 files, 20 modules, 66 edges, 25 subsystems, 0.39s |
| Requests Build Plan | PASS technically, but `add rate limiting` still `intent=general` |
| Requests Investigation | PASS technically, but evidence centers on weak files |
| Requests Impact | PASS, `src/requests/sessions.py`, high risk, 2 direct importers |
| Requests Export | PASS, compact Claude packet about 434 estimated tokens |

### Targeted beta tests

Command:

```powershell
py -3 -m pytest jarvis_desktop/tests/test_phase139_beta_readiness.py jarvis_desktop/tests/test_phase141_private_beta_launch.py jarvis_desktop/tests/test_phase143_installer_and_support.py -q -p no:cacheprovider --basetemp $env:TEMP\atlas_phase145_pytest
```

Result:

```text
15 passed, 3 failed
```

Failures:

- `test_health_reports_phase141_version`: expects `"phase141"` but current
  product version is `"phase143-one-click-installer"`.
- `test_startup_checks_pass_in_dev`: startup readiness false in default data
  directory.
- `test_startup_status_route`: startup route reports ready=false in default data
  directory.

Observed warning:

```text
analytics write failed ... PermissionError: C:\Users\babi2\.jarvis_desktop\analytics.jsonl
```

Default startup check:

```text
ready=false
directories: data (writable): Permission denied:
C:\Users\babi2\.jarvis_desktop\.write_test
```

### Prior benchmark evidence consumed

Reports used as current measurement evidence:

- `reports/overnight_repository_leaderboard.md`
- `reports/overnight_failure_taxonomy.md`
- `reports/post_benchmark_roi_analysis.md`
- `reports/phase139_beta_readiness.md`
- `reports/phase141_private_beta_launch.md`
- `reports/phase142_beta_breakage_audit.md`
- `reports/phase143_installer_and_support.md`
- `reports/phase144_private_beta_execution.md`

Notable benchmark facts:

- Home Assistant scan: 25,893 files, 9,709 modules, 36,013 edges, 494.804s.
- VS Code scan: 14,892 files, 7,563 modules, 13,228 edges, 67,338 unresolved imports.
- Atlas self-scan timed out after 2400s.
- QuixBugs, LangChain, and Qdrant recorded graph failures.
- Most measured repositories clustered at exactly 85.00 overall with Build score
  fixed at 60, indicating proxy scoring rather than human-validated quality.

## Workflow Validation

### 1. Fresh Install Experience

Confusion points:

- Root `README.md` still leads with the old JARVIS assistant runtime and
  `py -3 main.py`, not the Atlas desktop beta path.
- `jarvis_desktop/README.md` is much clearer, but a fresh user may never find it.
- `installer/README.md` calls `Atlas_Setup.exe` "self-contained" but also says
  runtime requires Python 3.10+.
- `installer/output/Atlas_Setup.exe` was not present in the workspace.
- `installer/README.md` uninstall copy still says "JARVIS Desktop".

Failures:

- Default app data directory was not writable on this machine, so startup checks
  fail without redirecting `JARVIS_DESKTOP_DATA`.

Missing guidance:

- No single "Start here for beta users" document at repo root.
- No prominent "do not pip install the monorepo requirements" warning in the
  top-level README.
- No clear Mac/Linux launch path in the main README.

Crashes:

- No crash observed, but startup readiness failure would divert a user to
  support on first launch.

Misleading outputs:

- "Self-contained installer" overpromises because Python is still required.

### 2. First Launch Experience

Confusion points:

- There are two launchers: `run_jarvis_desktop.py` with legacy JARVIS naming and
  `run_atlas.py` with startup checks.
- The legacy launcher does not run the Phase 143 preflight support redirect.
- If users follow older docs, they may bypass the best first-launch path.

Failures:

- Default startup checks currently report `ready=false` because
  `C:\Users\babi2\.jarvis_desktop` is not writable.

Missing guidance:

- Port conflict handling exists only as a command-line flag; no visible
  first-launch auto-recovery was verified.
- The app depends on CDN-loaded Three.js and 3d-force-graph for the premium graph
  first impression.

Crashes:

- None observed in API path.

Misleading outputs:

- Support opens for startup failure, but the hint says "Repair the installation
  or reinstall from Atlas_Setup.exe" even when the issue is a local data
  directory permission problem.

### 3. Sample Repository Workflow

Confusion points:

- The sample path is fast and useful, but the workflow examples are not all
  guaranteed to work against the selected sample.
- The small demo is too small to make Build/Investigation look trustworthy for
  common beta prompts.

Failures:

- Demo Impact quick-start target `core/util.py` returned `mock=true` with
  evidence "No module node matched `core/util.py`."

Missing guidance:

- The sample flow does not warn that tiny samples are presentation examples, not
  realistic quality proof.

Crashes:

- None observed.

Misleading outputs:

- Demo Investigation for "why are duplicate events being fired" produced an
  investigation report whose formatted head referenced EMA/trading domain
  knowledge. That looks unrelated to the user's symptom.

### 4. Real Repository Workflow

Confusion points:

- Requests scan worked quickly, but it reported 185 unresolved imports and a
  73.71% unresolved ratio while graph health still said healthy. The detailed
  internal/external explanation exists in summary, but a beta user can still see
  the raw ratio and distrust the result.

Failures:

- No API failure on Requests.
- Prior benchmark: Atlas self-scan timed out after 2400s.
- Prior benchmark: QuixBugs, LangChain, and Qdrant had graph failures.

Missing guidance:

- Large-repo expected scan time is not made painfully obvious before a user
  points Atlas at something Home Assistant-sized.

Crashes:

- None observed in small real repo smoke.

Misleading outputs:

- Benchmark scores can remain high even when graph quality is weak or no edges
  exist, so "successful scan" can overstate usefulness.

### 5. Build Plan Workflow

Confusion points:

- "add rate limiting" is recognized enough to show Rate Limiting domain text,
  but the returned intent is still `general`.
- On the small demo, Build Plan returned no first files and low-medium
  confidence, yet the report still looks substantial.

Failures:

- No API crash.

Missing guidance:

- Build Plan does not clearly distinguish "repository-backed plan" from
  "generic/domain template with weak repo mapping" at the top of the result.

Crashes:

- None observed.

Misleading outputs:

- Prior benchmark shows Build score was uniformly 60 across measured repos.
  This makes Build Plan the weakest repeated workflow.

### 6. Investigation Workflow

Confusion points:

- The report uses confident workflow formatting even when localization is weak.
- Requests investigation for "HTTP connection pool leak after retry" identified
  `src/requests/sessions.py` in formatted text, but the extracted evidence shown
  by the API smoke was mostly from `src/requests/__init__.py`.

Failures:

- No API crash.

Missing guidance:

- Investigation does not force the user to paste a traceback, log, or failing
  test, so vague symptoms can produce plausible but low-evidence output.

Crashes:

- None observed.

Misleading outputs:

- Demo investigation mapped duplicate events to unrelated EMA/trading knowledge.

### 7. Impact Workflow

Confusion points:

- Exact file impact can work well when the target is in graph.
- The sample quick-start can produce target-not-found, making the feature look
  broken in the first minute.

Failures:

- Demo `core/util.py` impact returned a mock/heuristic target-not-found result.
- Legacy `/api/impact` still has a mock fallback code path, though the UI uses
  `/api/planning/impact`.

Missing guidance:

- Users need clearer "choose a graph node or use an architecture concept" help
  directly next to the input.

Crashes:

- None observed.

Misleading outputs:

- A mock/heuristic impact result still returns `ok=true`, which is risky for
  external beta trust even when visibly tagged.

### 8. Export Workflow

Confusion points:

- Export works technically and is concise.
- The export content still says `JARVIS REPOSITORY CONTEXT` rather than Atlas,
  creating brand mismatch at the exact handoff to Codex/Claude/Cursor.

Failures:

- No API crash.

Missing guidance:

- Export screen needs sharper "copy this, paste it into X with your actual task"
  guidance for first-time users.

Crashes:

- None observed.

Misleading outputs:

- Token savings are estimates and correctly marked as such in code, but beta
  users may interpret compact packet size as proof of answer quality.

### 9. Support Workflow

Confusion points:

- Support page can export diagnostics and support bundle, but there is no real
  support destination.
- `contact.html` explicitly says the public contact channel is not configured.
- Feedback button says "Send feedback" and toasts "feedback saved", but it only
  stores localStorage until manually exported.

Failures:

- Default data-dir permission issue means analytics/support logs can fail in the
  default location.

Missing guidance:

- No visible support email, issue tracker, Discord, or upload channel for the
  exported support bundle.
- No clear "send this zip to..." instruction.

Crashes:

- None observed in support bundle generation.

Misleading outputs:

- "Send feedback" implies feedback was transmitted; it was only saved locally.

## Top 20 Issues Before Beta Launch

| Rank | Severity | Issue | Evidence | Beta risk |
|---:|---|---|---|---|
| 1 | Critical | Default startup readiness fails on this machine | `startup_checks.ready=false`, permission denied writing `.jarvis_desktop/.write_test` | First launch can fail before value |
| 2 | Critical | Targeted beta tests fail | 3 failed, 15 passed | Release branch is not clean enough for beta |
| 3 | Critical | Fresh install entry point is unclear | root README leads with `py -3 main.py`; desktop README is separate | Users run the wrong product |
| 4 | Critical | No installer artifact present | `installer/output/Atlas_Setup.exe` absent | "One-click install" cannot be validated from workspace |
| 5 | Critical | Atlas self-scan times out | prior benchmark timeout after 2400s | Dogfooding failure undermines trust |
| 6 | High | Sample Impact example is broken | `core/util.py` returns `mock=true`, target not found | First-minute workflow can look fake |
| 7 | High | Feedback/support is local-only but looks sent | feedback uses localStorage and toast says saved | Beta feedback can be lost |
| 8 | High | No configured contact/support channel | `contact.html` says public contact channel not configured | Testers have nowhere to send issues |
| 9 | High | Atlas/JARVIS branding is inconsistent | desktop README, beta/demo/gallery/admin/feedback/export still contain JARVIS | Product looks unfinished |
| 10 | High | CDN graph dependency can break offline first impression | `index.html` loads Three.js and 3d-force-graph from unpkg | Premium graph may disappear offline/corporate network |
| 11 | High | Build Plan quality is weakest repeated workflow | overnight Build score 60 for every measured repo | Core "plan a change" promise underdelivers |
| 12 | High | Build Plan can look specific while intent is generic | `add rate limiting` returned `intent=general` | User may overtrust generic advice |
| 13 | High | Investigation can use unrelated domain knowledge | demo duplicate-events query surfaced EMA/trading knowledge | Hallucination-like user experience |
| 14 | High | Weak/no-edge graphs still produce successful downstream outputs | QuixBugs/LangChain/Qdrant graph failures but high proxy scores | False confidence on unsupported repos |
| 15 | High | Large repo scans can feel frozen | Home Assistant took 494.804s; Atlas self timed out | Users kill app or assume crash |
| 16 | Medium | Unresolved import UX is hard to trust | Requests unresolved ratio 73.71% but health healthy; VS Code unresolved 67,338 | Users challenge graph health |
| 17 | Medium | Legacy mock impact path remains reachable | `_impact_mock()` returns `ok=true` in `/api/impact` path | A consumer can treat heuristic fallback as success |
| 18 | Medium | Support hint is too generic for data-dir failure | says reinstall/repair, not fix writable data directory | Support loop is longer than necessary |
| 19 | Medium | Export still says JARVIS context | API smoke export text begins `JARVIS REPOSITORY CONTEXT` | Confusing handoff to external AI tools |
| 20 | Medium | Installer docs contradict runtime reality | "self-contained" but Python 3.10+ required | Installation expectations are wrong |

## Crashes Observed

No Python exception crashed the API smoke. The serious reliability issue is
startup readiness failure from default data-dir permission denial, plus targeted
test failures.

## Misleading Outputs Observed

- `ok=true` on mock/heuristic impact fallback.
- Demo investigation maps "duplicate events" to unrelated EMA/trading domain
  evidence.
- Build Plan presents rich domain text while the classifier intent remains
  `general`.
- Export packet and several static pages still say JARVIS.
- Feedback "send" behavior only saves locally.
- Proxy benchmark quality scores cluster at 85 and do not prove correctness.

## What Worked

- Startup checks can pass when app data is writable.
- Sample demo loads quickly.
- Requests real repo scan completes quickly.
- Exact-file impact on `src/requests/sessions.py` produces useful import and
  verification evidence.
- Context export is fast and compact.
- Support bundle generation works without crashing.
- Empty/missing path validation is friendly.

## What I Did Not Verify

- I did not manually open the native Windows folder picker in a foreground
  browser window during this pass.
- I did not run a full browser click-through or screenshot pass.
- I did not run the full `jarvis_desktop/tests` suite.
- I did not run a new Home Assistant or VS Code scan; prior benchmark results
  were used for large-repo evidence.

## Recommended Gate Before External Beta

Atlas should not go to unsupervised external beta until these are true:

1. Default startup checks pass on a clean user profile or provide an exact
   writable-directory fix.
2. Phase 139/141/143 beta tests pass or stale tests are deliberately retired.
3. The sample workflow has no target-not-found or mock-success path.
4. Feedback/support has a real destination or the UI says "saved locally, export
   and send manually."
5. Branding is consistently Atlas across app, docs, support, exports, installer,
   and marketing pages.
6. Large-repo scan expectations and cancellation/recovery guidance are obvious.
7. Graph health and unresolved imports are explained in the first-order UI, not
   just hidden in detailed payloads.
8. Proxy quality scores are not presented as correctness.

## Final Beta Readiness Assessment

Supervised internal demo: GO.

First external beta: NO-GO.

Reason: the product has enough working core workflow to demo live, but not enough
self-serve install/support trust for external developers to test without close
operator supervision.
