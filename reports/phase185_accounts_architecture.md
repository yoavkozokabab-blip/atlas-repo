# Phase 185 — Atlas User Accounts v1: Architecture

**Date:** 2026-06-07  
**Type:** Design only. Nothing in this document is implemented.  
**Constraint:** Repository contents remain local-first. The server never receives source code, file paths, or exported context packets.

---

## 1. System Overview

Atlas currently runs as a self-contained local application: a Python HTTP server with a browser-based frontend, no network dependency, no accounts. Adding accounts introduces a small cloud backend that handles identity, licensing, and usage analytics while preserving the local-first contract.

```
┌─────────────────────────────────────────────────────┐
│                  User's Machine                       │
│                                                       │
│  ┌─────────────────────────────────────────────┐    │
│  │              Atlas Desktop App               │    │
│  │                                               │    │
│  │  ┌──────────────┐  ┌────────────────────┐   │    │
│  │  │ Graph Engine │  │ Intelligence Engine │   │    │
│  │  │  (local)     │  │   (local)           │   │    │
│  │  └──────────────┘  └────────────────────┘   │    │
│  │                                               │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │          Auth Client Layer           │   │    │
│  │  │  • stores session token locally      │   │    │
│  │  │  • sends ONLY counters + metadata    │   │    │
│  │  │  • strips all code content           │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  └─────────────┬───────────────────────────────┘    │
│                │  HTTPS only                          │
└────────────────┼─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              Atlas Cloud Backend                      │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │  Auth API    │  │ License API  │  │Analytics │  │
│  └──────────────┘  └──────────────┘  └──────────┘  │
│                                                       │
│  ┌──────────────────────────────────────────────┐   │
│  │              PostgreSQL                        │   │
│  │  users · licenses · devices · sessions        │   │
│  │  usage_daily · waitlist · audit_log           │   │
│  └──────────────────────────────────────────────┘   │
│                                                       │
│  ┌──────────────┐  ┌──────────────────────────┐    │
│  │    Redis     │  │    Email Provider         │    │
│  │  (sessions,  │  │  (verify, reset, invite)  │    │
│  │  rate limit) │  └──────────────────────────┘    │
│  └──────────────┘                                    │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              Atlas Admin Console                      │
│     (separate web application, admin role only)       │
└─────────────────────────────────────────────────────┘
```

---

## 2. User Authentication

### 2.1 Registration flow

```
User                    Atlas Desktop             Atlas Cloud
  │                          │                        │
  │ enters email+password     │                        │
  │─────────────────────────►│                        │
  │                          │ POST /auth/register     │
  │                          │─────────────────────►  │
  │                          │ 201 { user_id, status: │
  │                          │       "pending_verify" }│
  │                          │◄─────────────────────  │
  │                          │          sends verification email
  │ clicks verify link ────────────────────────────►  │
  │                          │                  marks email_verified=true
  │                          │                  status → "active"
  │◄──────────────────────────────────────────────── │
  │ "Email verified. You can now log in."             │
```

**Registration rules:**
- Email must be unique; checked server-side
- Password minimum: 12 characters
- Passwords stored as Argon2id hashes (never reversible)
- Email verification token expires in 24 hours
- Unverified accounts are purged after 7 days
- Beta launch: registration may be invite-only (checked via `beta_flag` on invite code)

### 2.2 Login flow

```
POST /auth/login
Body: { email, password, device_id, device_platform, app_version }

Response 200:
{
  access_token:  "<JWT, 15 min TTL>",
  refresh_token: "<opaque, 30 day TTL>",
  user: {
    user_id, email, status, role, beta_flag
  },
  license: {
    plan, expiry_date, max_devices, status
  }
}
```

**The desktop app stores:**
- `access_token` in memory (not persisted to disk)
- `refresh_token` encrypted on disk (`{appdata}/Atlas/session.enc`)
- `device_id` (generated once, persisted: `{appdata}/Atlas/device.id`)

**The desktop app never sends:**
- Repository paths
- File contents
- Scan results
- Export payloads

### 2.3 Session management

Sessions use a two-token scheme:

