# Phase 194 — Foundation (Parts 9, 1, 10)

Sequencing chosen by the user: **foundation first** — design system → navigation
redesign → home polish → checkpoint before the heavier parts (admin workspace,
result/export cards, noise reduction, final review).

This report covers the foundation increment. Parts 2–8 and 11 follow in later
increments and will extend this report set.

## Part 9 — Design system ✅
Added a tokenized design language in `styles.css` (`:root` + `.ds-*` primitives):
3 heading sizes, 2 body sizes, one 4px spacing scale, one card radius, one
button sizing system, and a limited palette (one primary, one accent, semantic
states). Tokens were set to the existing values so nothing visually regressed;
`.glass` now uses `var(--radius)`. Full reference:
`reports/phase194_design_system.md`.

## Part 1 — Top navigation redesign ✅
Rebuilt the topbar into three clear groups on a single row:
- **LEFT** — Atlas logo (dropped the redundant tagline).
- **CENTER** — Home · Scan · **Map** · Change Plan · Debug · **Impact**
  (renamed from "Codebase Map"/"What breaks?"). Verified single-row at desktop
  width (`distinctRows: 1`); the nav wraps only on very narrow viewports.
- **RIGHT** — repository selector (clickable repo chip → Scan), detail-mode
  toggle (Simple / Full detail), and a **single** user menu.

Consolidated everything scattered across the bar into the one user menu:
Account · Devices · Admin Workspace (admin/superadmin only) · Quickstart ·
Documentation · Support · Help & about · Copy diagnostics · Report an issue ·
Sign out. Removed the standalone Quickstart link and the separate "Help & more"
menu. The loose account chip is hidden whenever the user menu is shown → no
duplicate account entry points. "Admin Console" renamed to **Admin Workspace**.

## Part 10 — Home experience polish ✅
The home (rebuilt in 193B) now leads with the dashboard for signed-in users: the
big marketing hero title/headline is hidden once authenticated (the topbar
already brands Atlas), removing duplication and dead space. Home shows: Welcome +
tagline, single status indicator, Repository status line, Quick Actions (4 large
cards), Getting Started (auto-hides once there's analysis history), and Recent
Activity (analyses / repositories / exports with empty states). Scan picker and
sample packs remain available below.

## Removed UI clutter (foundation)
- Separate "Help & more" top-bar menu (merged into the user menu).
- Standalone Quickstart top-bar link (moved into the user menu).
- Loose "Sign in"/account chip as a visible signed-in entry point (hidden;
  user menu is the single entry point).
- Redundant brand tagline in the topbar.
- Duplicate plan badge on Home (Phase 193B) — one combined status pill.
- Redundant giant "ATLAS / Describe a change…" hero for signed-in users.

## Verification
- Live (preview, real `index.html`): topbar groups LEFT/CENTER/RIGHT; nav center
  = the six workflows; single row at desktop width; user menu consolidated;
  loose account chip hidden; "Admin Workspace" label; home renders as a premium
  dashboard (welcome, Active · Enterprise pill, four quick-action cards, getting
  started, three recent-activity columns). Screenshots captured.
- Tests: 106 passing across the UI/nav suites (155, 184, 176, 188, 193,
  193b, 193-admin, 122-nav-aliases, …). Updated `test_phase155` (Help-menu
  consolidation) and `test_phase193b` (Admin Workspace label).
- Pre-existing (NOT introduced here): `test_phase122::test_simplified_nav_labels`
  and `::test_product_version_atlas_hardening_lineage`,
  `test_phase175b::test_feedback_local_mode_message` and
  `::test_export_cta_primary_after_change_plan` were already failing at HEAD
  (verified: the asserted strings `Investigate Bug` / `Advanced` are absent at
  the committed baseline, and the version/feedback checks are pure-Python,
  untouched by this work). Left for their owning area.

## Still to do (Phase 194)
Part 2 (noise −30/40%), Part 3 (unified result card), Part 4 (export dropdown),
Part 5 (recent-results cards), Part 6 (Admin Workspace sections), Part 7 (full
users table), Part 8 (admin password tools), Part 11 (full UX audit).

## Ship-blocker fix (follow-up)
A full-suite run surfaced `test_phase179::test_shipped_static_has_no_phase_labels`
failing — shipped static assets must not contain internal `Phase N` labels. My
193/193b/194 code comments (and pre-existing labels in `app.js`/`atlas_beta.js`)
violated it. Scrubbed all `Phase N` tokens from comments in `atlas_accounts.js`,
`index.html`, `styles.css`, `app.js`, `atlas_beta.js` (comment-only, no behavior
change). Now 159 UI/ship-blocker tests pass; the only remaining static-label
failure is `atlas_admin.js`, untracked Admin-Console WIP cleaned when the Admin
Workspace (Parts 6–8) lands.

Note on the full suite: other failures observed in a 38-min full run are
pre-existing engine/integration failures from the repo's dirty working tree
(uncommitted `evidence_engine`/`impact_engine`/`planning_engine`/… changes), not
introduced by this UX work and outside Part 194's "do not change analysis
engines" scope.

## Commits
- `9bbe61d1b` — foundation (Parts 9/1/10)
- `491293aa9` — ship-blocker: scrub internal phase labels from shipped static
