# Builder UX Audit

Date: 2026-05-31

## Scope

Builder Core intelligence is treated as frozen for this audit. The recommendations below improve installation, workflow clarity, responsiveness, accessibility, failure handling, integration, and product polish only.

This audit does not propose:

- New AI capabilities
- New bug detectors
- New semantic rules
- New reasoning systems
- Automatic code changes
- Changes to the Builder Core roadmap

## Executive Summary

Builder Core already has a credible safety foundation: it is local, read-only, and intentionally separate from the main JARVIS runtime. Its current UX is still closer to an engineering CLI prototype than a polished daily tool.

The highest-value improvements are practical:

1. Give engineers a simple install and launch path.
2. Make every long operation visibly active, cancellable, and honest about skipped work.
3. Replace raw tracebacks and ambiguous state errors with concise recovery guidance.
4. Add stable machine-readable output and exit behavior for editor, Git, and CI workflows.
5. Make notifications, tray visibility, and overlays optional layers around a fully capable CLI.

None of these changes require changing the intelligence layer.

## Observed Baseline

| Area | Current behavior | UX implication |
| --- | --- | --- |
| Launch | Commands use `py -3 -m builder_core.cli ...` | Functional, but cumbersome for repeated daily use |
| Installation | No packaging metadata or dedicated console entry point was found | First-time setup is unclear |
| Indexing | `init` prints a summary after indexing completes | Users cannot tell whether a large repository is active, slow, or stuck |
| Scanning | Repository scans run without progress or cancellation feedback | Work feels slower than it is |
| State | Builder state lives in `.jarvis_builder/index.json` | Good local boundary, but state lifecycle is not visible |
| Corrupted state | Missing and unreadable index state are presented as the same condition | Recovery guidance can be misleading |
| Invalid project path | A raw Python traceback is shown | Normal user errors feel like crashes |
| Git hygiene | `.jarvis_builder/` is not ignored automatically or clearly surfaced as an ignore recommendation | Engineers may accidentally stage generated state |
| Output | Human-readable terminal sections only | Weak fit for editor and CI integration |
| Accessibility | No explicit plain-progress, no-color, or screen-reader-oriented mode | Dynamic terminal UX could become exclusionary if added carelessly |

### Local Timing Observation

The following are single local observations on the available QuixBugs checkout, not a formal performance benchmark:

| Command | Observed duration |
| --- | ---: |
| CLI help | 123 ms |
| Single-file analysis | 123 ms |
| Full `bug-scan` | 1.23 s |
| Full `security-scan` | 0.98 s |

The basic CLI is already responsive. The product opportunity is to make longer work legible and comfortable as repository size grows.

## Priority Definitions

| Priority | Meaning |
| --- | --- |
| P0 | Required for a trustworthy first-use and daily-use baseline |
| P1 | High-value polish that materially improves repeated engineering workflows |
| P2 | Optional refinement that improves comfort, perceived quality, or advanced workflows |

Implementation complexity uses `Low`, `Medium`, or `High` relative to the current CLI.

## Highest-Priority Improvements

| Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- |
| Add an installable `jarvis-builder` console entry point while keeping module invocation supported | Removes repetitive launch friction | Medium | A clear, memorable daily command | P0 |
| Add a centralized user-facing error boundary with stable exit codes and optional debug detail | Replaces routine tracebacks with actionable messages | Medium | Faster recovery and greater trust | P0 |
| Show indexing and scan phases, counters, elapsed time, and skipped-file summaries | Makes long work visibly active and honest | Medium | Less uncertainty on real repositories | P0 |
| Make `Ctrl+C` cancellation explicit and state-safe | Prevents users from feeling trapped in a long scan | Medium | Confident interruption without corrupted state | P0 |
| Persist index state atomically and distinguish missing, corrupt, and incompatible state | Prevents ambiguous recovery paths | Medium | Predictable self-repair after interrupted writes | P0 |
| Add JSON and SARIF output plus deterministic CI exit behavior | Unlocks editor and CI usage without changing analysis | Medium | Findings become usable inside existing engineering loops | P0 |
| Expand README and command help to cover the current CLI surface | Fixes discoverability gaps | Low | Engineers can learn the product without reading source | P0 |
| Warn that `.jarvis_builder/` should be ignored by Git and provide the exact ignore entry | Reduces accidental generated-state commits | Low | Cleaner repositories with no silent file edits | P0 |

