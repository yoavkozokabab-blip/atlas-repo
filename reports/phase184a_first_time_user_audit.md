# Phase 184A First-Time User Audit

Date: 2026-06-07

Role: skeptical engineer who found Atlas on Reddit today. I treated the product as unfamiliar and tried the path: install artifact check, launch, load sample, Change Plan, Debug/Investigate, What Breaks/Impact, Copy for Claude.

No code changes were made.

## Verdict

**5 supervised beta users: GO with supervision.**

**20 semi-self-serve users: NO-GO.**

**Public Reddit launch: NO-GO.**

Atlas reaches real value quickly once the sample is loaded, but a first-time user sees enough internal state leaks and workflow inconsistencies that I would not send it broadly without a handler nearby.

## What I Tested

Install artifact:

```text
dist/Atlas/Atlas.exe exists
installer/output/Atlas_Setup.exe exists
```

Self-test:

```powershell
py -3 run_atlas.py --self-test
```

Result:

```text
Atlas self-test: READY
[ok] Atlas launcher (source mode): run_atlas.py present
[ok] Required directories: present
[--] Start menu / desktop shortcuts: no Atlas shortcuts found
[ok] Browser auto-open: default browser available
```

Packaged launch:

```powershell
Start-Process dist\Atlas\Atlas.exe --no-browser
GET http://127.0.0.1:8777/api/health
```

Result:

```json
{
  "ok": true,
  "product": "ATLAS",
  "version": "phase146b-true-beta-blocker-fixes",
  "repository_open": false
}
```

UI flow:

1. Opened `http://127.0.0.1:8777/`.
2. Read welcome screen.
3. Clicked `Load Sample Repository`.
4. Generated a Change Plan.
5. Ran Investigation for `why are duplicate events being fired`.
6. Ran Impact for `core/hub.py`.
7. Clicked `Copy Claude`.

## Direct Answers

### 1. Do I understand Atlas in under 60 seconds?

**Mostly yes.**

The welcome copy is good enough:

> Atlas maps your repository on your machine and prepares grounded Build Plans for your AI tools. It does not write or apply code for you.

That immediately tells me:

- it is local;
- it analyzes repositories;
- it prepares context/plans;
- it is not an autonomous code editor.

What is still unclear in the first minute:

- whether Atlas is a repo visualizer, a prompt generator, a bug finder, or all three;
- what I should click first after the welcome overlay closes;
- whether "Debug", "Investigate Bug", "Impact", "What Breaks", and "Build Plan" are separate workflows or different labels for the same thing.

### 2. Do I reach value in under 5 minutes?

**Partially.**

I reached a usable Change Plan in under 5 minutes. The plan included real files, tests, rollback steps, and export buttons.

However, the official end of the requested value path, `Copy For Claude`, did not work in my browser run: clicking `Copy Claude` left the browser clipboard empty and produced a browser-side error. The API export route did return a valid Claude packet, so the backend has the content. The user-facing copy action is the broken part observed in this run.

### 3. What would make me quit?

1. **High:** The app says `Build Plan needs a scan` even after I loaded the sample repository.
2. **High:** `Copy Claude` appears successful in the UI flow, but the clipboard was empty in my run.
3. **High:** The packaged app reports an internal version string: `phase146b-true-beta-blocker-fixes`.
4. **High:** The app loads UI dependencies from `unpkg.com`, which weakens the local-first trust story and may fail on locked-down networks.
5. **Medium:** Multiple workflows show "needs a scan" while still allowing generation if I click through.
6. **Medium:** The sample repository is tiny and artificial, so the first "wow" moment feels more like a demo harness than proof.
7. **Medium:** Debug output mixes useful hypotheses with generic backend/domain language that does not fully match the sample repo.
8. **Medium:** The product uses several overlapping labels: Build Plan, Change Plan, Investigate Bug, Debug, Impact, What Breaks, Export context.
9. **Low:** Source-mode launcher still has legacy `JARVIS Desktop` naming in `run_jarvis_desktop.py`.
10. **Low:** Console warnings show deprecated/multiple Three.js imports.

### 4. What would make me recommend it?

