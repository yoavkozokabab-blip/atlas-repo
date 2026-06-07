# Phase 185 — Atlas Admin Console v1: Design

**Date:** 2026-06-07  
**Type:** Design only. Nothing in this document is implemented.

---

## 1. Overview

The Admin Console is a separate, protected web application that gives Atlas operators full visibility and control over users, licenses, devices, beta access, and platform health. It is never bundled with the desktop app and is never accessible from the user-facing website.

**Access:** `admin.useatlas.dev` (separate subdomain, never linked from user pages)  
**Authentication:** Admin-role JWT, with optional IP allowlist  
**Audience:** Atlas team members only

---

## 2. Information Architecture

```
Admin Console
│
├── Dashboard          ← landing page, live metrics
├── Users
│   ├── Search / list
│   ├── User detail
│   └── Bulk actions
├── Beta Management
│   ├── Waitlist
│   ├── Invite management
│   └── Beta cohort view
├── Licenses
│   ├── Active licenses
│   └── Expired / at-risk
├── Devices
│   └── Device revocation
├── Analytics
│   ├── Usage trends
│   ├── Token savings
│   └── Crash / error feed
└── Audit Log
    └── Admin action history
```

---

## 3. Dashboard

The landing page of the admin console. Shows the current health of the platform at a glance.

### 3.1 Metric cards (top row)

| Metric | Calculation |
|---|---|
| Total users | `COUNT(users WHERE status != 'banned')` |
| Active users (24h) | `COUNT(users WHERE last_seen > now() - 24h)` |
| Active users (7d) | `COUNT(users WHERE last_seen > now() - 7d)` |
| Beta users | `COUNT(users WHERE beta_flag = true)` |
| Pending waitlist | `COUNT(beta_waitlist WHERE status = 'pending')` |
| Active devices | `COUNT(devices WHERE revoked_at IS NULL)` |

### 3.2 Platform activity (time series, last 30 days)

| Chart | Data source |
|---|---|
| Daily active users | `COUNT(DISTINCT user_id) FROM usage_daily GROUP BY date` |
| Scans / day | `SUM(scans) FROM usage_daily GROUP BY date` |
| Exports / day | `SUM(exports) FROM usage_daily GROUP BY date` |
| Change Plans / day | `SUM(change_plans) FROM usage_daily GROUP BY date` |
| Token savings / day | `SUM(saved_tokens) FROM usage_daily GROUP BY date` |

### 3.3 Health indicators

| Indicator | Source | Threshold |
|---|---|---|
| Crash rate (24h) | `crash_events` count | Alert if > 5% of sessions |
| Failed logins (1h) | `auth_failures` rate-limit counters | Alert if > 50/hour |
| Email delivery rate | Provider webhook | Alert if < 95% |
| Feedback volume (24h) | Feedback submissions | Informational |

---

## 4. User Management

### 4.1 User list / search

**Search fields:** email, user_id (partial), status, plan, beta_flag, date range  
**Default sort:** last_seen descending  
**Columns:**

| Column | Sortable | Filterable |
|---|---|---|
| Email | ✓ | ✓ (contains) |
| Status | ✓ | ✓ (multi-select) |
| Plan | ✓ | ✓ (multi-select) |
| Beta | — | ✓ (toggle) |
| Created | ✓ | ✓ (range) |
| Last seen | ✓ | ✓ (range) |
| Devices | — | — |

**Bulk actions (checkbox selection):**
- Suspend selected
- Grant beta access to selected
- Export CSV

### 4.2 User detail view

```
┌─────────────────────────────────────────────────────────┐
│  user@example.com                         [active / beta]│
│  user_id: 550e8400-e29b-41d4-a716-446655440000           │
│  Created: 2026-06-01 · Last seen: 2026-06-07 (today)    │
├────────────────────┬────────────────────────────────────┤
│  ACTIONS           │  LICENSE                            │
│  [Suspend]         │  Plan: beta                         │
│  [Ban]             │  Expires: 2026-12-31                │
│  [Force logout]    │  Devices: 2/3                       │
│  [Grant beta]      │  [Change plan ▼]                    │
│  [Revoke beta]     │                                     │
├────────────────────┴────────────────────────────────────┤
│  DEVICES                                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Windows · 0.1.0-beta · first: Jun 1 · last: Jun 7│   │
│  │ device_id: abc123…                  [Revoke]      │   │
│  │                                                   │   │
│  │ Windows · 0.1.0-beta · first: Jun 3 · last: Jun 6│   │
│  │ device_id: def456…                  [Revoke]      │   │
│  └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│  USAGE (last 30 days)                                     │
│  Launches: 42 · Scans: 18 · Change Plans: 31             │
│  Debug: 14 · What Breaks: 22 · Exports: 29               │
│  Tokens saved: 7.1M (98%)                                 │
├──────────────────────────────────────────────────────────┤
│  ADMIN NOTES                                              │
│  [text area — admin-only visible]                         │
│  [Save note]                                              │
└──────────────────────────────────────────────────────────┘
```

### 4.3 Admin actions on users

| Action | Confirmation required | Effect | Reversible |
|---|---|---|---|
| Suspend | Yes — reason field | `status = suspended`, all sessions invalidated | Yes — Activate |
| Ban | Yes — reason field | `status = banned`, all sessions invalidated, email blocked | Admin only |
| Activate | — | `status = active` | — |
| Grant beta | — | `beta_flag = true`, `plan = beta` | Yes |
| Revoke beta | Yes | `beta_flag = false`, `plan = free` | Yes |
| Change plan | — | Updates license record | Yes |
| Force logout | — | All refresh tokens invalidated | — |
| Revoke device | — | Single device's sessions invalidated | Yes (re-register) |
| Add admin note | — | Appends to notes field | Editable |