## 1. Startup Experience

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| S1 | Provide an installable `jarvis-builder` entry point and keep `py -3 -m builder_core.cli` as a documented fallback | Simplifies every invocation | Medium | First launch feels like a product, not an internal module | P0 |
| S2 | Add a short first-run preflight that validates the project path, Python version, state-directory writability, and optional Git availability before indexing begins | Moves failures to the start of the workflow | Medium | Immediate, specific setup guidance | P0 |
| S3 | Print an immediate indexing start line with the resolved project path and current phase | Eliminates the silent startup gap | Low | Users know the correct repository is being processed | P0 |
| S4 | Show indexing phases such as discovery, README/docs, Python files, tests, and Git metadata with file counters | Makes initialization understandable | Medium | Users can distinguish progress from a hang | P0 |
| S5 | After project load, show a compact summary: project root, indexed timestamp, branch or commit when available, indexed file count, and freshness | Exposes state clearly | Medium | Engineers can trust the analysis context | P1 |
| S6 | Catch expected startup errors and print a concise message, recovery action, and stable exit code; reserve stack traces for an explicit debug option | Turns routine mistakes into guided recovery | Medium | Less frustration and less terminal noise | P0 |
| S7 | Warn when `.jarvis_builder/` is not ignored by Git and print the exact `.gitignore` line without modifying the repository | Protects repository hygiene | Low | Safe setup with no surprising edits | P0 |
| S8 | Add a short success message after `init` with the two or three most relevant next commands | Reduces the gap between setup and value | Low | A smooth first-use path | P1 |

## 2. Responsiveness

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| R1 | Emit an acknowledgement within the first moment of every operation: project accepted, command accepted, phase started | Improves perceived responsiveness immediately | Low | No uncertainty after pressing Enter | P0 |
| R2 | Show TTY-aware progress with phase, processed count, total when known, and elapsed time | Makes longer analysis legible | Medium | Engineers can decide whether to wait or cancel | P0 |
| R3 | Support clean `Ctrl+C` cancellation with a clear interrupted message and no partially published index | Establishes control during slow work | Medium | Safe interruption when priorities change | P0 |
| R4 | Report skipped, unreadable, and truncated files at the end of indexing and scans | Makes analysis coverage honest | Medium | Users can judge result completeness | P0 |
| R5 | Show whether an index is fresh, stale, or reused, with the reason | Clarifies when work is being avoided safely | Medium | Cached work feels trustworthy rather than mysterious | P1 |
| R6 | Avoid unnecessary re-indexing when the stored project snapshot is still fresh | Reduces repeated wait time without changing analysis semantics | High | Faster daily use on stable repositories | P1 |
| R7 | Offer an explicit background mode for long indexing and scans with job status, cancel, and attach-to-output commands | Keeps terminals available during large operations | High | Better fit for large repositories | P2 |
| R8 | Print a compact completion line with total elapsed time and the slowest visible phase | Helps users build accurate expectations | Low | Performance feels measurable and predictable | P1 |

## 3. Accessibility

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| A1 | Keep the complete workflow keyboard-first and add shell completion for commands, flags, and common values | Speeds expert use and supports users who avoid pointer workflows | Medium | Efficient terminal navigation | P1 |
| A2 | Never encode severity or state using color alone; pair color with text labels and stable symbols | Prevents color-dependent interpretation | Low | Color-blind-safe results | P0 |
| A3 | Provide `--no-color` and respect common terminal conventions for disabling color | Improves compatibility with assistive tools and logs | Low | Clean readable output everywhere | P0 |
| A4 | Make progress output screen-reader friendly: use stable line-by-line progress in plain mode and avoid spinner rewrites when output is non-interactive | Prevents dynamic terminal noise | Medium | Usable output with screen readers and redirected logs | P0 |
| A5 | Keep paths and line references copyable in `path:line` form | Improves keyboard and assistive workflows | Low | Fast jump-to-source from terminal output | P1 |
| A6 | Support concise and detailed verbosity levels without hiding failure information | Lets users control terminal density | Medium | Better readability across quick checks and investigations | P1 |
| A7 | If an overlay is added, follow operating-system text scaling and offer a high-contrast setting | Prevents an optional visual layer from becoming inaccessible | Medium | Comfortable visibility across display settings | P1 |

## 4. Notifications

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| N1 | Add an explicit opt-in desktop notification for operations that exceed a configurable duration | Helps users safely switch context | Medium | No need to watch a terminal during long work | P1 |
| N2 | Add an optional completion sound or terminal bell for long-running work | Provides a lightweight alert path | Low | Useful feedback without a desktop integration requirement | P2 |
| N3 | Provide a silent mode that disables sounds and desktop alerts while preserving terminal results | Prevents notification fatigue | Low | Comfortable use in meetings, shared spaces, and CI | P1 |
| N4 | Distinguish success, interruption, and failure in alerts using both text and iconography | Prevents ambiguous notifications | Medium | Engineers know whether action is needed | P1 |
| N5 | Keep notification content privacy-safe by default: show command type and duration, not source snippets or findings | Reduces accidental information exposure | Low | Safe use on sensitive repositories | P0 |
| N6 | Avoid noisy alerts for short commands and foreground terminal sessions unless the user opts in | Preserves signal quality | Medium | Notifications remain useful over time | P1 |