| Token | Type | TTL | Storage | Purpose |
|---|---|---|---|---|
| Access token | JWT (ES256) | 15 minutes | In-memory only | API authentication |
| Refresh token | Opaque UUID | 30 days | Encrypted local file + DB | Silent re-auth |

**Silent refresh:** The desktop client refreshes the access token 2 minutes before expiry using the stored refresh token. The user is never prompted unless the refresh token is also expired or revoked.

**Force logout:** Admin or user revokes all refresh tokens for a user/device. Next refresh attempt returns 401. Desktop shows "Your session has ended — please log in again."

**Offline grace period:** License and session state are cached locally for 7 days. The app works fully offline within that window. After 7 days without a successful check-in, the app shows a gentle notice ("Reconnect to continue" for pro/enterprise; beta/free continue offline indefinitely with degraded license checks).

### 2.4 Email verification

```
POST /auth/verify-email
Body: { token }  ← from email link query param

Tokens:
  - SHA-256 random, 32 bytes
  - Stored as hash in DB
  - Expires: 24 hours
  - Single-use (marked used_at on redemption)
```

### 2.5 Password reset

```
POST /auth/forgot-password
Body: { email }
→ Always returns 200 (prevents email enumeration)
→ If email exists: send reset link

POST /auth/reset-password
Body: { token, new_password }
→ Validates token, hashes new password, invalidates all sessions
```

Reset tokens:
- Expire in 1 hour
- Single-use
- Invalidate all active sessions on redemption (security: assume compromise)

---

## 3. User Data Model

### 3.1 User record

| Field | Type | Notes |
|---|---|---|
| `user_id` | UUID | Primary key, never exposed in URLs |
| `email` | VARCHAR(254) | Unique, lowercase-normalised |
| `password_hash` | VARCHAR | Argon2id output |
| `email_verified` | BOOLEAN | Required for login |
| `created_at` | TIMESTAMPTZ | Account creation |
| `last_seen` | TIMESTAMPTZ | Last successful login or heartbeat |
| `status` | ENUM | `active`, `beta`, `suspended`, `banned`, `expired` |
| `role` | ENUM | `user`, `admin`, `superadmin` |
| `beta_flag` | BOOLEAN | Grants beta features |
| `invited_by` | UUID FK | User who sent invite (nullable) |
| `invite_code` | VARCHAR | Code used at registration (nullable) |

### 3.2 User status states

```
                ┌──────────────┐
                │   pending    │  (email not verified)
                └──────┬───────┘
                       │ email verified
                       ▼
┌──────────┐   ┌──────────────┐   ┌──────────────┐
│ expired  │◄──│    active    │──►│     beta     │
│ (license │   │              │   │ (beta_flag)  │
│  lapsed) │   └──────┬───────┘   └──────────────┘
└──────────┘          │ admin action
                       ▼
                ┌──────────────┐
                │  suspended   │  (temporary, reversible)
                └──────┬───────┘
                       │ admin action
                       ▼
                ┌──────────────┐
                │    banned    │  (permanent)
                └──────────────┘
```

- **active**: Normal user, license-governed
- **beta**: `beta_flag = true`; same as active but with beta features enabled
- **suspended**: Cannot log in; data retained; reversible
- **banned**: Cannot log in or re-register with same email; data retained for audit
- **expired**: License expired; read-only mode; can renew

---

## 4. License Model

### 4.1 License record

| Field | Type | Notes |
|---|---|---|
| `license_id` | UUID | PK |
| `user_id` | UUID FK | One license per user (current active) |
| `plan` | ENUM | `beta`, `free`, `pro`, `enterprise` |
| `start_date` | TIMESTAMPTZ | When plan became active |
| `expiry_date` | TIMESTAMPTZ | NULL = perpetual (free) |
| `max_devices` | INTEGER | How many device registrations allowed |
| `max_repositories` | INTEGER | NULL = unlimited |
| `status` | ENUM | `active`, `expired`, `suspended`, `cancelled` |
| `notes` | TEXT | Admin-editable notes |

### 4.2 Plan limits

| Plan | Devices | Repos | Expiry | Cost model |
|---|---|---|---|---|
| `beta` | 3 | unlimited | Admin-set | Free (supervised access) |
| `free` | 1 | 3 | None | Perpetual |
| `pro` | 5 | unlimited | Annual/monthly | Paid (future) |
| `enterprise` | 50 | unlimited | Custom | Paid (future) |

