# Builder UX Execution Plan

Date: 2026-05-31

## Scope

This plan selects exactly five recommendations from `reports/builder_ux_audit.md`:

- Three P0 items
- Two P1 items

Builder Core intelligence remains frozen. This plan does not change analysis behavior, detectors, semantic rules, reasoning systems, findings, rankings, or repository safety boundaries.

## Selection Method

Items are ranked by:

1. User impact
2. Engineering effort
3. Regression risk

The selected tranche improves the everyday CLI experience before adding optional surfaces such as overlays, notifications, editor plugins, JSON output, or SARIF output.

| Rank | Audit item | Priority | User impact | Engineering effort | Risk | Why selected now |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | F1: Friendly expected-error handling | P0 | Very high | Medium | Low | Raw tracebacks make normal mistakes feel like crashes |
| 2 | R2: TTY-aware progress with phase, count, and elapsed time | P0 | Very high | Medium | Medium | Long repository work currently appears silent |
| 3 | S1: Installable `jarvis-builder` entry point | P0 | High | Medium | Low | Module syntax adds friction to every first-run and daily invocation |
| 4 | R8: Compact completion timing summary | P1 | Medium | Low | Low | Makes performance predictable with little implementation surface |
| 5 | S8: Post-`init` next-command suggestions | P1 | Medium | Low | Low | Helps a new user move directly from indexing to useful work |

## Constraints

- Do not change Builder Core intelligence.
- Do not add or promote detectors.
- Do not add semantic profiles or reasoning rules.
- Do not alter finding schemas, ranking, or benchmark behavior.
- Do not execute target repository code.
- Do not modify target repository source files.
- Keep target-repository writes restricted to `.jarvis_builder/`.
- Keep `py -3 -m builder_core.cli` working as a supported fallback.
- Do not add overlays, tray processes, notifications, CI formats, or editor plugins in this tranche.

## 1. Friendly Expected-Error Handling

**Selected audit item:** F1  
**Priority:** P0  
**Rank:** 1

### Outcome

Expected user errors should produce a concise message, a practical recovery step, and a stable non-zero exit code. Routine mistakes should not print a Python traceback unless a debug option is explicitly requested.

The first covered cases should be:

- Project directory does not exist
- Project path is not a directory
- Requested source file is missing or unreadable
- Indexed command is used before `init`
- `.jarvis_builder/` cannot be created safely

### Exact Files Likely Affected

| File | Expected change |
| --- | --- |
| `builder_core/cli.py` | Add a narrow CLI error boundary, consistent stderr rendering, stable exit handling, and explicit debug-detail behavior |
| `builder_core/tests/test_builder_ux.py` | New focused tests for invalid paths, missing files, missing index state, safe-memory-directory failures, exit codes, and traceback suppression |
| `builder_core/README.md` | Document normal error behavior and the debug-detail escape hatch |

### Estimated Implementation Size

- Production code: 35-70 lines
- Tests: 50-90 lines
- Documentation: 5-15 lines
- Total: approximately 90-175 lines across 3 files

### Rollback Plan

Revert the CLI error-boundary change, remove the focused UX tests for that boundary, and remove the short README note. Existing command handlers already return integer status codes in several cases, so rollback should restore current behavior without touching analyzers or state files.

### Acceptance Criteria

- `jarvis-builder` module fallback invocation against a missing project path exits non-zero without a traceback.
- The error names the invalid path and gives a concise recovery action.
- `ask` before `init` continues to exit non-zero with an actionable `init` instruction.
- `analyze-file` for a missing file continues to exit non-zero with a concise message.
- A debug-detail option can expose technical detail when explicitly requested.
- Existing Builder Core analysis outputs and benchmarks are unchanged for valid inputs.

## 2. TTY-Aware Progress

**Selected audit item:** R2  
**Priority:** P0  
**Rank:** 2

### Outcome

Repository indexing and full-repository scans should acknowledge work immediately and show honest progress:

- Current phase
- Files processed
- Total files when known
- Elapsed time

Interactive terminals may refresh a compact status line. Redirected output and non-interactive environments must remain stable line-by-line text.

### Exact Files Likely Affected

| File | Expected change |
| --- | --- |
| `builder_core/cli.py` | Create and pass a CLI progress reporter for `init`, `bug-scan`, and `security-scan` |
| `builder_core/indexer.py` | Add optional progress callbacks around repository discovery and Python analysis loops |
| `builder_core/bug_intelligence/engine.py` | Add optional progress callbacks around Python file collection, reading, and analysis loops |
| `builder_core/progress.py` | New small terminal-only helper for TTY detection, elapsed time, and stable progress rendering |
| `builder_core/tests/test_builder_ux.py` | Verify visible phases, elapsed reporting, callback behavior, and stable redirected output |

### Estimated Implementation Size

- Production code: 110-190 lines
- Tests: 80-140 lines
- Total: approximately 190-330 lines across 5 files

### Rollback Plan

Remove `builder_core/progress.py`, remove optional callback parameters and emissions, and remove CLI reporter wiring. Because callbacks must default to `None`, rollback does not require changes to analyzer logic or result formatting.

### Acceptance Criteria

- `init` prints an immediate start acknowledgement before repository traversal.
- `bug-scan` and `security-scan` expose progress during full-repository work.
- Progress includes a phase label, processed count, and elapsed time.
- Redirected output uses stable lines and does not contain spinner rewrites or terminal control noise.
- Optional callbacks default to `None`; existing direct callers remain compatible.
- Progress reporting does not change findings, rankings, benchmark counts, or target-repository writes.

