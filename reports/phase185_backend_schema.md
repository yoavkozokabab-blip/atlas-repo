# Phase 185 — Atlas Backend Schema

**Date:** 2026-06-07  
**Type:** Design only. Nothing in this document is implemented.  
**Database:** PostgreSQL 15+

---

## 1. Schema Overview

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│    users     │────►│    licenses      │     │   sessions   │
│              │     │                  │     │              │
│  user_id PK  │     │  license_id PK   │     │ session_id PK│
│  email       │     │  user_id FK      │     │ user_id FK   │
│  status      │     │  plan            │     │ device_id FK │
│  role        │     │  expiry_date     │     │ refresh_hash │
│  beta_flag   │     │  max_devices     │     │ expires_at   │
└──────┬───────┘     └──────────────────┘     └──────────────┘
       │
       ├──────────────────────────────────────────────────────┐
       │                                                        │
       ▼                                                        ▼
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   devices    │     │  usage_daily     │     │  admin_audit_log │
│              │     │                  │     │                  │
│ device_id PK │     │  usage_id PK     │     │  log_id PK       │
│ user_id FK   │     │  user_id FK      │     │  admin_id FK     │
│ platform     │     │  device_id FK    │     │  action          │
│ app_version  │     │  date            │     │  target_user FK  │
│ revoked_at   │     │  scans, plans…   │     │  before/after    │
└──────────────┘     └──────────────────┘     └──────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐
│  email_tokens    │  │  beta_waitlist   │  │  invites          │
│  (verify+reset)  │  │                  │  │                   │
│  token_id PK     │  │  waitlist_id PK  │  │  invite_id PK     │
│  user_id FK      │  │  email           │  │  code UNIQUE      │
│  kind            │  │  status          │  │  created_by FK    │
│  token_hash      │  │  invited_by FK   │  │  used_by FK       │
│  expires_at      │  └──────────────────┘  └───────────────────┘
└──────────────────┘
```

---

## 2. Complete DDL

### 2.1 Core tables

```sql
-- ─────────────────────────────────────────────────────────────────
-- USERS
-- ─────────────────────────────────────────────────────────────────
CREATE TYPE user_status AS ENUM (
    'pending',    -- email not yet verified
    'active',
    'beta',
    'suspended',
    'banned',
    'expired'     -- license lapsed (future billing)
);

CREATE TYPE user_role AS ENUM (
    'user',
    'admin',
    'superadmin'
);

