# Phase 116C Desktop UI/UX Product Audit

**Date:** 2026-06-02
**Audit type:** Desktop product audit plus narrowly scoped UI fixes
**Observed committed baseline:** `f9c45a36 phase116b: fix graph hover lag on large repositories`
**Verdict:** **NO-GO for first external beta testers.**
**Supervised internal demo:** **GO.**

## Executive Assessment

JARVIS Desktop is now a real local repository-intelligence product shell rather
than a static presentation. A first-time user can open Home, validate a path,
scan a repository, inspect scan results, load Demo Mode, open Command Center,
switch graph views, ask the bounded Copilot, inspect direct impact evidence, and
export compact AI context.

The desktop is visibly closer to beta quality after the Phase 114-116 work:

- FastAPI scanned through the live UI in `2.79s`.
- Django scanned through the localhost API in `15.52s`.
- VS Code scanned through the localhost API in `5.20s`.
- VS Code automatically opened a six-node subsystem overview instead of trying
  to render all `8,144` modules.
- The full desktop suite passed: `146 passed in 20.70s`.

The remaining beta blockers are trust issues, not missing visual ambition. The
current scope model can treat docs fixtures as production code, the health badge
can say `healthy` with tens of thousands of unresolved imports, cycle counts are
still non-canonical, and repository-derived strings still reach `innerHTML`
sinks. Those issues can make a polished answer confidently misleading.

## Audit Boundary

This workspace was actively changing during the audit. Phase 116B landed while
the audit was running, and additional uncommitted Phase 116D/F work appeared in
overlapping desktop files. The conclusions below distinguish:

- live behavior verified against the current localhost server;
- committed Phase 116B behavior;
- concurrent uncommitted work that was present but not treated as a stable
  release baseline.

The live server answered with version `phase116d-browse-subsystem-graph` while
the current source later reported `phase116f-analytics-isolation`. A restart is
required before treating the latest source as the running release candidate.

## GO / NO-GO

**NO-GO for first external beta testers.**

The product is appropriate for supervised internal demos and continued UX
testing. Before an external beta, fix the trust blockers listed below, freeze one
desktop snapshot, restart from that snapshot, run the desktop suite, and capture
one visual QA matrix.

## Repository Scan Evidence

| Repository | Verification path | Files indexed | Modules | Edges | Scan time | Product observation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Bundled small demo | Live browser | `6` | `5` | `4` | `0.01s` | Demo badge and scan success state work |
| FastAPI | Live browser Home -> Validate -> Scan | `2,753` | `525` | `603` | `2.79s` | Normal scan flow is responsive and clear |
| Django | Localhost API | `6,868` | `933` | `2,916` | `15.52s` | Import-level graph returned with `full_graph_pending=true` |
| VS Code | Localhost API plus live browser refresh | `14,871` | `8,144` | `13,224` | `5.20s` | Massive Repository Mode correctly defaults to subsystem overview |

## Screen Audit Table