1. It launches as a packaged executable without needing Python in the tested packaged path.
2. The welcome screen gives a clear local-first, non-autonomous positioning.
3. Sample scan is fast.
4. Build Plan produces a concrete ordered plan with affected systems, tests, rollback, and limitations.
5. Impact Analysis for `core/hub.py` is understandable and grounded in direct importers.
6. The export API returns a compact Claude prompt with useful repository facts.
7. It repeatedly says it does not edit files or run patches for me, which builds trust.

### 5. What still looks unfinished?

- The scan-state UI is inconsistent after loading the sample.
- Clipboard export is not reliable enough for the core "Atlas + Claude/Cursor/Codex" workflow.
- Demo sample is too small to feel like a real repository proof.
- The health payload and packaged version look like an internal phase build.
- External CDN dependencies are still present in the shipped app page.
- Some UI copy says "about 60 seconds" for the sample load, but the small sample loads nearly instantly.
- The graph is visually rich, but on the tiny sample it is not yet persuasive as a developer tool.

### 6. What still feels internal?

- `version: phase146b-true-beta-blocker-fixes` from packaged `Atlas.exe`.
- `run_jarvis_desktop.py` still says `Launch JARVIS Desktop`.
- Console warnings reference implementation choices users should never need to see.
- Workflow panels expose state-machine seams, especially "needs a scan" after sample is loaded.
- Recent repository paths include packaged internal paths like `dist\Atlas\_internal\jarvis_desktop\demo\small_repo`.

### 7. What would block a beta install?

- I did not run the installer executable to avoid changing this machine's installed programs, so SmartScreen, shortcut creation, uninstall, and clean-machine install were not fully verified in this audit.
- Source self-test reported no Start menu / desktop shortcuts because this was not an installed run.
- `Atlas.exe` itself launches and serves the app, which is good.
- Public beta is still blocked by stale/internal versioning, external CDN reliance, and the copy/export reliability issue.

## Severity Findings

### Critical

None observed that prevents `Atlas.exe` from launching or sample analysis from running in a supervised session.

### High

#### H1: Sample loaded, but workflow panels still say "needs a scan"

Reproduction:

1. Launch `dist\Atlas\Atlas.exe --no-browser`.
2. Open `http://127.0.0.1:8777/`.
3. Click `Load Sample Repository`.
4. Open `Build Plan`, `Investigate Bug`, or `Impact`.

Expected:

- Panels should recognize the loaded sample and show ready state.

Actual:

- Build Plan showed `Build Plan needs a scan`.
- Investigate showed `Investigation needs a scan`.
- Impact showed `Impact analysis needs a scan`.
- Clicking generate/simulate still worked, so this is a UI state/copy bug rather than a backend failure.

User impact:

- This is exactly where a skeptical user wonders whether the product is broken.

#### H2: Copy for Claude failed in the browser run

Reproduction:

1. Load sample.
2. Generate a Change Plan.
3. Click `Copy Claude`.
4. Read browser clipboard.

Expected:

- Clipboard contains a Claude-ready prompt.

Actual:

- Clipboard was empty in this run.
- Browser logs showed:

```text
SyntaxError: Failed to execute 'dispatchEvent' on 'EventTarget': Unexpected end of input
```

Control:

`POST /api/context/export` returned a valid compact Claude packet of about 294 estimated tokens. The backend content exists; the observed issue is the user-facing copy action.

#### H3: Packaged app exposes internal phase version

Reproduction:

```powershell
GET http://127.0.0.1:8777/api/health
```

Actual:

```text
version = phase146b-true-beta-blocker-fixes
```

Expected:

- A beta user should see something like `0.1.0-beta`, not an internal phase name.

#### H4: Shipped UI loads external CDN assets

Evidence:

`jarvis_desktop/static/index.html` includes:

```html
https://unpkg.com/three@0.157.0/build/three.min.js
https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js
https://fonts.googleapis.com/...
```

Expected:

- A local-first desktop app should bundle critical UI assets or clearly disclose optional network usage.

Risk:

- Offline/corporate networks can break the app.
- A privacy-sensitive engineer may not trust "local-first" if the UI immediately contacts external CDNs.

### Medium

#### M1: Sample repository is too artificial to create confidence

