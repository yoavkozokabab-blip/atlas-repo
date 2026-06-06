# Phase 154 - Installation and First-Use Friction Audit

Date: 2026-06-04

Scope: observation and validation only. No Atlas source code, intelligence,
detectors, routing, billing, or UI behavior was modified. This report is the
only intended workspace artifact from this pass.

## Verdict

Atlas is usable when a supervised tester is handed the packaged executable and
starts with the sample repository. It is not yet safe for semi-self-serve beta
distribution because the installer path failed in this hostile local test, the
support copy is stale for packaged users, and several workflows still produce
outputs that look more certain than the evidence supports.

| Audience | Verdict | Reason |
|---|---|---|
| 5 supervised users | GO, supervised only | `dist/Atlas/Atlas.exe` starts without Python commands, sample and real-repo API workflows work, and support bundle generation works. Use direct operator support and start every tester on the sample repo. |
| 20 semi-self-serve users | NO-GO | Installer failed under this profile, browser auto-open was not visually confirmed, support channel remains unclear, and investigation/build quality can mislead. |
| Public waitlist users | NO-GO for downloadable beta | Unsigned installer, CDN dependency, stale support copy, and broad-repo quality gaps would create avoidable trust loss. |

## Method and Limits

Validated on the current Windows workspace using the packaged executable and
the local HTTP API at `http://127.0.0.1:8777`.

Screenshots were not captured because no headless browser or Playwright runtime
was available in the validation environment, and no Chrome/Edge browser binary
was available on PATH. Browser auto-open was therefore not visually confirmed;
server readiness and HTTP page loading were confirmed.

The "clean Windows install" path could not be tested on a clean VM. A silent
installer run into a temp directory was attempted and failed with permission
errors, which is recorded as a real hostile-environment finding.

## Commands Run

```powershell
Start-Process .\dist\Atlas\Atlas.exe -WindowStyle Hidden -PassThru
Invoke-RestMethod http://127.0.0.1:8777/api/health
Invoke-RestMethod http://127.0.0.1:8777/api/demo/load -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/planning/change -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/planning/investigate -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/planning/impact -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/context/export -Method POST
Invoke-RestMethod http://127.0.0.1:8777/api/system/support-bundle -Method POST
.\installer\output\Atlas_Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS /DIR="<temp>\AtlasPhase154Install"
```

## Installation Path

| Check | Result | Evidence |
|---|---|---|
| Installer artifact exists | PASS | `installer/output/Atlas_Setup.exe`, 11,699,027 bytes |
| Packaged exe exists | PASS | `dist/Atlas/Atlas.exe`, 3,012,509 bytes |
| Bundled Python present | PASS | `dist/Atlas/_internal/python313.dll`, 6,083,856 bytes |
| Direct exe launch | PASS | `/api/health` reachable; product `ATLAS`; version `phase146b-true-beta-blocker-fixes` |
| No terminal required for exe | PASS by packaging inspection | PyInstaller entry is windowed; launch used `Atlas.exe`, not `py -3` |
| Installer silent install | FAIL in this environment | Exit code 4 |
| Installer failure cause | FAIL | `IPersistFile::Save failed; code 0x80070005`; `RegCreateKeyEx failed; code 5` while creating shortcuts/uninstall registry key |
| Browser opens automatically | PARTIAL | Server opened and static pages loaded; no browser process/window was visually confirmed |
| SmartScreen/antivirus friction | NOT VERIFIED | Artifact is unsigned; clean download path not tested |

The direct packaged executable is the strongest current install evidence. The
installer is not beta-safe until it is validated on a clean Windows profile and
on a locked-down standard user profile.

## First-Use Measurements

Measured from the local API after `Atlas.exe` was running.

| Workflow | Result | Duration |
|---|---:|---:|
| Health check | PASS | 0.110s |
| Load sample repo | PASS | 0.051s |
| Sample Build Plan: `add rate limiting` | PASS technically | 0.394s |
| Sample Investigation: `why are duplicate events being fired` | PASS technically | 0.084s |
| Sample Impact: `core/hub.py` | PASS | 0.015s |
| Sample Export: Codex compact | PASS | 0.013s, 288 estimated tokens |
| Support status | PASS | 0.013s |
| Support bundle | PASS | 0.014s |

Estimated user clicks on happy path:

- First successful Build Plan: 2 primary clicks after app open (`Load Sample Repository`, `Generate Change Plan`), plus any welcome modal choice.
- First export: 1-2 more clicks after scan (`Export`, `Copy to clipboard`).
- Confusing moments on happy path: about 4-6, mostly welcome/tour choices, "Build Plan" vs "Generate Change Plan", technical output density, and support/diagnostics buttons.

## Real Repository Workflow

| Repo | Files | Modules | Edges | Scan | Build | Investigate | Impact | Export |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Requests | 125 | 20 | 66 | 0.530s | 0.089s | 0.107s | 0.062s | 0.013s |
| FastAPI | 2,753 | 73 | 159 | 9.017s | 0.094s | 0.097s | 0.018s | 0.003s |

Functional result: both real repositories scan and all three core workflows
return without crashing.

Trust result: not beta-clean yet. FastAPI Build Plan included `scripts` and a
Playwright screenshot helper in likely affected files for "add request rate
limiting"; this looks like production-scope pollution. Investigation produced
weak top root-cause lines such as `__future__.annotations` and `re`, which a
developer will read as nonsense even when the broader likely area is plausible.

## Support Path

Support bundle generation works and the bundle does not include source files.
In-memory zip entries were:

```text
manifest.json
version.txt
diagnostics.json
environment.json
scan_metadata.json
startup_checks.json
logs/launcher.log
logs/analytics.jsonl
```

Support page copy is improved but stale for the packaged beta. It still says:

- "Install Python 3.10+"
- "On Windows use Launch Atlas.bat"
- "On Mac/Linux use python3 run_atlas.py"

That is the opposite of the Phase 149/150 goal for a non-technical beta user:
download installer, run Atlas, browser opens, no Python.

## Claude/Cursor/Codex Workflow

Export works and now uses Atlas branding:

```text
# ATLAS REPOSITORY CONTEXT
```

The export screen has clear enough copy: copy the packet, paste it into Claude,
Codex, or Cursor, then ask the assistant to implement or review. Token counts
are explicitly estimates. This path is demo-usable.

Remaining friction: target/packet choices (`compact`, `verbose`, estimated
tokens) are useful for power users but still jargon-heavy for a first session.

## Top 20 Friction Points

| Rank | Severity | Issue | Evidence |
|---:|---|---|---|
| 1 | Critical | Installer failed in this hostile local install attempt | Exit code 4; shortcut and HKCU uninstall registry permission denied |
| 2 | Critical | Clean no-Python VM install remains unproven | Direct exe works; true clean-machine install was not available |
| 3 | Critical | Browser auto-open not visually confirmed | Server reachable, but no visible browser automation/screenshot proof |
| 4 | Critical | Support page gives packaged users Python/BAT instructions | `support.html` still tells users to install Python 3.10+ |
| 5 | High | Default packaged data path fell back to temp | Startup status: `fallback=temp`, data dir under `%TEMP%` |
| 6 | High | Installer is unsigned; SmartScreen risk remains | No signing evidence; antivirus/SmartScreen not tested |
| 7 | High | Support destination is still unclear | Bundle works, but user is not clearly told where to send it |
| 8 | High | First screen has too many equal-feeling paths | Sample, walkthrough, scan repo, task cards, repo picker |
| 9 | High | Two onboarding systems can still appear | Welcome screen plus onboarding/tour code still exists |
| 10 | High | Pre-scan task cards can route to gated empty states | Cards call feature views before scan and rely on recovery panels |
| 11 | High | Build Plan output can look specific with weak grounding | Sample has no first files; FastAPI includes questionable scripts |
| 12 | High | Investigation top hypothesis can be nonsense | Requests: `__future__.annotations`; FastAPI: `re` as likely root cause |
| 13 | High | FastAPI production scope still includes scripts/examples | Rate limiting plan surfaced `scripts/playwright/.../image02.py` |
| 14 | Medium | Graph health wording can understate unresolved import concern | Requests unresolved ratio 73.71%; FastAPI 77.89% |
| 15 | Medium | Diagnostics field naming is misleading | `scan_statistics.unresolved_internal` showed 560 while graph health said internal unresolved was 0 |
| 16 | Medium | CDN dependency remains for premium graph and fonts | `index.html` uses Google Fonts, Three.js, and 3d-force-graph from external URLs |
| 17 | Medium | Large-repo scan expectations remain risky | Prior evidence: Home Assistant ~494.8s; Atlas self timeout |
| 18 | Medium | Product version is stale relative to packaging phase | Build reports `phase146b-true-beta-blocker-fixes` |
| 19 | Medium | Root launch scripts still mention Python path | `Launch Atlas.bat` still falls back to `py -3 run_atlas.py` |
| 20 | Medium | Support/diagnostics buttons make first screen feel technical | Visible Support, Diagnostics, Report Issue before first success |

## Critical Blockers

1. Installer must succeed on clean and locked-down Windows profiles.
2. Packaged support copy must stop telling beta users to install Python.
3. Browser auto-open needs real manual verification, not just server readiness.
4. A real support destination must exist before semi-self-serve testers.
5. Build/Investigation must surface low-confidence or weak-grounding warnings
   before confident-looking details.

## Quick Wins

1. Replace packaged Support FAQ startup advice with installer/exe-first advice.
2. Add a visible "Send this bundle to ..." support destination.
3. Add a top-level "evidence strength" banner to Build Plan and Investigation.
4. Hide or disable task cards until a sample or repo is loaded, or make each
   card load the sample first.
5. Rename "Generate Change Plan" to match "Build Plan" consistently.
6. Show data-dir fallback in Support when Atlas is using temp storage.
7. Make FastAPI-style `scripts`, docs, fixtures, and generated examples visibly
   excluded or downgraded in production-scope results.
8. Vendor graph assets locally for offline/corporate beta machines.

## Must Fix Before 20-User Beta

1. Installer succeeds on a clean Windows VM with no Python installed.
2. Installer succeeds or degrades gracefully on a locked-down standard profile.
3. Browser opens automatically and Support opens on failure, verified manually.
4. Support page and installer docs are aligned with self-contained packaging.
5. Support/feedback has an actual destination.
6. First-use path is one obvious path: sample -> Build Plan -> export.
7. Investigation output suppresses or demotes nonsensical root-cause lines.
8. Build Plan does not suggest docs/scripts/examples as likely change files for
   production features unless evidence explicitly supports that.
9. Graph health and diagnostics use consistent unresolved-import terminology.
10. Large-repo scan expectations, cancellation, and partial results are obvious
    before a user points Atlas at a monorepo.

## Final Assessment

Core question: can a normal developer install Atlas, open it, scan a repository,
and use it with Claude/Cursor/Codex without help?

Answer: not reliably yet.

If they receive `Atlas.exe` directly and nothing blocks the browser, they can
open Atlas, load the sample, scan Requests/FastAPI, generate Build/Investigation
/Impact, export a Codex packet, and download a support bundle. The workflow is
real.

If they receive only `Atlas_Setup.exe` and no human support, this pass says
NO-GO. The installer failed in a locked-down local profile, support copy points
users back to Python, and several outputs can undermine trust during the first
useful session.