| Screen | Flow tested | Result | Issues | Severity | Fix needed |
| --- | --- | --- | --- | --- | --- |
| Home | Launch, onboarding dismissal, refresh, manual path entry, Validate, recent repo chip, Browse click | **PASS with caveat** | Native picker returned clean cancellation in the hidden preview; visible Explorer selection could not be confirmed. Cards remain `div` click targets rather than keyboard-native controls. | P1 | Verify native picker in a normal foreground launch; make cards keyboard accessible |
| Scan | FastAPI validation and scan through UI; Demo Mode scan; failure states inspected in source/tests | **PASS with trust issue** | The displayed stage list still includes contracts and verification evidence even though backend markers disclose there is no dedicated extraction step. | P0 | Show only stages that perform real work, or label skipped stages honestly |
| Command Center | FastAPI module graph; VS Code massive fallback; graph view toggles; refresh | **PASS with trust issues** | Health can be `healthy` with very high unresolved imports. Token savings still looks more precise than its estimate basis warrants. | P0 | Tighten health semantics and relabel token estimate |
| Intelligence | FastAPI summary and subsystem map | **FAIL trust gate** | `docs_src` dominated FastAPI as `449` production files. Runtime flow remains a fixed conceptual sequence while UI says it is derived. | P0 | Fix production-scope classification and clearly label conceptual runtime flow |
| Impact | Page load plus VS Code direct-impact API probe | **PASS with limitation** | Real direct reverse-import result worked (`330` importers), but the UI still represents direct-only evidence as the available impact answer. | P1 | Keep direct-only limitation visible beside result; do not imply transitive blast radius |
| Bug Hunt | Page load plus VS Code heuristic localization probe | **PASS with limitation** | Heuristic path match returned high confidence for a cited file. It remains a review lead, not defect confirmation. | P0 | Keep heuristic disclosure visible for every result state |
| AI Export | FastAPI page load and compact packet preview; VS Code compact export API | **PASS with trust issue** | FastAPI export was distorted by docs fixtures classified as production. | P0 | Fix scope before promoting export quality externally |
| Demo Mode | Home -> Try Demo -> Scan success -> Command Center | **PASS** | Reported cycle count is inflated: the two-node ring is represented twice in reverse directions. | P0 | Canonicalize import cycles |
| Product Tour | Start recording-style tour; stop through floating control | **PASS after fix** | Before the fix, Screenshot Mode hid the normal Stop button. After the fix, the floating control exits cleanly. | Fixed | Keep regression coverage |
| Massive Repository Mode | VS Code refresh -> Command Center | **PASS** | Mode is clearly labeled and defaults to subsystem graph with warning. Health still overstates confidence with `69,039` unresolved imports. | P0 | Preserve UX; revise health scoring |
| Hierarchy Drilldown | Module -> subsystem -> hierarchy toggle; hierarchy counts | **PASS at top level** | Top-level hierarchy payload rendered. Deep canvas drilldown was not manually exercised because graph screenshot/canvas inspection timed out in the embedded browser. | P1 | Add automated drilldown interaction coverage |
| Module Inspector | Source callback and API behavior inspected; Phase 116B test coverage passed | **PARTIAL** | Canvas node click could not be driven reliably in the embedded browser after screenshot capture timeouts. | P1 | Add browser-level click/inspector smoke with a stable local harness |
| Copilot | FastAPI risk answer live; bounded suggestion source inspected; duplicate-send analytics reproduced | **PASS after fix** | One Send click previously produced two API requests. Fixed by removing redundant boot listener. Copilot remains deterministic and bounded. | Fixed | Keep one-click regression test |
| Export Demo Bundle | Localhost API export | **PASS** | ZIP payload returned. Browser download click was not needed for acceptance. | P2 | Add one browser download smoke later |
| Screenshot Mode | Enter and exit live | **PASS after fix** | Before the fix, entering Screenshot Mode hid its only exit button. | Fixed | Keep floating exit control |

## Graph Interaction Smoothness

### Is The Graph Real?

Yes. Module and subsystem payloads come from repository dependency scans. The
live FastAPI Command Center rendered:

```text
module - 525 nodes - 603 edges - production - 4 galaxies - 435 bridges - loaded 47ms
```

The live VS Code Command Center rendered the safe massive-repository fallback:

```text
subsystem - 6 nodes - 2 edges - production - showing 6/8144 modules - loaded 16ms
```

### Hover Lag Cause

The prior lag source was the frontend hover hot path in
`jarvis_desktop/static/universe.js`: hover updates refreshed graph styling while
walking graph relationships repeatedly during mouse movement.

Committed Phase 116B now:

- precomputes adjacency with `buildAdjacencyMaps`;
- schedules hover work through `requestAnimationFrame`;
- ignores duplicate hover IDs;
- caps hover neighbors at `100` for large graphs;
- caps selected neighbors at `250`;
- installs graph accessors once;
- disables directional particles and pulse animation for large graphs;
- exposes optional hover timing diagnostics.

This is the right shape of fix. It avoids a broad graph rewrite.

### Graph Verification Results

| Interaction | Result | Evidence |
| --- | --- | --- |
| Module graph render | PASS | FastAPI live render: `525` nodes, `603` edges |
| Subsystem toggle | PASS | FastAPI switched to `4` subsystem nodes |
| Hierarchy toggle | PASS | FastAPI hierarchy counts rendered |
| Massive fallback | PASS | VS Code defaulted to `6/8144` subsystem overview |
| Graph clears on view change | PASS in source/tests | `STATE.graph`, `STATE.graph3d`, and performance state clear |
| Hover hot path | PASS in source/tests | Phase 116B adjacency and scheduling tests passed |
| Selected node highlight | Covered in source/tests | `showNode`, inspector render, and selection refresh remain wired |
| Canvas click -> inspector | Not fully live-verified | Embedded graph screenshot/canvas capture timed out |
| Screenshot capture | Environment-limited | `Page.captureScreenshot` timed out with active 3D graph |

## Fixed During Phase 116C

### Native Browse Flow

- Added localhost-only `POST /api/system/browse-folder`.
- Added a bounded native Windows folder-picker worker.
- Added clean cancellation and unsupported-environment responses.
- Added a Home-screen Browse button.
- Added automatic validation after a selected path returns.
- Preserved manual paste-path and recent-repository flows.

### Copilot Double Execution

One visible Send click incremented local `copilot_question` analytics from `59`
to `61`. The button already had an inline click command and boot added a second
listener. The redundant boot listener was removed.

### Screenshot Mode Escape

