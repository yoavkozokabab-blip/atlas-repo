# Phase 193B — Home Experience & Navigation Simplification

Builds on Phase 193 (`26afd13fe`). Strictly UX: home experience, navigation
structure, onboarding, information architecture, and perceived product quality.
No auth/accounts-service/billing/installer/backend changes.

## What changed

### Part 1 — A real Home (onboarding dashboard)
`#homeDashboard` was rebuilt from a status-centric header into a four-section
onboarding dashboard (`jarvis_desktop/static/index.html` + `styles.css`):

1. **Welcome** — "Welcome back, {name}." + "Atlas helps you understand large
   repositories before your AI starts changing code." + current repository line.
2. **Quick Actions** — four large visual cards: **Scan Repository**,
   **Debug Issue**, **Change Plan**, **What Breaks?**, each with a description.
3. **Getting Started** — numbered steps (Scan a repository → Open Codebase Map →
   Generate a Change Plan → Export to Claude/Cursor/Codex). **Auto-hides** once
   the account has usage history (`gs.style.display = items.length ? 'none' : ''`).
4. **Recent Activity** — three columns (Recent analyses, Recent repositories,
   Recent exports), each with empty-state copy when nothing exists.

### Part 2 — Account removed from main navigation
Primary nav contains only the core workflows: Home, Scan, Codebase Map, Change
Plan, Debug, What Breaks? (Repository Context stays advanced-only/hidden by
default.) There is no `Account` item / `data-view="accounts"` in the nav.

### Part 3 — User-menu restructure
The topbar user menu now contains: **Account · Devices · Admin Console
(admin/superadmin only) · Support · Sign out**. `Devices` opens the account view
and scrolls to the device list (`atlasAccounts.openDevices()`). Admin Console
stays role-gated (`admin-only`, shown only when `isAdmin()`).

### Part 4 — Pending dashboard = success state
Title "Application received"; body "Your Atlas beta application has been
submitted successfully. Our team is reviewing your application."; "Typical
review time: 24–72 hours."; "You can close Atlas and return later…". Rendered
with a **success** tone (`.status-dash.success`, green accent + ✓), not a
warning. Actions: Refresh status, Contact support, Sign out.

### Part 5 — Inactive dashboard = calm/neutral
Title "Account not active". Reassures explicitly: "Your account exists / You
signed in successfully / Atlas access is currently unavailable." **Neutral**
tone (`.status-dash.neutral`) — no error/danger/warning styling or language.
Actions: Refresh status, Contact support, Sign out.

### Part 6 — Rejected dashboard = closure
Title "Application not approved"; "Your application was reviewed but was not
approved at this time." Actions: Contact support, Sign out (no Refresh). The
**Reapply** button is a placeholder hidden behind a feature flag
(`REAPPLY_ENABLED = false`).

### Parts 7–8 — Information architecture & cleanup
Every authenticated user always sees: am I signed in (user menu), my account
status (one pill on Home / the status dashboard), and what to do next (quick
actions / dashboards). The duplicate plan badge was removed — Home now shows a
**single** combined status indicator (e.g. `Active · Pro`); the loose account
chip stays hidden whenever the user menu is shown.

## Verification

The screenshot capture tool was unavailable during this session (renderer
capture timed out; `eval`/accessibility snapshots worked). Phase 193 captured
live screenshots of all six account states; Phase 193B's structure/copy/tone was
verified against the real `index.html` via accessibility snapshot + DOM eval:

- **Active home** (accessibility snapshot): nav = Home/Scan/Codebase Map/Change
  Plan/Debug/What breaks? (no Account); "Welcome back, yoav" + tagline; single
  pill "Active · Pro"; four quick-action cards with descriptions; three
  recent-activity columns; Getting Started hidden (usage history present).
- **Pending**: `status-dash glass success`, title "Application received",
  "submitted successfully", "24–72 hours", "close Atlas and return later",
  refresh shown, reapply hidden.
- **Inactive**: `status-dash glass neutral`, title "Account not active", steps
  [account exists / signed in successfully / access currently unavailable].
- **Rejected**: `status-dash glass neutral`, title "Application not approved",
  refresh hidden, reapply hidden (flag off).
- **User menus**: admin → [Account, Devices, Admin Console, Support, Sign out];
  normal user → [Account, Devices, Support, Sign out] (Admin Console gated out).

### Tests
- New: `jarvis_desktop/tests/test_phase193b_home_navigation.py` (welcome/tagline,
  quick-action cards + copy, getting-started auto-hide, recent-activity columns +
  empty states, nav has no Account, user-menu contents + gating, dashboard
  tones/copy, reapply behind flag, single status indicator).
- Updated `test_phase193_access_state_ux.py` home assertions for the new layout.
- Full `jarvis_desktop/tests` suite + UI-sensitive suites (188, 155, 157, 176,
  184, 193 admin) green.

## Commit

`0ae4dd209`
