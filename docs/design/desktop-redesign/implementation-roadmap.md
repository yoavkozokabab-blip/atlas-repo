# Implementation roadmap

## Phase 1 — reconnaissance

- Prove launcher, shell, frontend/backend, commands, paths, screens, contracts, and risks.
- Exercise live launch, local mode, scan, Home, Ask, Debug, Impact, Plan, Map, and required sizes.
- Create audit, IA, design, interaction, accessibility, QA, risk, and roadmap artifacts.

## Phase 2 — foundation

- Replace horizontal navigation with rail and single-row status bar.
- Introduce canonical tokens and primitives.
- Add command/search, focus management, skip link, reduced motion, responsive behavior.
- Keep compatibility IDs and endpoints.

## Phase 3 — core vertical slice

- Redesign splash/trust/auth/local mode, repository selection, Home, Scan, and Ask.
- Verify source mode at all sizes and focused auth/Home/scan/Ask tests.

## Phase 4 — repository intelligence

- Add Memory and Files/Symbols/Concepts from existing summary/graph/module data.
- Redesign Impact, Debug, Plan, and Graph around evidence paths and inspectors.
- Preserve graph performance and list fallback.

## Phase 5 — operations

- Create Agents, Diagnostics, and Settings from existing APIs and handlers.
- Preserve account, billing/admin, MCP confirmation, privacy, support export, cache, and rebuild behavior.

## Phase 6 — state polish

- Loading, empty, partial, stale, offline, permission, failure, low-confidence, update, destructive confirmation.
- Keyboard, screen reader, zoom, reduced motion, long paths, compact windows.

## Phase 7 — release proof

- Focused/full tests, JS syntax, screenshots, installed-app walkthrough, startup/shutdown, MCP artifacts, fresh-process persistence, package build, installer proof.
- Do not push, merge, deploy, or replace release assets without instruction.

## Blockers and constraints

- Installed Atlas launch via Computer Use required approval and timed out during reconnaissance; source mode is verified, installed proof remains a gate.
- No local Space Grotesk/Geist font assets exist; use offline-safe fallbacks unless licensed files are added.
- Some ideal Memory/Files fields are not first-class APIs; compose only existing summary, graph, module, history, trust, and diagnostics data.
