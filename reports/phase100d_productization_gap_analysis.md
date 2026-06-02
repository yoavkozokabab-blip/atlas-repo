# Phase 100D - Productization Gap Analysis

Date: 2026-06-01

## Executive Verdict

JARVIS Builder Core has enough intelligence for a **concierge private alpha**.
It is not yet ready for an external developer to install independently and use
daily without support.

The missing work is primarily productization:

- one honest user-facing trust model;
- a simple install and first-run path;
- visible, cancellable long-running work;
- state recovery and revision freshness;
- current documentation and a prepared demo;
- editor, Git, and CI integration;
- measured external workflow value.

Do not add more analysis engines before these gaps are closed.

The most important distinction is:

```text
review-intelligence alpha
  !=
confirmed-defect product claim
```

The current stack can be tested externally as a local, read-only repository
intelligence assistant. It must not be marketed as a general bug finder yet.

## Current Capability Baseline

| Capability | Current state | External value |
| --- | --- | --- |
| Repository Understanding | RU-3 routes architectural questions to deterministic index and graph-backed handlers | Helps developers locate production subsystems and entry points |
| Dependency Graph | Phase 94A graph builds resolved static relationships and records unresolved edges honestly | Shows imports, calls, references, cycles, and unknowns |
| Impact Analysis | Phase 94B separates asserted, possible, and unanalyzed impact | Supports change planning without pretending uncertainty is safety |
| Review Intelligence | Phase 95E found `148 / 202` useful review leads (`73.3%`) | Useful triage signal on real repositories |
| Confirmation Gate | Phase 99F remediated C1-C6, proof bundle, shadow mode, impact hook, and default-off governance | Strong internal trust foundation |
| Historical Replay | Phase 99D replays buggy/fixed revisions through the confirmation pipeline | Enables directional validation |
| Historical Corpus | Phase 100A defines a concrete `30`-case v1 assembly slate | Useful plan, but not yet measured execution evidence |
| Real-Repository Validation | Phase 98A scanned `24` pinned repositories with `0` unsafe outcomes | Operational breadth exists |

## Current Readiness Boundaries

### What Is Ready

- Local, deterministic, read-only Python repository analysis.
- Architecture questions grounded in indexed production files.
- Static dependency graph inspection with explicit unresolved relationships.
- Impact analysis with separate asserted and uncertain channels.
- Ranked review leads with evidence and next verification steps.
- Default-off confirmation infrastructure for controlled measurement.
- Read-only replay infrastructure for historical buggy/fixed pairs.

### What Is Not Ready

- Self-serve installation.
- Daily workflow polish.
- Production surfacing of confirmed defects.
- A measured historical confirmation track record.
- A completed Phase 98A human-review pass.
- Editor or CI integration.
- An external onboarding package.
- A supportable external release process.

## Ranked Productization Gaps

| Rank | Gap | Area | Impact | Why it blocks daily use | Priority |
| ---: | --- | --- | --- | --- | --- |
| 1 | External-safe trust surface and release boundary | Trust | Critical | Developers cannot rely on a tool whose output tiers, validation status, and unsupported claims are not presented consistently | P0 |
| 2 | Installable, versioned distribution | Installation | Critical | The current `py -3 -m builder_core.cli` invocation is an internal developer path, not a durable product entry point | P0 |
| 3 | Guided first-run workflow and current documentation | UX / Docs | Critical | The README teaches early Phase 82 commands while graph, impact, RU-3, confirmation, and replay capabilities have moved on | P0 |
| 4 | Progress, cancellation, and atomic state recovery | UX / Reliability | Critical | Large repositories can appear frozen; interruption can leave ambiguous state; routine errors still look like crashes | P0 |
| 5 | Revision freshness and coverage transparency | Trust / UX | High | Developers need to know which commit was analyzed, whether results are stale, and which files or edges were skipped | P0 |
| 6 | Editor, Git, and CI workflow outputs | Adoption | High | Terminal prose alone does not fit daily PR review, issue triage, or team workflows | P1 |
| 7 | Prepared external demo and onboarding kit | Demo | High | The first-ten-user demo is designed but not packaged into a repeatable, facilitator-light experience | P1 |
| 8 | External validation sessions and repeat-use evidence | Adoption | High | Phase 98A proves scanning breadth, not that developers choose to use the tool weekly | P1 |
| 9 | Privacy, retention, and local-state lifecycle controls | Trust / Installation | Medium | External users need to understand exactly what `.jarvis_builder/` contains and how to remove or exclude it safely | P1 |
| 10 | Release support model and troubleshooting bundle | Docs / Adoption | Medium | Daily-use users need a stable support path when repositories degrade, parse partially, or behave differently across environments | P1 |
| 11 | Performance reuse for repeated graph and impact work | Responsiveness | Medium | Graph commands rebuild from source each time; this is honest but may feel expensive on large repositories | P2 |
| 12 | Optional notifications, tray status, and overlay visibility | Polish | Low | Helpful for long jobs, but not required for a capable terminal-first daily tool | P2 |