### 4.3 License check (desktop client)

On startup and every 4 hours, the desktop app calls:

```
GET /client/license-check
Authorization: Bearer <access_token>

Response:
{
  valid: true,
  plan: "beta",
  expiry_date: "2026-12-31T23:59:59Z",
  features: {
    max_devices: 3,
    beta_features: true
  },
  message: null
}
```

The response is cached locally (`{appdata}/Atlas/license.json`) and used offline until stale (7-day grace). The desktop app enforces limits at the UI layer; the server is the authority.

---

## 5. Device Registration

### 5.1 Device record

| Field | Type | Notes |
|---|---|---|
| `device_id` | UUID | PK; generated on first install, stored locally |
| `user_id` | UUID FK | Owner |
| `device_fingerprint` | VARCHAR | Same as device_id (locally generated UUID) |
| `platform` | VARCHAR | `windows`, `macos`, `linux` |
| `app_version` | VARCHAR | e.g. `0.1.0-beta` |
| `first_seen` | TIMESTAMPTZ | First login from this device |
| `last_seen` | TIMESTAMPTZ | Last heartbeat |
| `revoked_at` | TIMESTAMPTZ | NULL = active |
| `revoked_by` | UUID FK | Admin or user who revoked |
| `label` | VARCHAR | User-friendly name (e.g. "Work laptop") |

### 5.2 Device registration flow

```
First login on a new device:
  1. App generates device_id UUID (stored in {appdata}/Atlas/device.id)
  2. Login request includes: device_id, platform, app_version
  3. Server checks: active devices for user ≤ max_devices
  4. If at limit: return 403 with message "Device limit reached (3/3)"
  5. If OK: register device, create session

Subsequent logins:
  1. Device already registered — just refresh session
  2. Server updates last_seen
```

### 5.3 Admin device controls

| Action | Effect |
|---|---|
| Revoke device | Sets `revoked_at`; all sessions for that device invalidated immediately |
| Force logout | Invalidates all sessions for the user (all devices) |
| Disable account | Sets `status = suspended`; all sessions invalidated |

---

## 6. Usage Analytics

### 6.1 What is tracked (metadata only)

```
POST /client/analytics
Authorization: Bearer <access_token>
Body:
{
  device_id: "uuid",
  date: "2026-06-07",          // local date on device
  launches: 1,
  scans: 3,
  change_plans: 2,
  debug_sessions: 1,
  what_breaks: 4,
  exports: 2,
  estimated_raw_tokens: 250000,  // tokens a naive codebase send would cost
  atlas_export_tokens: 4800,     // tokens Atlas's export actually used
  saved_tokens: 245200           // the difference
}
```

### 6.2 What is NEVER tracked

The analytics payload is constructed client-side in Atlas before transmission. The following are explicitly excluded:

- Repository paths or names
- File names or extensions
- Source code of any kind
- Exported context packets
- Change plan request text
- Debug symptom text
- Any text entered by the user

Enforcement: the analytics module reads only counters maintained in `STATE` (e.g., `STATE.stats.scans`) and token-count numbers from the export engine's size calculations. It does not have access to the plan text, file contents, or export payload.

### 6.3 Token dashboard (per user, server-side aggregate)

```
GET /user/usage?period=30d

Response:
{
  period: "30d",
  totals: {
    launches: 42,
    scans: 18,
    change_plans: 31,
    debug_sessions: 14,
    what_breaks: 22,
    exports: 29,
    estimated_raw_tokens: 7250000,
    atlas_export_tokens: 142000,
    saved_tokens: 7108000,
    savings_pct: 98.0
  },
  daily: [ ... per-day breakdown ... ]
}
```

---

## 7. API Surface

### 7.1 Auth endpoints (unauthenticated)

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Issue tokens |
| POST | `/auth/logout` | Revoke refresh token |
| POST | `/auth/refresh` | Exchange refresh → new access token |
| POST | `/auth/verify-email` | Consume verification token |
| POST | `/auth/forgot-password` | Send reset email |
| POST | `/auth/reset-password` | Consume reset token, set new password |

### 7.2 User endpoints (authenticated)

