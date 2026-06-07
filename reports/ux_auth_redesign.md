# Atlas Authentication UX Redesign

**Date:** 2026-06-05  
**Scope:** UI/UX only — no authentication logic, security, or accounts backend changes.

---

## Screenshots

| Before | After |
|--------|-------|
| Tiny login form top-left; full app nav + repo grid visible | Centered auth card; app shell hidden until sign-in |
| `reports/ux_auth_redesign/before.png` | `reports/ux_auth_redesign/after.png` |

---

## Files changed

| File | Change |
|------|--------|
| `jarvis_desktop/static/index.html` | Dedicated `#auth-layout`; wrapped app in `#app-shell`; moved login/register/state panels out of main views |
| `jarvis_desktop/static/styles.css` | Auth layout CSS: centered card, inputs, errors, responsive rules |
| `jarvis_desktop/static/atlas_accounts.js` | Auth/app mode toggle, account-state messaging, login error mapping |
| `jarvis_desktop/static/app.js` | Deferred `bootAtlasApp()` until authenticated; `go()` blocked in auth mode |
| `jarvis_desktop/static/atlas_beta.js` | Skip welcome overlay pre-auth; show after first authenticated session |

---

## UX rationale (major changes)

### 1. Dedicated auth layout (`#auth-layout`)

**Problem:** Login lived inside the same SPA shell as Home, Scan, and repository pickers — users saw product UI before authentication.

**Change:** Full-screen auth experience with only Atlas branding, Help link, login/register card, and support footer.

**Why:** Matches SaaS convention (Linear, Vercel, Notion): authentication is a focused gate, not a corner panel on a dashboard.

### 2. App shell hidden until authenticated (`#app-shell` + `body.auth-mode`)

**Problem:** Repository grids, demo packs, recent repos, and nav rendered on every load.

**Change:** `#app-shell` (topbar, banners, all workflow views) is `display:none` while `body.auth-mode` is active.

**Why:** Eliminates pre-login exposure of codebase content and reduces visual noise.

### 3. Centered login card (460px, 36px padding)

**Problem:** Form was small, top-aligned, and lost in empty grid space.

**Change:** Vertically and horizontally centered card with clear hierarchy: ATLAS → subtitle → Sign in → fields → primary/secondary actions.

**Why:** Improves scan path for first-time users; primary action is obvious.

### 4. Visual design: quieter background

**Problem:** Large grid dominated the viewport.

**Change:** In auth mode, grid opacity reduced, glow centered behind card, darker gradient.

**Why:** Keeps Atlas dark identity without the “empty debug page” feel.

### 5. Input and button hierarchy

**Problem:** Generic inputs; Create account competed visually with Sign in.

**Change:** Full-width inputs with icons; `Sign In` as primary gradient button; `Create Account` as ghost secondary.

**Why:** Clear primary vs secondary action pattern.

### 6. Deferred app boot (`bootAtlasApp`)

**Problem:** `renderDemoPackPicker()` and `loadRecent()` ran before auth, populating repo UI in DOM (even if hidden later).

**Change:** Repo loading deferred until `atlas:authenticated` event.

**Why:** Faster initial paint for auth screen; no repository data fetched pre-login.

### 7. Human-readable account states (`acc-panel-state`)

**Problem:** Generic “Login failed” / blocked messages.

**Change:** Dedicated copy for suspended, banned, pending beta, offline grace expired, session expired, device limit, rate limit, and service unavailable — each with title, explanation, and recommended next step.

**Why:** Users know what happened and what to do without contacting support blindly.

### 8. Minimal pre-login navigation

**Problem:** Home, Scan, Codebase Map, Change Plan, Debug, What breaks? visible before sign-in.

**Change:** Only auth topbar (logo + Help). Full nav returns after authentication.

**Why:** Prevents confusion about available features and reinforces sign-in as the entry point.

### 9. Welcome overlay after auth

**Problem:** Welcome screen could appear over login or compete with auth-first flow.

**Change:** Welcome shows only after `atlas:authenticated` (first session).

**Why:** Onboarding starts after the user is in the product, not during sign-in.

---

## Account states covered (UI copy)

| State | User sees |
|-------|-----------|
| Invalid password | “Incorrect sign-in” + credential guidance |
| Suspended | Suspension notice + support contact |
| Banned | Ban notice + appeal guidance |
| Beta pending | Pending approval + support for status |
| Offline grace expired | Reconnect + sign in again |
| Session / cache invalid | Re-sign-in prompt |
| Device limit | Remove device or contact support |
| Rate limited | Wait 15 minutes |
| Service offline | Restart Atlas guidance |

---

## Responsive behavior

- Card scales to full width on viewports ≤520px with reduced padding
- Auth stage uses flex centering for vertical alignment on short and tall screens
- Touch-friendly input height (~44px) and full-width buttons

---

## Out of scope (unchanged)

- `/api/accounts/*` routes and accounts service
- Token storage, license gating logic, offline grace rules
- Phase 186/187 security behavior

---

## Verification

- Phase 186 account + privacy tests: **39 passed**
- Manual: load `index.html` unsigned → auth card only, no repo grid
- Manual: sign in → app shell appears, home loads, nav functional