## 5. Overlay And Visibility

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| O1 | Keep overlays optional and read-only; the CLI must remain fully usable without them | Preserves a reliable terminal-first product | Low | No hidden dependency on desktop UI | P0 |
| O2 | Offer a minimal status strip for long work with state, elapsed time, progress, and a visible cancel affordance | Adds ambient visibility without clutter | High | Users can glance at progress while coding | P2 |
| O3 | If tray support is added, show state through text and icon: idle, indexing, scanning, completed, interrupted, or failed | Makes background status easy to inspect | High | Clear desktop presence during longer work | P2 |
| O4 | Give the tray menu a small set of workflow actions: open terminal here, show active job, cancel active job, and open the latest report | Keeps desktop controls practical | High | Faster return to active work | P2 |
| O5 | Add a privacy mode for overlays and notifications that hides project names and finding details | Protects sensitive repository context | Medium | Safer use during screen sharing | P1 |
| O6 | Provide quick-open mechanisms from terminal output: copyable source references and an optional editor-open action | Shortens the path from finding to inspection | Medium | Less navigation friction | P1 |

## 6. Developer Workflow

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| D1 | Support a stable `jarvis-builder` command and optional current-directory project discovery while preserving explicit `--project` | Reduces repeated path typing | Medium | Faster terminal workflow | P0 |
| D2 | Add machine-readable JSON output for analysis, scan, and risk-report commands | Enables scripting without parsing terminal prose | Medium | Reliable automation and editor integration | P0 |
| D3 | Add SARIF output for scans and deterministic non-interactive exit codes | Fits standard CI and code-scanning workflows | Medium | Findings can appear in existing review surfaces | P0 |
| D4 | Keep non-interactive output stable: no spinner rewrites, no sounds, no desktop notifications, and no prompts | Prevents CI instability | Medium | Predictable pipeline behavior | P0 |
| D5 | Publish a VS Code task and problem-matcher example before considering a larger editor integration | Gives immediate editor value at low cost | Low | Clickable findings inside a familiar workflow | P1 |
| D6 | Show indexed Git branch and commit when available, and identify stale analysis after a checkout change | Prevents context confusion across branches | Medium | Engineers know which revision was analyzed | P1 |
| D7 | Document PowerShell, Command Prompt, and Bash examples for common workflows | Removes shell-specific setup friction | Low | Faster adoption across teams | P1 |
| D8 | State the read-only contract clearly in help and docs: source files are never modified and generated state stays under `.jarvis_builder/` | Reinforces the trust boundary | Low | Confident use on production repositories | P0 |

## 7. Discoverability

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| Q1 | Update the README command matrix to cover the full current CLI surface, including analysis and scan commands | Closes a visible documentation gap | Low | Users discover existing value without source inspection | P0 |
| Q2 | Add one practical example to each command's `--help` output | Makes usage self-contained | Low | Less trial and error | P0 |
| Q3 | After `init`, print a short next-step list tailored to the indexed project | Improves first-session momentum | Low | Users reach useful results quickly | P1 |
| Q4 | Make errors contextual: suggest the exact recovery command for missing index, stale index, invalid path, and corrupted state | Turns failure into guidance | Medium | Less time spent diagnosing setup issues | P0 |
| Q5 | Add typo suggestions for close command names and flags | Softens small mistakes | Medium | Faster correction during terminal use | P1 |
| Q6 | Provide a one-page quickstart focused on a realistic engineer loop: initialize, analyze a file, scan, export, and use results in CI | Establishes a clear mental model | Low | Easier onboarding for teams | P1 |
| Q7 | Keep command descriptions outcome-oriented and consistent across help, README, and examples | Reduces cognitive load | Low | The tool feels coherent | P1 |

## 8. Performance Perception

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| P1 | Print command acceptance and resolved project path immediately | Makes startup feel instant | Low | Immediate confidence after invocation | P0 |
| P2 | Prefer honest phase counters over speculative ETAs; show ETA only when enough data exists | Avoids misleading progress | Medium | Users trust the interface | P1 |
| P3 | Emit a quiet heartbeat every one or two seconds during slow work | Prevents the appearance of a hang | Medium | Comfortable waiting on large repositories | P0 |
| P4 | Label reused analysis as cached and explain why it is valid | Makes avoided work visible | Medium | Fast paths feel deliberate | P1 |
| P5 | Keep ranked findings stable until the scan completes while updating only progress during the run | Avoids distracting output churn | Low | Results are easier to read and compare | P1 |
| P6 | Print a concise final summary before detailed findings: duration, files analyzed, files skipped, and finding count | Establishes a fast mental snapshot | Low | Engineers can decide whether to inspect further | P0 |
| P7 | Use TTY detection so interactive progress is polished while redirected output remains line-stable | Improves both terminal feel and automation reliability | Medium | No tradeoff between polish and scriptability | P0 |

