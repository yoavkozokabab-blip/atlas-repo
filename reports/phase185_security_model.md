# Phase 185 — Atlas Security Model

**Date:** 2026-06-07  
**Type:** Design only. Nothing in this document is implemented.

---

## 1. Threat Model

Atlas is a local-first tool with a lightweight cloud layer for identity and analytics. The threat surface is deliberately narrow: no source code transits the network, so the highest-value target for attackers is account credentials and usage metadata, not code.

### 1.1 Assets to protect

| Asset | Value | Location |
|---|---|---|
| User source code | Highest | Local machine only — server never receives |
| Export packets (context sent to Claude) | High | Local machine only — server never receives |
| Account credentials | High | Server (hashed) |
| Session tokens | High | Client (memory/disk) + Server (DB) |
| Usage analytics | Low-Medium | Server — counts only, no code content |
| Admin credentials | Critical | Server (hashed) + IP-restricted |

### 1.2 Threat actors

| Actor | Capability | Primary concern |
|---|---|---|
| Credential stuffing bot | Automated, high volume | Brute-force login |
| Phishing attacker | Social engineering | Account takeover via reset |
| Compromised device | Local access | Stolen session tokens |
| Malicious insider (team) | Admin console access | Account manipulation |
| Passive network observer | TLS interception attempt | Token exposure in transit |

### 1.3 Out of scope (local-first guarantee)

- Source code exfiltration: not possible by design — analytics module has no access to code content
- Repository path disclosure: not sent to server
- Export packet interception: exports never transit the network (copy to clipboard locally)

---

## 2. Password Security

### 2.1 Hashing algorithm

**Argon2id** with parameters:
```
memory:     65536 KB  (64 MB)
iterations: 3
parallelism: 4
output length: 32 bytes
salt: 16 bytes random per hash
```

Argon2id is memory-hard (resistant to GPU cracking) and the recommended algorithm by OWASP (2024). If Argon2 is unavailable in deployment, fallback to **bcrypt** with cost factor 12 minimum.

### 2.2 Password requirements