| Method | Path | Purpose |
|---|---|---|
| GET | `/user/me` | Profile + status |
| GET | `/user/license` | Current license |
| GET | `/user/devices` | Device list |
| DELETE | `/user/devices/:device_id` | Self-revoke a device |
| GET | `/user/usage` | Usage dashboard data |

### 7.3 Desktop client endpoints (authenticated, device-scoped)

| Method | Path | Purpose |
|---|---|---|
| POST | `/client/heartbeat` | Update last_seen, receive config |
| POST | `/client/analytics` | Submit daily usage batch |
| GET | `/client/license-check` | Validate license, get feature flags |

### 7.4 Admin endpoints (admin role required)

See `phase185_admin_console.md` for full detail.

---

## 8. Desktop Client Integration

### 8.1 New files required (not implementing — design only)

```
jarvis_desktop/
  auth/
    client.py          # HTTP auth client
    session_store.py   # encrypted local session storage
    device_id.py       # device UUID management
    license_cache.py   # local license state + offline grace
  analytics/
    collector.py       # assembles analytics payload from STATE counters
    batcher.py         # queues and sends batches with retry
```

### 8.2 Startup sequence with accounts

```
1. Atlas starts
2. Load device_id from disk (generate if absent)
3. Load cached license from disk (license.json)
4. If license cache is valid and within grace period:
   → show app normally, attempt background token refresh
5. If no cached license or cache expired:
   → show login screen
6. After login:
   → fetch license, cache locally
   → register device if new
   → show app
7. Every 4 hours (background):
   → heartbeat call (updates last_seen, pulls feature flags)
   → flush analytics batch
```

### 8.3 Offline behaviour

| Scenario | Behaviour |
|---|---|
| No internet, valid cache | Full app, all features, 7-day grace |
| No internet, expired cache | "Reconnect to continue" notice; app continues working |
| Session expired offline | Continues offline; prompts login on next connectivity |
| Device revoked (discovered on next heartbeat) | "This device has been removed from your account" |
| Account suspended (discovered on next heartbeat) | "Your account has been suspended. Contact support." |

---

## 9. Beta Access Flow

```
Option A — Invite link:
  Admin creates invite → generates invite_code URL
  User visits landing.html?invite=<code>
  Registration form pre-fills invite_code
  Server validates code → sets beta_flag = true

Option B — Waitlist approval:
  User submits email at beta.html
  Stored in beta_waitlist table
  Admin reviews list, clicks "Approve"
  System sends personalised invite link
  User registers → beta_flag = true automatically

Option C — Direct grant:
  Admin finds user by email
  Clicks "Grant beta access"
  Sets beta_flag = true, plan = "beta"
```

---

## 10. Implementation Complexity

### Development effort

| Component | Complexity | Estimate |
|---|---|---|
| Backend API (FastAPI + PostgreSQL) | Medium | 3–4 weeks |
| Auth flows (register, verify, login, reset) | Medium | 1 week |
| Session management + token handling | Medium | 3 days |
| License check + feature flag engine | Low | 2 days |
| Device registration + limits | Low | 2 days |
| Analytics pipeline (client + server) | Medium | 1 week |
| Desktop client integration (auth layer) | Medium-High | 1–2 weeks |
| Admin console (separate doc) | Medium | 2 weeks |
| Email templates (verify, reset, invite) | Low | 2 days |
| Testing + security review | High | 1 week |
| **Total** | | **~7–9 weeks** (1 senior engineer) |

### Infrastructure estimate

| Service | Sizing | Monthly cost |
|---|---|---|
| App server (VPS, 2 vCPU, 4 GB) | Single instance | ~$20 |
| PostgreSQL (managed, 10 GB) | db.t3.micro or equivalent | ~$15 |
| Redis (managed, 256 MB) | cache.t3.micro or equivalent | ~$15 |
| Email provider (up to 10k/mo) | SendGrid / Postmark free tier | $0–10 |
| TLS certificate | Let's Encrypt | $0 |
| Domain | useatlas.dev (existing) | ~$15/year |
| **Total (up to 1000 users)** | | **~$50–60/month** |

At 10,000 users: ~$150–200/month (larger DB, read replica, load balancer).
