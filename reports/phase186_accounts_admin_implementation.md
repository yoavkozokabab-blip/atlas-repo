# Phase 186 — User Accounts, Beta Access & Admin Control

**Status:** Implementation complete  
**Date:** 2026-06-07  
**Commit:** phase186: add accounts and beta admin control

---

## 1. Scope

Phase 186 implements Atlas Accounts v1 — a standalone backend service plus desktop client integration that enables:

- **User registration and login** (email + password, bcrypt, JWT HS256)
- **Refresh token rotation** with device binding
- **License gating** of core desktop workflows
- **7-day offline grace** so local-first positioning is never broken
- **Admin console** for managing users, beta access, devices, and audit logs
- **Privacy-safe usage analytics** — integer counters only, no source code ever

All features are gated by hard rules: no source code collection, no payment, no billing enforcement, no Stripe.

---

## 2. Architecture

```
┌─────────────────────────────────────────────┐
│  Atlas Desktop (jarvis_desktop/)             │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │  server.py   │  │ accounts_client.py │   │
│  │  (port 8777) │  │  (stdlib only)     │   │
│  │  +ACCOUNTS_  │  │  token cache       │   │
│  │   ROUTES     │  │  offline grace     │   │
│  └──────┬───────┘  └────────┬───────────┘   │
│         │ /api/accounts/*   │ urllib         │
└─────────│───────────────────│───────────────┘
          │                   ▼
┌─────────│───────────────────────────────────┐
│  Atlas Accounts Service (port 8788)          │
│  ┌──────────────────────────────────────┐   │
│  │  FastAPI (accounts_service/)         │   │
│  │  /auth/*  /user/*  /analytics/*      │   │
│  │  /admin/*  /health                   │   │
│  │  SQLite → PostgreSQL (production)    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

The desktop app acts as a proxy: the browser JS calls `/api/accounts/*` on the local server (port 8777), which forwards to the accounts service (port 8788). This avoids CORS issues and keeps all browser API calls to one origin.

---

## 3. Files Created

### Backend — `accounts_service/`

| File | Purpose |
|------|---------|
| `config.py` | All config: DB URL, JWT secret, CORS origins, ports, grace period |
| `database.py` | SQLAlchemy engine, SessionLocal, Base, init_db(), get_db() |
| `models.py` | 8 ORM models: User, Device, License, Session, EmailToken, UsageDaily, Feedback, AdminAuditLog |
| `schemas.py` | Pydantic v2 schemas for all requests and responses |
| `security.py` | bcrypt hashing, JWT HS256, refresh token generation, SHA-256 hashing |
| `rate_limit.py` | In-memory sliding window rate limiter (Redis-ready interface) |
| `dependencies.py` | FastAPI deps: get_current_user, require_admin, require_superadmin |
| `routers/__init__.py` | Package marker |
| `routers/auth.py` | POST /auth/register, /login, /refresh, /logout |
| `routers/users.py` | GET /user/me, /user/license, /user/devices; DELETE /user/devices/{id} |
| `routers/analytics.py` | POST /analytics/event with PrivacyValidator |
| `routers/admin.py` | Full admin suite (see Section 5) |
| `main.py` | FastAPI app assembly, CORS, router registration, startup |
| `requirements.txt` | Pinned dependencies for `.lib` install |
| `__init__.py` | Package marker |

### Desktop Integration — `jarvis_desktop/`

| File | Purpose |
|------|---------|
| `accounts_client.py` | stdlib-only client: device_id, token cache, offline grace, all API calls |
| `accounts_routes.py` | `/api/accounts/*` handler table merged into server._route_handlers() |
| `static/atlas_accounts.js` | Frontend: login/register/profile/blocked panels + license gating |

### Modified files

| File | Change |
|------|--------|
| `jarvis_desktop/server.py` | Import ACCOUNTS_ROUTES; merge via `**ACCOUNTS_ROUTES` |
| `jarvis_desktop/static/index.html` | Account nav button, account chip, account screen section, script tag |

### Tests — `jarvis_desktop/tests/`

| File | Coverage |
|------|---------|
| `test_phase186_accounts.py` | Registration, login, refresh rotation, logout, /user/* routes |
| `test_phase186_admin.py` | Dashboard, user list, PATCH/grant-beta/revoke-beta, force-logout, device revocation, audit log |
| `test_phase186_privacy.py` | PrivacyValidator unit tests, analytics endpoint enforcement, payload construction audit |

---

## 4. Auth Flow

### Registration
1. Client POSTs email + password + device_id + app_version + platform
2. Rate limit check: 10 requests/hour per IP
3. Email normalised (lowercase, strip), duplicate check
4. Password hashed with bcrypt (passlib CryptContext)
5. User created with status="active", role="user", beta_flag=False
6. Default License created: plan="free", max_devices=1
7. Device registered (or heartbeat updated if existing)
8. Access token (JWT HS256, 15 min) + refresh token (random 32-byte hex, SHA-256 stored)
9. Session row persisted

### Login
1. Rate limit: 5 attempts/15 min per IP
2. Constant-time: hash a dummy password if user not found (timing attack prevention)
3. Verify password against stored hash
4. Check user status — suspend/ban/expire returns 403 with reason message
5. Device registration/limit enforcement
6. Issue tokens

### Token Refresh
1. Hash incoming refresh token; look up Session row
2. Verify device_id matches session (device theft detection)
3. Rotate: revoke old session, issue new access + refresh tokens
4. If device mismatch: revoke and return 401

### Offline Grace
```
last_license_check + 7 days > now  →  cached license used, _offline=True in response
last_license_check + 7 days < now  →  valid=False, status="offline_grace_expired"
never checked / never logged in    →  valid=False, status="unauthenticated"
```

---

## 5. Admin Endpoints

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /admin/dashboard | admin | Metrics: user counts, usage today, feedback pending |
| GET | /admin/users | admin | Paginated + searchable user list |
| GET | /admin/users/{id} | admin | Single user details |
| PATCH | /admin/users/{id} | admin/superadmin | Update status, beta_flag, plan, notes |
| POST | /admin/users/{id}/grant-beta | admin | Set beta_flag=True, status=beta, plan=beta, max_devices=3 |
| POST | /admin/users/{id}/revoke-beta | admin | Revert beta access |
| POST | /admin/users/{id}/force-logout | admin | Revoke all active sessions |
| DELETE | /admin/users/{id}/devices/{device_id} | admin | Revoke one device + its sessions |
| GET | /admin/audit-log | admin | Paginated audit log |
| GET | /admin/feedback | admin | Feedback inbox |

**Superadmin-only:** banning users (status=banned), role changes

Every state-changing admin action writes an immutable `AdminAuditLog` entry capturing: admin_user_id (denormalised), admin_email (snapshot), action, target_user_id, target_user_email, target_device_id, before/after metadata, timestamp.

---

## 6. Privacy Architecture

### PrivacyValidator
The analytics router enforces a structural privacy guarantee:

```python
class PrivacyValidator:
    ALLOWED_STRING_FIELDS = {"event_type", "app_version", "date"}

    @staticmethod
    def validate(payload: dict) -> None:
        for key, value in payload.items():
            if not isinstance(value, str):
                continue
            if key not in ALLOWED_STRING_FIELDS:
                raise ValueError(f"Unexpected string field: {key!r}")
            if _SECRET_PATTERN.search(value):
                raise ValueError(f"Field {key!r} appears to contain sensitive data")
```

- Any string field outside `{event_type, app_version, date}` → 422 immediately
- Values matching `/api[_-]?key|secret|password|token|bearer|sk-[a-z0-9]+|/[a-z]|[a-z]:\\/i` → 422
- Only integer counter fields are accepted without restriction
- `event_type` limited to 8 known values; unknown types are accepted but do not gate rejection

### What the server MAY receive
| Field | Type | Notes |
|-------|------|-------|
| email | string | Account registration only |
| user_id | string | UUID, system-generated |
| device_id | string | Random hex, client-generated |
| app_version | string | e.g. "0.1.0-beta" |
| event_type | string | One of 8 known values |
| date | string | YYYY-MM-DD |
| launches, scans, etc. | int | Non-negative counters |

### What the server MUST NEVER receive
- Source code or file contents
- Repository paths (raw)
- Raw prompts or export text
- Any string field not in the whitelist

---

## 7. Desktop Client — accounts_client.py

The desktop Python client is **stdlib-only** — no pip packages added to the desktop app. It uses `urllib.request` for HTTP and `json` for serialisation.

Key responsibilities:
- **Device ID**: generated once with `secrets.token_hex(16)`, persisted to `accounts_state.json` in the data directory
- **Token caching**: access + refresh tokens stored in `accounts_state.json`; access token refreshed automatically when <2 min from expiry
- **Offline grace**: license checked from cache if service unreachable; expired if >7 days stale
- **Privacy**: `send_analytics_event()` only builds payloads with whitelisted keys; extra counter names validated against known payload keys with `isinstance(v, int)` guard

---

## 8. Frontend — atlas_accounts.js

Single IIFE module providing:

- **Login panel**: email + password form, error display, enter key support
- **Register panel**: email + password + confirm, client-side length validation
- **Profile panel**: email, plan, status, beta flag, offline warning, device list with remove buttons
- **Blocked panel**: suspended/banned message, sign-out only
- **Account chip**: topbar button showing sign-in state / user · plan
- **License gating**: `[data-lock="1"]` nav items disabled when no valid license
- **Auto-polling**: refreshes state every 60 seconds
- **Event delegation**: dispatches `atlas:viewchange` for profile population

---

## 9. Hard Rules Verification

| Rule | Status |
|------|--------|
| No source code collected | ✅ PrivacyValidator structurally prevents it |
| No repository contents | ✅ No string fields except whitelisted 3 |
| No raw prompt text | ✅ Rejected at schema + validator level |
| No raw export text | ✅ Rejected at schema + validator level |
| Offline local-first preserved | ✅ 7-day grace; desktop works without accounts service |
| No payment / No Stripe | ✅ Not present anywhere in codebase |
| No billing enforcement | ✅ License check is advisory, not a hard gate |

---

## 10. Running the Accounts Service

```powershell
# Install dependencies (one time)
py -3 -m pip install --target accounts_service\.lib -r accounts_service\requirements.txt

# Start the service
py -3 -m accounts_service.main
# → Listening on http://127.0.0.1:8788

# Create first superadmin (SQLite direct or via API + manual DB update)
# Default: any registered user can be promoted via DB until admin console is bootstrapped
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ATLAS_ACCOUNTS_DB` | `sqlite:///./atlas_accounts.db` | SQLAlchemy database URL |
| `ATLAS_JWT_SECRET` | random (re-generated on restart) | JWT signing secret — set in production! |
| `ATLAS_ACCOUNTS_HOST` | `127.0.0.1` | Bind address |
| `ATLAS_ACCOUNTS_PORT` | `8788` | Port |
| `ATLAS_OFFLINE_GRACE_DAYS` | `7` | Days of offline grace |
| `ATLAS_ACCOUNTS_URL` | `http://127.0.0.1:8788` | Desktop client service URL |

**⚠ Production:** set `ATLAS_JWT_SECRET` to a stable 64-char random value. The default re-generates on every startup, invalidating all tokens.

---

## 11. Test Coverage Summary

### test_phase186_accounts.py (23 tests)
- Registration: creates user, rejects duplicate, rejects short password
- Login: returns tokens, rejects wrong password, rejects unknown email, blocks suspended users
- Refresh: issues new tokens, rejects old token after rotation, rejects device mismatch
- Logout: revokes session, always returns 204
- User routes: /user/me, /user/license, /user/devices — auth required

### test_phase186_admin.py (18 tests)
- Dashboard: metrics present, admin required, unauthenticated blocked
- User list: search, get by id, 404 for nonexistent
- User actions: grant-beta, revoke-beta, PATCH status, ban requires superadmin, role change requires superadmin
- Force logout revokes sessions
- Device revocation, nonexistent device returns 404
- Audit log populated after actions, requires admin
- Feedback list accessible to admin, blocked for user

### test_phase186_privacy.py (17 tests)
- PrivacyValidator: whitelisted fields pass, unexpected string fields raise, path fields raise, prompt field raises, file_contents raises, API key in event_type raises, bearer token raises, path in app_version raises, integers always allowed, None values allowed
- Event type whitelist: exact set, no dangerous types
- Analytics endpoint: valid event accepted, source_code field rejected, path field rejected, negative counters rejected, unauthenticated rejected
- Client payload construction: no forbidden keys, guard clause present

---

## 12. Remaining Items (Post-Phase 186)

| Item | Priority | Notes |
|------|----------|-------|
| Production JWT secret management | High | Must be set via env var before public deployment |
| Superadmin bootstrap flow | High | Currently requires direct DB access to create first admin |
| Admin console HTML page | Medium | admin.html with dashboard/user list UI |
| Email verification | Low | Currently skipped for beta (status="active" on register) |
| Password reset flow | Low | EmailToken model exists; endpoint not implemented |
| Redis rate limiting | Low | In-memory store works for single-process; Redis for multi-process |
| PostgreSQL migration | Low | SQLAlchemy is DB-agnostic; change DATABASE_URL |
| HTTPS / reverse proxy | Medium | Required for production deployment |