## 1. UX Gaps

### P0: First Use Still Feels Like an Internal CLI

Live inspection found:

- No `jarvis-builder` command installed.
- No package metadata (`pyproject.toml`, `setup.py`, or `setup.cfg`) at the
  workspace root.
- No visible progress helper.
- No focused Builder UX test module.
- A missing project directory still prints a raw traceback:

```text
ValueError: Project directory does not exist: C:\__jarvis_missing_repo__
```

The first-run experience needs:

- immediate command acknowledgement;
- resolved repository path;
- indexing phases and file counters;
- elapsed time;
- compact completion summary;
- safe `Ctrl+C` cancellation;
- clear next commands after `init`;
- concise expected-error handling;
- explicit debug mode for technical detail.

### P0: State Handling Is Too Ambiguous

The current index write path writes directly to:

```text
<project>/.jarvis_builder/index.json
```

The current read path returns the same `None` result for:

- missing index;
- unreadable index;
- corrupted JSON.

That makes interrupted indexing and damaged local state harder to understand.
Daily use needs:

- atomic index replacement;
- distinct missing, corrupt, incompatible, and stale state messages;
- safe rebuild guidance;
- confirmation that the prior valid index remains after cancellation.

### P1: Output Is Command-Centric Rather Than Workflow-Centric

The CLI has useful commands:

```text
init
ask
risk-report
analyze-file
bug-scan
security-scan
graph
impact-file
impact-module
impact-function
impact-paths
impact
```

The surface still asks the user to understand the internal command taxonomy.
Daily use needs a calmer output envelope:

```text
summary
  -> confidence and coverage
  -> findings or impact
  -> evidence
  -> unknowns and blockers
  -> next inspection step
```

## 2. Installation Friction

### Current Friction

The current documented launch path is:

```powershell
py -3 -m builder_core.cli ...
```

That is functional for the workspace owner, but awkward for an external
developer:

- Windows-specific launcher syntax appears first.
- No installable console entry point exists.
- No frozen alpha package or wheel is documented.
- No Python version support matrix is documented.
- No dependency preflight is exposed.
- No installation verification command is documented.
- No uninstall or local-state cleanup guidance is documented.

### Minimum External-Safe Installation Experience

An external developer should be able to:

1. Install one versioned package.
2. Run:

```text
jarvis-builder --help
```

3. Point it at a repository.
4. See a preflight result before indexing starts.
5. Understand that source files remain read-only.
6. Know that generated local state is contained under `.jarvis_builder/`.
7. Remove the package and local state cleanly.

Keep the module invocation as a documented fallback.

## 3. Documentation Gaps

### Current README Drift

`builder_core/README.md` still centers the original Phase 82 flow:

```text
init
ask
risk-report
benchmark-quixbugs
```

It does not yet explain the full external workflow:

- RU-3 architecture questions;
- dependency graph commands;
- impact commands;
- known-versus-unknown semantics;
- asserted versus possible impact;
- review lead versus strong suspect versus confirmed defect;
- confirmation default-off behavior;
- historical replay as an internal validation workflow;
- corrupted or stale state recovery;
- skipped-file and degraded-scan interpretation;
- Git ignore guidance for `.jarvis_builder/`;
- JSON, SARIF, editor, and CI workflow expectations;
- privacy and retention boundaries.

### Required Documentation Set

| Document | Purpose |
| --- | --- |
| One-page quickstart | Install, initialize, ask, inspect impact, scan, clean up |
| Daily workflow guide | PR review, unfamiliar repository, refactor planning, regression investigation |
| Command reference | Complete current CLI surface with examples |
| Trust model | What is known, possible, blocked, unresolved, review-only, and confirmed |
| Local-data guide | `.jarvis_builder/` contents, Git ignore, retention, deletion |
| Troubleshooting guide | Invalid path, corrupt state, degraded graph, skipped files, unsupported repository |
| Support matrix | Python versions, shells, operating systems, repository-size guidance |
| Validation note | Honest metrics, corpus qualifiers, and unsupported marketing claims |

