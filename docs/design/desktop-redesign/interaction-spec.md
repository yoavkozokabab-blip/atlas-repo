# Interaction specification

## Principles

- Keep repository, readiness, freshness, and agent context visible.
- Preserve entered briefs while moving between destinations.
- Prefer inline expansion and inspectors to modal dialogs.
- Confirm destructive/config-writing actions at action time.
- Show backend-reported phases and evidence only.

## Core interactions

- Scan: select/browse, validate, scope, start, cancel, retry, complete. Cancellation says the prior index is unchanged.
- Ask: `Ctrl+Enter` runs. Loading names repository work. Result order is verdict, evidence, files, confidence/unknowns, next action.
- Impact: typing and scanned-file selection. Direct, transitive, tests, and unresolved risk use text and line style as well as color.
- Debug: ranked hypotheses with evidence, falsifier, and verification when present.
- Plan: numbered sequence, likely edits, verification, compatibility and delivery risks.
- Graph: a keyboard list is always available; selection updates and announces an inspector. Canvas is never the only representation.
- Agents: configure, status, test, repair, and manual config remain per tool. Writes retain confirmation and backup behavior.
- Diagnostics: read-only checks are immediate; cache clear, rebuild, and support export are separated.

## Global states

Loading keeps stable geometry. Empty states explain why. Errors say what failed, what remained safe, and one recovery. Offline distinguishes account-service reachability from local repository functions. Low confidence and partial graph state remain adjacent to the result.