Screenshot Mode hid the graph header, including its own exit button. A floating
exit control now appears only while presentation mode is active.

### Product Tour Cleanup

Product Tour uses Screenshot Mode for a clean recording. Its floating control
now says `Stop tour`, exits presentation mode, and hides both tour panels.

## Remaining External-Beta Blockers

1. **Production scope is not trustworthy enough.** FastAPI classified
   `docs_src` fixtures as `449` production modules, distorting subsystem maps,
   ranking, and AI export.
2. **Graph health is too optimistic.** VS Code was labeled `healthy` with
   `69,039` unresolved imports.
3. **Cycle counts remain non-canonical.** The bundled two-node demo cycle is
   counted twice; Django reported `80` cycles and should be audited for the same
   duplication pattern.
4. **Repository-derived HTML is not consistently escaped.** Several frontend
   surfaces still render API strings with `innerHTML`.
5. **Scan stages overstate backend work.** Contract and verification-evidence
   stages appear even when there is no dedicated desktop extraction step.
6. **Bug Hunt must remain visibly heuristic.** A referenced path can produce
   high confidence without defect proof.
7. **Token savings is presented too prominently.** It is an estimate, not a
   frozen benchmark result.
8. **The flagship graph still depends on CDN assets.** Offline behavior is
   degraded.
9. **Native Explorer visibility needs foreground verification.** The hidden
   preview returned clean cancellation but did not surface a visible dialog.
10. **Freeze one release snapshot.** Concurrent Phase 116D/F edits overlapped
    this audit; restart and verify the final merged state.

### Clean Snapshot Release Blocker

An archive of the committed tree could not collect the desktop suite because
tracked Builder Core code imports `builder_core.bug_intelligence.export_index`,
while `builder_core/bug_intelligence/export_index.py` remains untracked in the
shared working tree. The live worktree masks this packaging failure. Track the
required Builder Core module in its owning phase before publishing a release.

## Exact Files Likely Needing Follow-Up

| File | Follow-up |
| --- | --- |
| `jarvis_desktop/api.py` | Health semantics, scan-stage truthfulness, Bug Hunt disclosure, token estimate labeling |
| `jarvis_desktop/static/app.js` | Safe DOM rendering, honest stage labels, persistent limitations |
| `jarvis_desktop/static/universe.js` | Keep Phase 116B performance path; add stable browser-level inspector smoke |
| `jarvis_desktop/static/index.html` | Accessibility controls and bundled graph runtime |
| `jarvis_desktop/static/styles.css` | Small-window and keyboard focus polish |
| `jarvis_desktop/system_browse.py` | Foreground Windows verification and final contract freeze |
| `builder_core/repository_understanding.py` | Production-role classification audit for docs fixtures |
| `builder_core/bug_intelligence/depgraph.py` | Canonical import-cycle representation |
| `builder_core/bug_intelligence/export_index.py` | Track the required module in its owning Builder Core phase before release |
| `jarvis_desktop/tests/` | Stable interaction smoke, cycle truthfulness, health semantics, and foreground Browse verification |

## Tests

Focused no-temp verification:

```text
py -3 -m pytest \
  jarvis_desktop/tests/test_phase116c_native_browse_flow.py::<selected no-temp tests> \
  jarvis_desktop/tests/test_hotfix_validate_endpoint.py::<route tests> \
  jarvis_desktop/tests/test_phase107_desktop_api.py::<route tests> \
  -q -p no:cacheprovider

12 passed in 0.13s
```

Full isolated desktop suite:

```text
py -3 -m pytest jarvis_desktop/tests -q -p no:cacheprovider --basetemp <isolated-temp>

146 passed in 20.70s
```

The first sandbox runs were blocked by managed temporary-directory permissions.
The isolated elevated run created its temp parent explicitly and completed
cleanly.

Post-commit shared-worktree verification also passed:

```text
146 passed in 20.89s
```

A committed-tree archive check intentionally excluded untracked files and
failed during collection because the required Builder Core
`export_index.py` module is still untracked. This is an existing packaging
blocker outside the Phase 116C desktop scope.

## Screenshots

No usable screenshots were captured. The in-app browser rendered and exposed the
DOM successfully, but screenshot capture timed out while the active 3D graph was
running. Capture a foreground desktop and narrow-window screenshot matrix after
the final snapshot is frozen.

## Final Recommendation

The desktop is close enough to keep investing in product polish. The graph is
real, massive-mode behavior is materially better, and the basic developer loop
works. Do not add more cinematic features yet.

Fix trustworthiness first:

1. correct production scope;
2. correct health and cycle semantics;
3. sanitize rendered repository strings;
4. make scan and Bug Hunt disclosures fully honest;
5. freeze, restart, and visually verify one release candidate.