## 9. Failure UX

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| F1 | Replace raw tracebacks for expected user errors with a concise error, cause, recovery step, and stable exit code | Makes failures feel handled | Medium | Faster recovery and more trust | P0 |
| F2 | Distinguish missing index, unreadable index, corrupted JSON, and incompatible index version | Prevents incorrect recovery guidance | Medium | Users understand what happened | P0 |
| F3 | Publish index updates atomically using a temporary file and replacement step | Reduces state corruption after interruption | Medium | Reliable startup after cancelled or failed work | P0 |
| F4 | On corruption, explain a safe repair path such as rebuilding the local `.jarvis_builder/` state | Makes repair routine | Low | No manual diagnosis required | P0 |
| F5 | Report unsupported or low-signal repositories honestly: for example, no supported source files found, while noting any docs that were indexed | Avoids false expectations | Medium | Clear result boundaries | P1 |
| F6 | Summarize unreadable, oversized, or skipped files and offer a detail view | Makes coverage gaps inspectable | Medium | Better confidence in scan completeness | P0 |
| F7 | On `Ctrl+C`, print that the operation was interrupted and whether the prior valid index remains available | Confirms state safety | Medium | Users can cancel without anxiety | P0 |
| F8 | Offer an explicit debug diagnostic mode that prints technical detail and a privacy-safe metadata summary | Preserves troubleshootability without noisy defaults | Medium | Better support experience | P1 |

## 10. Product Polish

| ID | Recommendation | Impact | Implementation complexity | User value | Priority |
| --- | --- | --- | --- | --- | --- |
| L1 | Use a consistent output envelope across analysis commands: summary, findings, evidence, sources, and next action where relevant | Makes commands easier to scan | Medium | Familiar structure across workflows | P1 |
| L2 | Standardize terminology across `risk-report`, `bug-scan`, `analyze-file`, and security output; document differences where names must remain distinct | Reduces ambiguity | Low | Users know which command to reach for | P1 |
| L3 | Include project path, Git context when available, duration, analyzed count, skipped count, and finding count in completion summaries | Makes output self-contained | Low | Easier sharing and later review | P1 |
| L4 | Keep terminal formatting robust at narrow widths and use plain-text fallbacks for redirected output | Prevents broken layouts | Medium | Polished behavior in real terminals | P1 |
| L5 | Give findings stable local identifiers within a result set and preserve copyable `path:line` evidence | Improves discussion and navigation | Medium | Easier collaboration during code review | P1 |
| L6 | Use concise empty states such as `No findings in 42 analyzed files` rather than blank sections | Makes successful scans feel complete | Low | Clear closure | P0 |
| L7 | Show the read-only boundary at moments that matter: first run, help, and any state repair message | Reinforces trust without overexplaining | Low | Confident use on valuable codebases | P1 |
| L8 | Keep visual motion restrained: subtle progress, no unnecessary animations, and no decorative desktop clutter | Preserves a professional engineering feel | Low | Premium polish without distraction | P2 |

## Recommended UX Baseline

Builder Core should feel ready for daily engineering use when the following are true:

- A new user can install and run `jarvis-builder --help` without knowing Python module syntax.
- `init`, repository scans, and long operations acknowledge startup immediately and expose progress.
- Every long-running operation can be cancelled safely with `Ctrl+C`.
- Missing, corrupt, incompatible, and stale state produce distinct, actionable messages.
- `.jarvis_builder/` is clearly identified as generated local state and recommended for Git ignore.
- Human terminal output remains concise and readable.
- JSON and SARIF output support editor and CI workflows.
- Redirected output is stable and non-interactive.
- Colors are optional and never the only state indicator.
- Notifications, tray presence, and overlays are opt-in conveniences, not dependencies.
- The read-only source boundary remains visible and credible.

## Guardrails

The following should remain out of scope for Builder UX polish:

- Adding or promoting detectors
- Adding semantic profiles or reasoning rules
- Introducing LLM interpretation
- Automatic source edits or fixes
- Silent background scans without explicit user action
- Mandatory overlays or tray processes
- Silent `.gitignore` edits
- Any change that weakens the local read-only project boundary

## Closing Assessment

Builder Core does not need more intelligence to feel substantially better. It needs a calmer product shell around the intelligence it already has: clear installation, immediate feedback, safe cancellation, honest state handling, accessible output, and integrations that respect how engineers already work.