## 3. Installable Console Entry Point

**Selected audit item:** S1  
**Priority:** P0  
**Rank:** 3

### Outcome

Engineers should be able to run:

```text
jarvis-builder --help
```

The current invocation remains supported:

```text
py -3 -m builder_core.cli --help
```

### Exact Files Likely Affected

| File | Expected change |
| --- | --- |
| `pyproject.toml` | New minimal package metadata and `jarvis-builder = "builder_core.cli:main"` console script |
| `builder_core/cli.py` | Align help-program naming with the installed entry point while preserving module execution |
| `builder_core/README.md` | Document installation, the preferred entry point, and the module fallback |
| `builder_core/tests/test_builder_ux.py` | Verify the CLI entry target and preserve direct `main()` behavior |

### Estimated Implementation Size

- Packaging metadata: 20-45 lines
- Production code: 1-5 lines
- Tests: 20-40 lines
- Documentation: 15-30 lines
- Total: approximately 56-120 lines across 4 files

### Rollback Plan

Remove `pyproject.toml`, restore the previous help-program label if changed, and revert the installation documentation. The existing Python module invocation remains the operational fallback throughout implementation.

### Acceptance Criteria

- An editable local install exposes `jarvis-builder`.
- `jarvis-builder --help` exits successfully.
- `py -3 -m builder_core.cli --help` still exits successfully.
- Both entry paths expose the same current command set.
- Packaging does not pull Builder Core through `main.py`.
- No voice, browser, trading, website, router, detector, or reasoning modules are affected.

## 4. Compact Completion Timing Summary

**Selected audit item:** R8  
**Priority:** P1  
**Rank:** 4

### Outcome

At the end of indexing and full-repository scans, print a compact completion line with total elapsed time. When progress phases are available, include the slowest visible phase.

Example shape:

```text
Completed in 1.24s. Slowest phase: repository analysis (0.91s).
```

### Exact Files Likely Affected

| File | Expected change |
| --- | --- |
| `builder_core/cli.py` | Render completion summaries after `init`, `bug-scan`, and `security-scan` |
| `builder_core/progress.py` | Record total elapsed time and visible phase durations |
| `builder_core/tests/test_builder_ux.py` | Verify completion lines and deterministic formatting |

### Estimated Implementation Size

- Production code: 20-40 lines
- Tests: 20-45 lines
- Total: approximately 40-85 lines across 3 files

### Rollback Plan

Remove completion-summary rendering and phase-duration accumulation while retaining the P0 progress reporter. Findings and command status codes remain untouched.

### Acceptance Criteria

- `init`, `bug-scan`, and `security-scan` end with a concise elapsed-time summary.
- The summary appears after successful work and remains readable in redirected output.
- Timing output does not reorder findings or alter command exit status.
- Slowest-phase text is omitted cleanly if no phase timings are available.

## 5. Post-Init Next Commands

**Selected audit item:** S8  
**Priority:** P1  
**Rank:** 5

### Outcome

After a successful `init`, print a short, fixed next-step list that helps a new user immediately run useful existing commands.

The suggestions should remain concise and should not claim capabilities beyond the current CLI. A suitable set is:

```text
Next:
  jarvis-builder analyze-file --project <path> <file>
  jarvis-builder bug-scan --project <path> --top 10
  jarvis-builder security-scan --project <path>
```

### Exact Files Likely Affected

| File | Expected change |
| --- | --- |
| `builder_core/cli.py` | Print fixed next-command suggestions after successful indexing |
| `builder_core/README.md` | Mirror the suggested first-use flow |
| `builder_core/tests/test_builder_ux.py` | Verify that suggestions appear only after successful `init` |

### Estimated Implementation Size

- Production code: 8-18 lines
- Tests: 15-30 lines
- Documentation: 5-15 lines
- Total: approximately 28-63 lines across 3 files

### Rollback Plan

Remove the post-`init` suggestion block and matching README text. Index creation and analysis behavior remain unchanged.

### Acceptance Criteria

- A successful `init` ends with no more than three useful next commands.
- Suggestions reference only existing commands.
- Suggested paths are copyable and use the resolved project root.
- Failed `init` runs do not print next-step suggestions.
- Suggestions work with the installed entry point and remain understandable for module-fallback users.

## Expected Combined File Set

The selected five items should remain contained to:

```text
pyproject.toml
builder_core/cli.py
builder_core/indexer.py
builder_core/progress.py
builder_core/bug_intelligence/engine.py
builder_core/README.md
builder_core/tests/test_builder_ux.py
```

No analyzer, detector, semantic reasoning, benchmark, voice, browser, trading, website, or router file should change.

## Verification Plan

Run the focused UX tests first:

```powershell
py -3 -m pytest builder_core/tests/test_builder_ux.py -q
```

Then run the existing Builder Core regression suite:

```powershell
py -3 -m pytest builder_core/tests/ -q
```

Finally verify both launch paths:

```powershell
jarvis-builder --help
py -3 -m builder_core.cli --help
```

The implementation is acceptable only if:

- Existing benchmark results remain unchanged.
- Existing Builder Core tests remain green.
- The target repository write boundary remains `.jarvis_builder/` only.
- `git diff --name-only` contains only the expected UX file set.

## Explicitly Deferred

This tranche does not include:

- New AI behavior
- New detectors
- New reasoning systems
- JSON or SARIF export
- CI integration
- VS Code integration
- Background jobs
- Notifications or sounds
- Overlay or tray support
- Automatic `.gitignore` edits
- Automatic source edits