CREATE TABLE users (
    user_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email            VARCHAR(254) NOT NULL,
    password_hash    VARCHAR(256) NOT NULL,       -- Argon2id output
    email_verified   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen        TIMESTAMPTZ,
    status           user_status  NOT NULL DEFAULT 'pending',
    role             user_role    NOT NULL DEFAULT 'user',
    beta_flag        BOOLEAN      NOT NULL DEFAULT FALSE,
    invited_by       UUID         REFERENCES users(user_id) ON DELETE SET NULL,
    invite_code      VARCHAR(64),
    admin_notes      TEXT,                         -- admin-only field

    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE INDEX idx_users_email         ON users (LOWER(email));
CREATE INDEX idx_users_status        ON users (status);
CREATE INDEX idx_users_beta_flag     ON users (beta_flag) WHERE beta_flag = TRUE;
CREATE INDEX idx_users_last_seen     ON users (last_seen DESC);
CREATE INDEX idx_users_created_at    ON users (created_at DESC);


-- ─────────────────────────────────────────────────────────────────
-- LICENSES
-- ─────────────────────────────────────────────────────────────────
CREATE TYPE license_plan AS ENUM ('beta', 'free', 'pro', 'enterprise');
CREATE TYPE license_status AS ENUM ('active', 'expired', 'suspended', 'cancelled');

CREATE TABLE licenses (
    license_id       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    plan             license_plan NOT NULL DEFAULT 'free',
    start_date       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expiry_date      TIMESTAMPTZ,                  -- NULL = no expiry
    max_devices      INTEGER      NOT NULL DEFAULT 1,
    max_repositories INTEGER,                      -- NULL = unlimited
    status           license_status NOT NULL DEFAULT 'active',
    notes            TEXT,                         -- admin notes
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by       UUID         REFERENCES users(user_id) ON DELETE SET NULL
);

-- One active license per user (enforced in application layer + partial unique)
CREATE UNIQUE INDEX idx_licenses_active_user
    ON licenses (user_id)
    WHERE status = 'active';

CREATE INDEX idx_licenses_user_id     ON licenses (user_id);
CREATE INDEX idx_licenses_expiry_date ON licenses (expiry_date)
    WHERE expiry_date IS NOT NULL;


-- ─────────────────────────────────────────────────────────────────
-- DEVICES
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE devices (
    device_id        UUID         PRIMARY KEY,     -- set by desktop app on first install
    user_id          UUID         NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    platform         VARCHAR(32)  NOT NULL,         -- 'windows' | 'macos' | 'linux'
    app_version      VARCHAR(32)  NOT NULL,
    first_seen       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    label            VARCHAR(128),                  -- user-friendly name
    revoked_at       TIMESTAMPTZ,
    revoked_by       UUID         REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_devices_user_id    ON devices (user_id);
CREATE INDEX idx_devices_active     ON devices (user_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_devices_last_seen  ON devices (last_seen DESC);
```

### 2.2 Session and token tables

```sql
-- ─────────────────────────────────────────────────────────────────
-- SESSIONS
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE sessions (
    session_id       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_id        UUID         NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    refresh_hash     VARCHAR(64)  NOT NULL,  -- SHA-256 of refresh token, hex
    family_id        UUID         NOT NULL,  -- shared across rotations of the same chain
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_used        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ  NOT NULL,
    revoked_at       TIMESTAMPTZ,
    revoked_reason   VARCHAR(64),             -- 'logout', 'force_logout', 'device_revoked', 'rotation'
    ip_address       INET,
    user_agent       VARCHAR(512)
);

CREATE INDEX idx_sessions_user_id      ON sessions (user_id);
CREATE INDEX idx_sessions_device_id    ON sessions (device_id);
CREATE INDEX idx_sessions_refresh_hash ON sessions (refresh_hash);
CREATE INDEX idx_sessions_active       ON sessions (user_id, device_id)
    WHERE revoked_at IS NULL;


-- ─────────────────────────────────────────────────────────────────
-- EMAIL TOKENS (verification + password reset)
-- ─────────────────────────────────────────────────────────────────
CREATE TYPE token_kind AS ENUM ('email_verification', 'password_reset');

CREATE TABLE email_tokens (
    token_id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    kind             token_kind   NOT NULL,
    token_hash       VARCHAR(64)  NOT NULL,   -- SHA-256 of raw token, hex
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ  NOT NULL,
    used_at          TIMESTAMPTZ,
    ip_address       INET,                    -- IP that requested the token

    CONSTRAINT email_tokens_token_hash_unique UNIQUE (token_hash)
);

CREATE INDEX idx_email_tokens_user_id    ON email_tokens (user_id);
CREATE INDEX idx_email_tokens_kind       ON email_tokens (kind);
CREATE INDEX idx_email_tokens_expires_at ON email_tokens (expires_at)
    WHERE used_at IS NULL;
```

### 2.3 Analytics tables

```sql
-- ─────────────────────────────────────────────────────────────────
-- USAGE DAILY
-- Stores only integer counters. No code, paths, or text of any kind.
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE usage_daily (
    usage_id                UUID     PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID     NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_id               UUID     NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    date                    DATE     NOT NULL,

    -- Activity counters
    launches                INTEGER  NOT NULL DEFAULT 0 CHECK (launches >= 0),
    scans                   INTEGER  NOT NULL DEFAULT 0 CHECK (scans >= 0),
    change_plans            INTEGER  NOT NULL DEFAULT 0 CHECK (change_plans >= 0),
    debug_sessions          INTEGER  NOT NULL DEFAULT 0 CHECK (debug_sessions >= 0),
    what_breaks             INTEGER  NOT NULL DEFAULT 0 CHECK (what_breaks >= 0),
    exports                 INTEGER  NOT NULL DEFAULT 0 CHECK (exports >= 0),

    -- Token savings (integers only — no code content)
    estimated_raw_tokens    BIGINT   NOT NULL DEFAULT 0 CHECK (estimated_raw_tokens >= 0),
    atlas_export_tokens     BIGINT   NOT NULL DEFAULT 0 CHECK (atlas_export_tokens >= 0),
    saved_tokens            BIGINT   NOT NULL DEFAULT 0 CHECK (saved_tokens >= 0),

    received_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT usage_daily_device_date_unique UNIQUE (device_id, date)
);

CREATE INDEX idx_usage_daily_user_id ON usage_daily (user_id);
CREATE INDEX idx_usage_daily_date    ON usage_daily (date DESC);
CREATE INDEX idx_usage_daily_user_date ON usage_daily (user_id, date DESC);
```

### 2.4 Beta management tables

```sql
-- ─────────────────────────────────────────────────────────────────
-- BETA WAITLIST
-- ─────────────────────────────────────────────────────────────────
CREATE TYPE waitlist_status AS ENUM ('pending', 'approved', 'rejected', 'converted');

CREATE TABLE beta_waitlist (
    waitlist_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email            VARCHAR(254)    NOT NULL,
    submitted_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    status           waitlist_status NOT NULL DEFAULT 'pending',
    notes            TEXT,                      -- admin notes
    invited_by       UUID            REFERENCES users(user_id) ON DELETE SET NULL,
    converted_user_id UUID           REFERENCES users(user_id) ON DELETE SET NULL,
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT beta_waitlist_email_unique UNIQUE (email)
);

CREATE INDEX idx_waitlist_status     ON beta_waitlist (status);
CREATE INDEX idx_waitlist_submitted  ON beta_waitlist (submitted_at DESC);


-- ─────────────────────────────────────────────────────────────────
-- INVITES
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE invites (
    invite_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code             VARCHAR(64) NOT NULL,      -- random URL-safe token
    email            VARCHAR(254),              -- pre-fill if set
    created_by       UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL,
    used_at          TIMESTAMPTZ,
    used_by          UUID        REFERENCES users(user_id) ON DELETE SET NULL,
    revoked_at       TIMESTAMPTZ,

    CONSTRAINT invites_code_unique UNIQUE (code)
);

CREATE INDEX idx_invites_code       ON invites (code);
CREATE INDEX idx_invites_created_by ON invites (created_by);
CREATE INDEX idx_invites_active     ON invites (expires_at)
    WHERE used_at IS NULL AND revoked_at IS NULL;
```

### 2.5 Admin audit log

```sql
-- ─────────────────────────────────────────────────────────────────
-- ADMIN AUDIT LOG
-- Immutable: INSERT only. No UPDATE or DELETE permitted.
-- Enforced at database role level (not just application level).
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE admin_audit_log (
    log_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    admin_id         UUID        NOT NULL,     -- denormalised: admin may be deleted
    admin_email      VARCHAR(254) NOT NULL,    -- snapshot at time of action
    action           VARCHAR(64) NOT NULL,
    target_user_id   UUID,
    target_user_email VARCHAR(254),            -- snapshot
    target_device_id UUID,
    before_state     JSONB,
    after_state      JSONB,
    ip_address       INET,
    user_agent       VARCHAR(512)
);

CREATE INDEX idx_audit_log_admin_id      ON admin_audit_log (admin_id);
CREATE INDEX idx_audit_log_target_user   ON admin_audit_log (target_user_id);
CREATE INDEX idx_audit_log_action        ON admin_audit_log (action);
CREATE INDEX idx_audit_log_created_at    ON admin_audit_log (created_at DESC);

-- Revoke UPDATE and DELETE on this table from the API database role:
-- REVOKE UPDATE, DELETE ON admin_audit_log FROM atlas_api_user;
-- (Executed during DB setup, not in migrations)
```

---

## 3. Database Roles and Permissions

```sql
-- Application user (API server)
CREATE ROLE atlas_api_user LOGIN PASSWORD '...';

GRANT SELECT, INSERT, UPDATE, DELETE ON
    users, licenses, devices, sessions, email_tokens,
    usage_daily, beta_waitlist, invites
    TO atlas_api_user;

GRANT SELECT, INSERT ON admin_audit_log TO atlas_api_user;
-- Note: no UPDATE or DELETE on admin_audit_log

-- Read-only analytics user (reporting/dashboards)
CREATE ROLE atlas_readonly LOGIN PASSWORD '...';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO atlas_readonly;

-- Migration user (CI/CD only, no persistent login)
CREATE ROLE atlas_migrate LOGIN PASSWORD '...';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO atlas_migrate;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO atlas_migrate;
```

---

## 4. Key Queries

### 4.1 Admin dashboard metrics

```sql
-- Active users (24h)
SELECT COUNT(DISTINCT user_id)
FROM usage_daily
WHERE date >= CURRENT_DATE - INTERVAL '1 day';

-- Platform-wide token savings (last 30 days)
SELECT
    SUM(estimated_raw_tokens) AS raw_tokens,
    SUM(atlas_export_tokens)  AS export_tokens,
    SUM(saved_tokens)         AS saved,
    ROUND(100.0 * SUM(saved_tokens) / NULLIF(SUM(estimated_raw_tokens), 0), 1) AS savings_pct
FROM usage_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days';

-- Daily active users (time series)
SELECT date, COUNT(DISTINCT user_id) AS dau
FROM usage_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date;
```

### 4.2 License check for desktop client

```sql
-- Check if device is registered and license is active
SELECT
    u.status           AS user_status,
    u.beta_flag,
    u.role,
    l.plan,
    l.expiry_date,
    l.max_devices,
    l.max_repositories,
    l.status           AS license_status,
    d.revoked_at       AS device_revoked_at,
    (SELECT COUNT(*) FROM devices d2
     WHERE d2.user_id = u.user_id AND d2.revoked_at IS NULL) AS active_device_count
FROM users u
JOIN licenses l ON l.user_id = u.user_id AND l.status = 'active'
JOIN devices d ON d.device_id = $1 AND d.user_id = u.user_id
WHERE u.user_id = $2;
```

### 4.3 User token savings dashboard

```sql
SELECT
    SUM(launches)             AS launches,
    SUM(scans)                AS scans,
    SUM(change_plans)         AS change_plans,
    SUM(debug_sessions)       AS debug_sessions,
    SUM(what_breaks)          AS what_breaks,
    SUM(exports)              AS exports,
    SUM(estimated_raw_tokens) AS raw_tokens,
    SUM(atlas_export_tokens)  AS export_tokens,
    SUM(saved_tokens)         AS saved,
    ROUND(100.0 * SUM(saved_tokens)
          / NULLIF(SUM(estimated_raw_tokens), 0), 1) AS savings_pct
FROM usage_daily
WHERE user_id = $1
  AND date >= CURRENT_DATE - INTERVAL '30 days';
```

---

## 5. Migrations Strategy

Schema changes follow a numbered migration convention:

```
migrations/
  001_initial_schema.sql
  002_add_admin_notes_to_users.sql
  003_add_beta_waitlist.sql
  ...
```

Migration tool: **Alembic** (Python, consistent with existing stack) or raw SQL with a custom apply-order script.

Rules:
- Every migration is forward-only (no down migrations in production)
- Migrations are run by the CI/CD pipeline before deploying new server code
- Column additions are backward-compatible (NOT NULL with DEFAULT, or nullable)
- No column renames or drops until old code is fully retired

---

## 6. Backups and Recovery

| Backup type | Frequency | Retention | Target RTO |
|---|---|---|---|
| Continuous WAL archiving | Real-time | 7 days | < 1 hour (point-in-time) |
| Daily full snapshot | 00:00 UTC | 30 days | < 4 hours |
| Weekly full snapshot | Sunday 01:00 UTC | 12 weeks | < 8 hours |

Backup storage: object storage (S3-compatible), separate region from primary.

---

## 7. Implementation Complexity

### Development effort

| Component | Estimate |
|---|---|
| Initial schema migration (001_initial_schema.sql) | 1 day |
| DB role setup + permissions script | 0.5 day |
| ORM model layer (SQLAlchemy or Tortoise ORM) | 2 days |
| Alembic migration tooling | 0.5 day |
| Backup configuration | 0.5 day |
| Query tuning + index validation | 1 day |
| **Total** | **~1 week** (included in overall Phase 185 estimate) |

### Infrastructure estimate

| Resource | Sizing | Monthly |
|---|---|---|
| PostgreSQL (managed) | 2 vCPU, 4 GB, 20 GB SSD | ~$25–40 |
| Redis (managed, sessions + rate limit) | 256 MB | ~$15 |
| Backup storage | 10 GB object storage | ~$2 |
| **Total DB + cache** | | **~$40–60/month** |

Scaling path: read replica at ~2,000 daily active users; connection pooler (PgBouncer) at ~5,000.

---

## 8. Complete Implementation Estimate (all four documents)

### Development timeline

| Phase | Work | Duration |
|---|---|---|
| 1 — Backend core | Schema, auth API, session management, email flows | 3 weeks |
| 2 — Desktop integration | Auth client, device ID, license cache, analytics batcher | 2 weeks |
| 3 — Admin console | Admin API + web frontend | 2 weeks |
| 4 — Security + testing | Security review, rate limiting, pen test, integration tests | 1 week |
| 5 — Staging + rollout | Staging environment, beta user migration, smoke test | 1 week |
| **Total** | | **~9 weeks** (1 senior full-stack engineer) |

Or 5 weeks with 2 engineers working in parallel on backend + desktop integration.

### Infrastructure monthly operating cost

| Service | Monthly |
|---|---|
| App server (2 vCPU, 4 GB, single instance) | $20 |
| PostgreSQL (managed) | $25–40 |
| Redis (managed) | $15 |
| Email provider (SendGrid, up to 10k/mo) | $0–15 |
| Backup storage | $2 |
| TLS certificate (Let's Encrypt) | $0 |
| Domain (existing) | ~$1 amortised |
| CDN / DDoS protection (Cloudflare free) | $0 |
| **Total (up to 1,000 users)** | **~$65–95/month** |
| **Total (up to 10,000 users)** | **~$180–250/month** |

### What is NOT included in this estimate

- Billing integration (Stripe) — future phase
- Mobile clients — out of scope
- Enterprise SSO (SAML/OIDC) — future phase
- SOC 2 compliance audit — future phase
- Code signing for Atlas.exe — future phase (resolves SmartScreen warning)