All actions are logged to `admin_audit_log` with before/after state, admin user_id, and IP.

---

## 5. Beta Management

### 5.1 Waitlist view

Columns: email, submitted_at, status (pending / approved / rejected / converted)  
Default sort: submitted_at ascending (oldest first)

**Actions per row:**
- **Approve:** generates personalised invite link, sends email, sets status = 'approved'
- **Reject:** sets status = 'rejected', optionally sends a polite decline email
- **View:** if converted, link to user detail

**Bulk approve:** select multiple pending entries, generate and send all invites in one action.

### 5.2 Invite management

```
Invite record:
  invite_id     UUID
  code          VARCHAR(32) — random URL-safe token
  email         VARCHAR     — pre-filled at registration
  created_by    UUID FK admins
  created_at    TIMESTAMPTZ
  expires_at    TIMESTAMPTZ (default: 7 days)
  used_at       TIMESTAMPTZ
  used_by       UUID FK users
```

**Create invite:** Admin enters email → system generates `https://useatlas.dev/register?invite=<code>` → copies to clipboard, optionally sends email.

**Invite link behaviour:**
- Registration form pre-fills email from invite
- On registration, `beta_flag = true` and `plan = beta` set automatically
- Invite marked `used_at` on first use
- Expired or used invites return a clear message: "This invite link has expired. Contact support for a new one."

### 5.3 Beta cohort view

Summary table of all beta users:
- Email, status, last_seen, devices, usage (30d exports), token savings
- Exportable as CSV for analysis

---

## 6. Analytics Dashboard

### 6.1 Usage trends

Time range selector: 7d / 30d / 90d / custom

Charts:
1. **Daily Active Users** — line chart, unique users with at least one action
2. **Workflow usage** — stacked area: Change Plans / Debug / What Breaks / Exports
3. **Scans per day** — bar chart
4. **Token savings** — line chart: estimated raw tokens vs Atlas export tokens

### 6.2 Token savings aggregate

```
Platform-wide totals (last 30 days):
  Estimated raw token cost:  147,000,000 tokens
  Atlas export tokens used:    2,940,000 tokens
  Saved:                     144,060,000 tokens
  Savings rate:                       98.0%

Per-plan breakdown:
  beta users:  avg 98.1% savings, median 2,800 tokens/export
  free users:  avg 95.4% savings, median 4,100 tokens/export
```

### 6.3 Error feed

Real-time list of crash events (from desktop app's `/api/operations/crashes` data, anonymised):
- Timestamp, app_version, error kind, message (truncated to 160 chars)
- No stack traces visible in admin console (security: prevents code disclosure)
- Grouped by error kind with occurrence count

---

## 7. Admin API Endpoints

All endpoints require `role = admin` or `role = superadmin` in JWT claims.

### 7.1 User management

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/users` | Search/list users (paginated) |
| GET | `/admin/users/:id` | Full user detail |
| PATCH | `/admin/users/:id` | Update status, role, beta_flag, notes |
| POST | `/admin/users/:id/force-logout` | Revoke all sessions |
| DELETE | `/admin/users/:id/devices/:device_id` | Revoke specific device |

### 7.2 License management

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/licenses` | List licenses with filters |
| PATCH | `/admin/licenses/:id` | Update plan, expiry, limits |
| POST | `/admin/users/:id/grant-beta` | Grant beta flag + plan |
| POST | `/admin/users/:id/revoke-beta` | Revoke beta flag, reset plan to free |

### 7.3 Beta management

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/waitlist` | List waitlist entries |
| POST | `/admin/waitlist/:id/approve` | Approve + send invite |
| POST | `/admin/waitlist/:id/reject` | Reject entry |
| POST | `/admin/invites` | Create new invite link |
| GET | `/admin/invites` | List invites with status |
| DELETE | `/admin/invites/:id` | Revoke unused invite |

### 7.4 Analytics

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/analytics/dashboard` | Aggregate metrics |
| GET | `/admin/analytics/usage` | Usage time series |
| GET | `/admin/analytics/token-savings` | Token saving aggregate |
| GET | `/admin/analytics/errors` | Error/crash feed (anonymised) |

### 7.5 Audit log

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/audit-log` | Admin action history (filterable by admin, target, action, date) |

---

## 8. Admin Console Application

The Admin Console is a standalone web app (not embedded in the desktop app):

**Stack options:**
- Framework: React + TypeScript (or Next.js for SSR)
- Hosting: Same server as the API, served from `/admin/` path with admin-auth middleware
- Auth: Standard JWT in HttpOnly cookie; admin must re-login separately from their Atlas account

**Access control layers:**
1. Network: Optional IP allowlist (Cloudflare or nginx `allow/deny`)
2. Application: JWT `role` claim must be `admin` or `superadmin`
3. Action: `superadmin` required for ban and role changes

**Admin session:**
- Shorter lifetime than user sessions: 4-hour access token, 24-hour refresh
- No offline mode — must be online
- Inactivity timeout: 30 minutes

---

## 9. Implementation Complexity

| Component | Complexity | Estimate |
|---|---|---|
| Admin API endpoints (17 endpoints) | Medium | 1 week |
| Admin Console frontend | Medium | 2 weeks |
| Dashboard charts (recharts or chart.js) | Low | 3 days |
| Audit log infrastructure | Low | 2 days |
| Beta management flows | Low | 2 days |
| Admin auth + role middleware | Low | 1 day |
| **Total** | | **~3–4 weeks** (1 senior engineer) |

Included in the overall Phase 185 estimate of 7–9 weeks (see `phase185_accounts_architecture.md`).