## 4. Demo Quality

### What Exists

`reports/product_validation_first_10_users.md` defines a strong concierge demo:

```text
repository map
  -> dependency graph
  -> impact analysis
  -> contract review
  -> verification evidence and refutation
```

It also defines:

- a pinned public repository;
- a fallback public repository;
- a one-page question menu;
- a feedback form;
- two waves of five users;
- activation, usefulness, trust, and repeat-intent metrics.

### What Is Missing

The demo is still a plan. Before external sessions:

1. Select and pin the standard public repository.
2. Select and pin the fallback repository.
3. Verify both demo scans from a clean install.
4. Record expected durations.
5. Curate one architecture question, one graph question, one impact question,
   one useful review lead, and one honest blocked or refuted lead.
6. Prepare a short facilitator script.
7. Prepare a self-guided fallback for a developer who wants to explore without
   narration.
8. Avoid phase numbers, benchmark internals, and giant raw finding lists during
   the demo.

### Demo Quality Bar

The demo should prove:

```text
I understand this repository faster.
I can see what may break if I change this.
I know what JARVIS knows and what it does not know.
I can inspect one useful lead without being sold a fake certainty.
```

## 5. Trust Barriers

### P0: Confirmation Is Repaired but Not Product-Validated

Phase 99F is a meaningful improvement:

- C1-C6 aligned;
- mandatory test or runtime witness;
- impact consequence hook;
- empty proof obligations;
- complete bundle;
- shadow mode;
- double default-off gate;
- `371` tests passing.

However, external trust gates remain open:

- Phase 99F section 6.3: Phase 95E rejected-corpus replay remains manual.
- Phase 99F section 6.4: Phase 98A human review remains manual.
- Phase 98A: `300` blinded review packets remain unlabeled.
- Phase 100A: the `30`-case historical corpus is an assembly plan, not a
  completed replay and adjudication result.
- There is no measured historically proven confirmation count yet.

Therefore:

```text
confirmed-defect infrastructure exists
historically proven product claim does not yet exist
```

### P0: Product Vocabulary Must Be Explicit

The external surface must never blend:

| Tier | User-facing meaning |
| --- | --- |
| Architecture fact | Grounded repository structure |
| Asserted impact | Resolved static relationship |
| Possible impact | Unverified relationship worth checking |
| Review lead | Worth human inspection |
| Strong suspect | Static evidence is strong, but proof is incomplete |
| Confirmed defect | Complete in-repo proof bundle under gated rules |
| Historically proven confirmation | Confirmed on buggy revision, cleared on fixed revision, witness flipped, human accepted |
| Unknown or blocked | Evidence is incomplete; do not infer safety |

The strongest trust feature is not confidence language. It is refusing to claim
more than the evidence supports.

### P0: Coverage Gaps Must Be Visible

Phase 98A produced:

- `22` successful scans;
- `2` degraded scans;
- `0` unsafe scans;
- `8,832` grounded findings;
- `7,278` advisory findings.

Daily users need to see:

- analyzed files;
- skipped files;
- parse failures;
- truncated work;
- unresolved imports and calls;
- degraded graph status;
- current branch and commit;
- whether results are fresh or stale.

An empty result without coverage context is not trustworthy.

## 6. Adoption Barriers

### P1: Terminal Prose Does Not Reach Existing Workflows

The CLI currently supports deterministic JSON for graph export and optional
impact JSON. General analysis and scan workflows still need stable
machine-readable output.

Daily adoption requires:

- JSON output for analysis and scans;
- SARIF for CI and code-review surfaces;
- deterministic non-interactive exit codes;
- line-stable redirected output;
- copyable `path:line` source references;
- a VS Code task and problem-matcher example;
- a CI example;
- a Git workflow example for checking the analyzed commit.

Start with standards and examples. A full editor extension is not required for
the first daily-use release.

### P1: No External Usage Evidence Yet

The best current product-positioning evidence is still:

```text
local read-only review intelligence
```

The first-ten-user program has not been executed. Before calling the product
daily-use ready, measure:

- time to first useful answer;
- whether the read-only boundary is understood;
- whether developers ask unprompted questions;
- whether they choose to run it on their own repository;
- whether they name a recurring workflow;
- whether they want to keep using it weekly;
- whether unknown, blocked, or refuted outputs save time.

### P1: Repository Scope Must Be Bounded

The first release should clearly state:

- Python-first repository support;
- practical repository size guidance;
- generated-code exclusions;
- expected degraded behavior;
- no source modification;
- no implicit target-code execution;
- no production security-scanner claim;
- no general bug-finder claim until historical validation earns it.

Bounded expectations improve adoption because they reduce disappointment.

## Private Alpha vs Daily Self-Serve

### Concierge Private Alpha: Close

A carefully facilitated private alpha can begin once these are prepared:

| Requirement | Status |
| --- | --- |
| Honest review-intelligence positioning | Defined |
| Read-only safety statement | Defined |
| RU-3, graph, and impact demo flow | Implemented capabilities |
| Standard demo repository | Must be selected and pinned |
| Fallback demo repository | Must be selected and pinned |
| Demo script and question menu | Designed; must be packaged |
| Clean-install facilitator environment | Must be prepared |
| Severe trust-claim guardrails | Must be enforced in demo wording |

### External Daily Self-Serve: Not Ready

Daily self-serve use needs the P0 productization tranche:

1. Installable versioned package and `jarvis-builder` command.
2. Preflight, friendly errors, atomic state writes, and corruption recovery.
3. Progress, cancellation, completion summaries, and freshness reporting.
4. Complete quickstart, trust model, command reference, and troubleshooting
   documentation.
5. Coverage summaries and honest degraded-state output.
6. Frozen demo package verified from a clean install.

Team adoption then needs the P1 tranche:

1. JSON and SARIF output for scans.
2. Stable CI exit behavior.
3. VS Code task and problem-matcher example.
4. Git workflow guidance.
5. External first-ten-user evidence.

## Work to Defer

Do not block external testing on:

- new detectors;
- new reasoning systems;
- higher synthetic benchmark recall;
- more architecture classifiers;
- graph visualization;
- a full IDE extension;
- mandatory desktop overlay;
- tray process;
- completion sounds;
- autonomous patching;
- repair generation;
- repair verification;
- cloud accounts;
- team dashboards;
- background services.

Optional overlays, tray status, and notifications may improve polish later. The
CLI must remain complete without them.

## Productization Acceptance Criteria

### Private Alpha Ready

| Criterion | Target |
| --- | --- |
| Standard and fallback demo repositories pinned | yes |
| Clean facilitator install verified | yes |
| Demo reaches first useful answer | `< 10` minutes |
| Read-only safety statement shown | yes |
| Review leads never described as confirmed defects | `100%` |
| Unsupported claims during demo | `0` |

### Daily Self-Serve Ready

| Criterion | Target |
| --- | --- |
| `jarvis-builder --help` works after documented install | yes |
| Module fallback remains supported | yes |
| Invalid project path produces concise recovery guidance, no traceback | yes |
| Long operations acknowledge start immediately | yes |
| Long operations expose progress and elapsed time | yes |
| `Ctrl+C` leaves prior valid state intact | yes |
| Index writes are atomic | yes |
| Missing, corrupt, incompatible, and stale state are distinct | yes |
| `.jarvis_builder/` Git ignore guidance is visible | yes |
| Results show analyzed, skipped, degraded, and unresolved coverage | yes |
| README and quickstart cover RU-3, graph, impact, and trust tiers | yes |
| JSON output exists for scan workflows | yes |
| SARIF and deterministic CI exit behavior documented | yes |
| VS Code and Git examples documented | yes |

### Confirmed-Defect Claim Ready

| Criterion | Target |
| --- | --- |
| Phase 95E rejected-corpus manual gate | complete |
| Phase 98A `300`-packet human review | `300 / 300` |
| Phase 100A historical slate assembled and replayed | complete |
| Human-adjudicated confirmed precision | `100%` |
| Confirmed false positives | `0` |
| Fixed-version directional clearance | `100%` |
| Proof-packet completeness | `100%` |
| Hidden unresolved edges | `0` |
| Unsupported claims | `0` |

## Final Assessment

The current Builder Core is an increasingly serious repository-intelligence
engine wearing prototype clothes.

The shortest route to external daily use is:

```text
honest trust surface
  -> installable CLI
  -> guided first run
  -> progress, cancellation, and state recovery
  -> freshness and coverage visibility
  -> JSON/SARIF + editor and CI examples
  -> concierge external sessions
  -> measured daily-use signal
```

This is good news. The largest remaining gaps are product-shaped. JARVIS does
not need another intelligence expansion to become useful to external
developers. It needs a calm, trustworthy shell around the intelligence already
built.