- Minimum length: 12 characters
- No maximum (accept up to 1024 chars; hash truncation mitigated by Argon2's design)
- No forced character class rules (NIST SP 800-63B guidance)
- Reject passwords found in known breach databases (HaveIBeenPwned API, k-anonymity model)
- No periodic forced rotation

### 2.3 Password change security

- Require current password to change (prevents session hijack from changing password)
- Password reset invalidates **all** existing sessions (assume credential compromise)
- Notify user by email when password is changed

---

## 3. Token Design

### 3.1 Access token (JWT)

```
Algorithm: ES256 (ECDSA with P-256 curve)
Header:    { "alg": "ES256", "typ": "JWT" }
Claims:
  sub:    user_id (UUID)
  email:  user email
  role:   "user" | "admin" | "superadmin"
  beta:   boolean
  plan:   "beta" | "free" | "pro" | "enterprise"
  jti:    unique token ID (for potential revocation)
  iat:    issued at
  exp:    iat + 900 (15 minutes)
  aud:    "atlas-api"
  iss:    "atlas-auth"
```

**Why ES256 over HS256:** Asymmetric — the private key never leaves the auth service; other services verify with public key only.

**Why short TTL (15 minutes):** Limits damage from token theft. Desktop client silently refreshes without user interaction.

### 3.2 Refresh token (opaque)

```
Format:    random 32-byte value, base64url-encoded
Storage:   SHA-256 hash stored in DB (never the raw token)
TTL:       30 days from issuance
Binding:   device_id + user_id (cannot be used from a different device)
Rotation:  each refresh issues a new refresh token, old one invalidated
```

**Refresh token rotation:** prevents silent re-use of a stolen refresh token. If the original token is presented after it has been rotated (possible replay), the entire token family is invalidated as a security signal.

### 3.3 Email tokens (verification, reset)

```
Format:    random 32-byte value, base64url-encoded
Storage:   SHA-256 hash stored in DB (never raw)
Delivery:  embedded in URL as query param
TTL:
  Verification: 24 hours
  Reset:         1 hour (shorter — higher stakes)
Single-use: marked used_at on redemption; subsequent use returns 409
```

---

## 4. Session Management

### 4.1 Session lifecycle

```
Login
  → create session record (session_id, user_id, device_id, refresh_token_hash)
  → issue access_token (JWT) + refresh_token (opaque)

Every 13 minutes (2 min before JWT expiry)
  → desktop client calls POST /auth/refresh
  → new JWT issued
  → refresh token rotated

Logout (user-initiated)
  → refresh_token_hash set to NULL (revoked)
  → client deletes local session file

Force logout (admin-initiated)
  → ALL session records for user set revoked = true
  → active JWTs still valid until 15-min TTL (acceptable window)
  → next refresh attempt returns 401

Device revoke (admin-initiated)
  → All sessions for device_id set revoked = true
  → Same JWT TTL caveat as above
```

### 4.2 Local session storage

The desktop app stores the refresh token on disk:

```
Path:       {appdata}/Atlas/session.enc
Format:     AES-256-GCM encrypted
Key source: PBKDF2 derived from device_id + platform salt
            (device_id is unique per install; this provides device binding,
            not strong encryption — the goal is obscurity from casual access,
            not HSM-grade protection)
```

Access token is **never written to disk** — only held in memory for the process lifetime.

### 4.3 Session limits

| Plan | Max concurrent sessions |
|---|---|
| free | 1 (1 device) |
| beta | 3 |
| pro | 5 |
| enterprise | 50 |

Enforced at login: if at device limit, return 403 with clear message.

---

## 5. Transport Security

- All API endpoints served over HTTPS only (HTTP redirects to HTTPS)
- TLS 1.2 minimum; TLS 1.3 preferred
- HSTS header: `Strict-Transport-Security: max-age=63072000; includeSubDomains`
- Certificate: Let's Encrypt (auto-renewed)
- API base URL: `https://api.useatlas.dev`
- Admin console: `https://admin.useatlas.dev`

Desktop client TLS verification:
- Certificate pinning is **not** implemented (breaks on cert rotation, difficult to update in installed builds)
- System CA store is trusted
- Explicit check: reject self-signed certificates

---

## 6. Rate Limiting

All rate limits are per-IP unless noted. Enforced by Redis sliding window.

| Endpoint | Limit | Window | Action on exceed |
|---|---|---|---|
| POST /auth/login | 5 attempts | 15 minutes | 429 + lockout message |
| POST /auth/register | 10 | 1 hour | 429 |
| POST /auth/forgot-password | 3 per email, 10 per IP | 1 hour | 429 (silent — same message as success) |
| POST /auth/reset-password | 3 per token | — | 429 |
| POST /auth/verify-email | 10 | 1 hour | 429 |
| POST /auth/refresh | 20 | 1 minute | 429 |
| POST /client/analytics | 10 per device | 1 hour | 429 (batched — should be rare) |
| GET /client/license-check | 20 per device | 1 hour | 429 (cached locally) |
| All admin endpoints | 100 | 1 minute | 429 |

**Login lockout:** After 5 failed attempts from the same IP in 15 minutes, all subsequent attempts return 429 for the remainder of the window. The response **does not distinguish** between wrong password and non-existent email (prevents user enumeration).

---

## 7. Admin Protection

### 7.1 Access layers

| Layer | Mechanism |
|---|---|
| Network | Optional IP allowlist via Cloudflare/nginx (e.g., office IP only) |
| Application | JWT `role` claim must be `admin` or `superadmin` |
| Action | `superadmin` required for ban, role grant, admin creation |
| Audit | All admin actions logged with actor, target, before/after, IP, timestamp |

### 7.2 Admin account requirements

- Admin accounts are granted by superadmin only (not self-service)
- Admin accounts use the same auth flow but with separate 4-hour session TTL
- Admin console has its own login form; sharing a session with the desktop app is not supported
- Admin inactivity timeout: 30 minutes (shorter than user sessions)

### 7.3 Audit log integrity

Every admin action writes an immutable record:

```sql
admin_audit_log (
  log_id        UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at    TIMESTAMPTZ DEFAULT now() NOT NULL,
  admin_id      UUID        NOT NULL,  -- who did it
  action        VARCHAR(64) NOT NULL,  -- e.g. "suspend_user"
  target_user_id UUID,                 -- affected user (nullable)
  target_device_id UUID,               -- affected device (nullable)
  before_state  JSONB,                 -- previous values
  after_state   JSONB,                 -- new values
  ip_address    INET,
  user_agent    VARCHAR(256)
)
```

No `UPDATE` or `DELETE` is permitted on this table. Read and insert only. This is enforced at the DB role level (admin API user has `SELECT, INSERT` on `admin_audit_log`; no `UPDATE` or `DELETE`).

---

## 8. Input Validation and Injection Protection

### 8.1 API inputs

- All inputs validated at the API layer using Pydantic (FastAPI) with strict types
- Email: normalised to lowercase, validated by RFC 5322 regex
- UUIDs: validated format before DB query (prevents injection via malformed IDs)
- Passwords: length and encoding only; content not analysed server-side
- Analytics payloads: all fields are INTEGER; no string fields that could carry code

### 8.2 SQL injection

- All queries use parameterised statements (ORM or `psycopg3` with `%s` parameters)
- No raw string interpolation in SQL
- DB user for the API has minimum required privileges:
  - No `DROP`, `TRUNCATE`, `CREATE`
  - No access to `admin_audit_log` except `SELECT, INSERT`

### 8.3 CORS policy

API CORS policy:
```
Access-Control-Allow-Origin: https://useatlas.dev, https://admin.useatlas.dev
```
The desktop app calls `localhost:8777` (the local Python server), which proxies or calls the cloud API — it does not call the cloud API directly from browser JavaScript. This avoids CORS complexity for the desktop client.

---

## 9. Privacy Architecture

### 9.1 Local-first enforcement

The analytics module in the desktop app is structured to make code exfiltration structurally impossible:

```python
# analytics/collector.py — DESIGN ONLY

def build_analytics_payload(state: AppState) -> AnalyticsPayload:
    """
    Assembles usage counters from STATE.
    Has NO access to:
      - state.graph (repository graph data)
      - state.buildResult (plan text)
      - state.investigateResult (debug text)
      - state.impactResult (impact text)
      - state.exportPayload (context packets)
    Only reads integer counters from state.stats.*
    """
    return AnalyticsPayload(
        device_id=state.device_id,
        date=today_local(),
        launches=state.stats.launches,
        scans=state.stats.scans,
        change_plans=state.stats.change_plans,
        debug_sessions=state.stats.debug_sessions,
        what_breaks=state.stats.what_breaks,
        exports=state.stats.exports,
        estimated_raw_tokens=state.stats.estimated_raw_tokens,
        atlas_export_tokens=state.stats.atlas_export_tokens,
        saved_tokens=state.stats.saved_tokens,
    )
```

The `AnalyticsPayload` Pydantic model **only accepts integers and UUIDs**. Any attempt to add a string field fails at schema validation.

### 9.2 Data minimisation

| Data field | Collected | Rationale |
|---|---|---|
| Device ID | Yes | Required for device management |
| App version | Yes | Required for crash triage |
| Platform | Yes | Windows/macOS/Linux — required for support |
| Usage counters | Yes | Product analytics |
| Token counts | Yes | Savings metric (integers only) |
| Repository name | **No** | Not needed |
| Repository path | **No** | Not needed |
| File names | **No** | Not needed |
| Source code | **No** | Never sent |
| Export content | **No** | Never sent |
| Plan text | **No** | Never sent |
| IP address (analytics) | No | Not stored in usage_daily |
| IP address (auth) | Yes | Stored in sessions/resets for security |

### 9.3 Data retention

| Data type | Retention | Deletion method |
|---|---|---|
| Active user accounts | Indefinite (while active) | User-initiated or admin action |
| Deleted user accounts | 90 days (for recovery + abuse prevention) | Purge cron job |
| Sessions | 30 days + 7 days after expiry | Purge cron job |
| Usage daily records | 2 years | Purge cron job |
| Admin audit log | Indefinite | No deletion permitted |
| Password reset tokens | 7 days after use/expiry | Purge cron job |
| Email verification tokens | 7 days after use/expiry | Purge cron job |
| Beta waitlist | Indefinite | Manual admin action |

---

## 10. Security Review Checklist (pre-launch)

Before distributing to beta users with accounts enabled:

- [ ] Argon2id implemented with correct parameters (not bcrypt with cost < 12)
- [ ] Refresh token rotation implemented and tested
- [ ] Login rate limiting tested at 5 req/15 min per IP
- [ ] Password reset does not enumerate emails
- [ ] JWT signature verified on every request (not just decoded)
- [ ] Admin routes return 403 for `role = user` token
- [ ] `admin_audit_log` has no UPDATE/DELETE permissions for API user
- [ ] HTTPS enforced; HTTP redirects
- [ ] Refresh token stored hashed in DB, raw value never persisted
- [ ] Analytics payload accepted by API rejects any string field
- [ ] Device binding verified: refresh token rejected from different device_id
- [ ] Force logout invalidates sessions before returning 200
- [ ] Email verification required before login succeeds
- [ ] Penetration test on auth flows (OWASP Top 10 minimum)

---

## 11. Implementation Complexity

| Component | Estimate |
|---|---|
| Argon2id integration + password flow | 1 day |
| JWT signing (ES256 keypair, middleware) | 2 days |
| Refresh token rotation | 2 days |
| Rate limiting (Redis sliding window) | 2 days |
| Admin audit log + DB permissions | 1 day |
| Transport + CORS configuration | 1 day |
| Privacy: analytics payload model enforcement | 1 day |
| Security review + penetration testing | 5 days |
| **Total** | **~2 weeks** (included in overall Phase 185 estimate) |