The sample has 6 files / 5 modules and contrived modules like `alpha.py`, `beta.py`, `core/hub.py`, and `ring/x.py`. It proves the UI can run, but it does not show Atlas handling a realistic application.

#### M2: Debug/Investigation output is useful but too generic

Prompt:

```text
why are duplicate events being fired
```

Actual:

- It recognized duplicate events and produced plausible hypotheses.
- It also introduced generic backend concepts such as OpenAPI/contract tests and load tests that do not clearly fit the toy sample.

Risk:

- A skeptical engineer may read this as templated reasoning rather than repo-specific intelligence.

#### M3: Naming is still fragmented

The requested user mental model has:

- Install
- Launch
- Load Sample
- Change Plan
- Debug
- What Breaks
- Copy For Claude

The product uses:

- Build Plan
- Generate Change Plan
- Investigate Bug
- Impact Analysis
- Simulate Impact
- Export context
- Copy Claude

The concepts are understandable after use, but not frictionless.

#### M4: Graph feels impressive but not immediately actionable on sample

Repository Map showed modules, risk, cycles, hubs, and graph health. It was not wrong, but on the toy sample the graph feels like a feature preview rather than a decisive developer workflow.

### Low

#### L1: Source-mode legacy naming remains

`run_jarvis_desktop.py` still presents as JARVIS Desktop. That is not visible in the packaged beta path, but it leaks in source/developer mode.

#### L2: Browser console noise

The browser logged deprecated Three.js and multiple Three.js import warnings. Not a normal-user blocker, but it makes the app feel less polished during demos or debugging.

## Workflow Results

| Workflow | Result | Notes |
|---|---:|---|
| Install artifact check | PASS / partial | `Atlas_Setup.exe` and `Atlas.exe` exist. Installer not executed to avoid modifying machine install state. |
| Launch packaged app | PASS | `Atlas.exe --no-browser` launched; health returned OK. |
| First-screen understanding | MOSTLY PASS | Positioning is clear enough in under 60 seconds. |
| Load Sample | PARTIAL | Sample loads server-side, but workflow panels still claim scan is needed. |
| Change Plan | PASS with friction | Generated useful plan after clicking through misleading scan warning. |
| Debug / Investigate | PARTIAL | Generates plausible output, but includes generic/template-feeling concepts. |
| What Breaks / Impact | PASS | `core/hub.py` impact was grounded and readable. |
| Copy For Claude | FAIL in browser run | API has export text; clipboard action observed empty. |

## What Would Make Me Quit

1. Copy/export not working.
2. Seeing internal phase version strings.
3. Seeing "needs a scan" after I already loaded the sample.
4. External CDN calls in a local-first desktop product.
5. Toy demo results that do not convince me it will work on my repo.

## What Would Make Me Recommend It

1. Clean install and launch with no Python.
2. A reliable sample-to-Claude flow where the copied prompt demonstrably works.
3. A realistic sample repository showing a real architecture-level answer.
4. Clear, honest limits: "Atlas prepares context; your AI/editor applies changes."
5. Strong local-first posture with no surprise network dependencies.

## Beta Decision

5 supervised beta users:

**GO**, if the person running the beta knows to explain the sample-state warning and manually verify exports.

20 semi-self-serve users:

**NO-GO**, because copy/export and scan-state trust issues will create avoidable support churn.

Public Reddit launch:

**NO-GO**, because internal version strings, CDN dependencies, and sample workflow inconsistency will be called out quickly by skeptical engineers.

## Exact Files Likely Relevant Later

No fixes were made, but the likely surfaces are:

- `run_atlas.py`
- `run_jarvis_desktop.py`
- `jarvis_desktop/static/index.html`
- `jarvis_desktop/static/app.js`
- `jarvis_desktop/static/atlas_product.js`
- `jarvis_desktop/product_info.py`
- `jarvis_desktop/api.py`
- `installer/`
- `dist/Atlas/`

## Final Take

Atlas is close enough for **guided** beta conversations, not for self-serve discovery. The product has real value: the Change Plan and Impact workflows produce useful, grounded output. The problem is trust at the exact moment a new user is deciding whether the product is real. The next beta gate is not more intelligence; it is making the first sample path feel impossible to misunderstand.
