# Phase 186B — Accounts Architecture Review

**Scope:** Design review of the Phase 186 accounts implementation  
**Date:** 2026-06-07  
**Type:** Review only — no code changes  

---

## Executive Summary

The Phase 186 architecture is appropriate for a supervised private beta of 5–20 users with one critical operational fix needed before first login: the JWT secret must be stabilised or every service restart logs everyone out. Beyond that, the core design is sound. Seven specific issues would cause real user-facing problems at 100 users. Twelve changes are required before Stripe. The GDPR posture has a structural gap — there is no account deletion path — which must be resolved before any EU users are onboarded.

---

## 1. Is the architecture appropriate for a beta product?

**Yes, with one blocking operational issue.**

The core choices are well-suited to a private beta:

- **SQLite is correct for this scale.** A single-file database with no infrastructure to manage is the right call for 5–100 users. SQLAlchemy abstracts the migration to PostgreSQL when needed.
- **Standalone service with proxy pattern is clean.** The desktop server proxying `/api/accounts/*` to the accounts service on port 8788 solves CORS elegantly and keeps the browser's origin model intact. The JS layer never knows the accounts service port.
- **stdlib-only desktop client is the right constraint.** Adding pip dependencies to the packaged desktop is painful; `urllib.request` + `json` is sufficient and adds zero packaging risk.
- **PrivacyValidator is a genuine architectural achievement.** Structural prevention — reject any unexpected string field at the schema boundary — is far stronger than regex scanning of content. It makes code exfiltration via analytics structurally impossible, not just policy-prohibited.
- **Refresh token rotation with device binding is correct.** The implementation handles the rotation lifecycle properly and the device mismatch revocation is the right response to a potential stolen token.
- **Offline grace is properly isolated.** The desktop app degrades gracefully when the accounts service is unreachable and the 7-day window is enforced on the client side only, which is appropriate since there is no authoritative server to consult.

**The one blocking issue:**

`config.py` line 16–17 generates a new JWT secret on every process start:

```python
_default_secret = secrets.token_hex(32)
JWT_SECRET: str = os.environ.get("ATLAS_JWT_SECRET", _default_secret)
```

Every time the accounts service restarts without `ATLAS_JWT_SECRET` set in the environment, all existing access tokens become invalid. Users with valid refresh tokens will recover automatically on their next request, but users mid-session see a sudden 401 with no explanation. For 5 supervised beta users this is an embarrassing failure mode. This must be resolved before the first real user login — either by setting the env var or by persisting the secret to a local file on first run.

**Minor architectural concerns suitable for private beta:**

- No email verification (documented: skipped intentionally for beta). The tradeoff of faster onboarding vs. fake accounts is correct for a supervised 5-person beta.
- No superadmin bootstrap without direct DB access. Acceptable for 5 users but requires a documented runbook.
- Single uvicorn worker. Fine for private beta; becomes a problem at scale.
- `admin.html` UI was listed in reports but not implemented; admin operations require direct API calls. Functional for a technical operator but not for a non-technical admin.

---

## 2. What data should never be stored?

### Currently stored but should not be

**`Feedback.message_redacted` — field name implies sanitization that does not happen.**  
The column is named `message_redacted` but there is no redaction code anywhere in the service. Free-text feedback from users can contain: API keys they accidentally pasted, file paths, code snippets, email addresses of colleagues, or other PII. The field stores whatever the client sends, verbatim. Either strip known-sensitive patterns before writing, enforce a character limit, or rename the field to `message` to stop implying guarantees that aren't met.

**IP addresses in rate limiter keys.**  
`check_rate_limit(f"login:{client_ip}", ...)` and `check_rate_limit(f"register:{client_ip}", ...)` use the raw client IP as part of the rate limit key. Currently this is only in-memory and never written to disk or DB, which is correct. If the rate limiter is ever migrated to Redis, the IP addresses will persist in Redis. IP addresses are personal data under GDPR. The key should be hashed before storage in any persistent backend.

**`AdminAuditLog.target_user_email` — email snapshot in audit log.**  
When a user's email is changed (not currently implemented but implied by the model), the audit log will have their old email in historical entries. This creates a permanent personal data record that cannot be removed to comply with right-to-erasure requests without destroying audit integrity. Policy decision required before EU users.

**`Device.platform` — OS version string.**  
Currently stores values like "Windows 11". This is device fingerprinting data. For beta, it aids debugging. For production, evaluate whether it's necessary; if kept, document the legal basis.

**Revoked sessions — never cleaned up.**  
The `sessions` table accumulates every refresh token ever issued, with `revoked_at` set but never deleted. At beta scale this is trivial (a few dozen rows). At 1000 users with 30-day token lifetimes, it becomes tens of thousands of rows. Revoked sessions older than 30 days have zero utility and should be pruned.

### What is correctly NOT stored

- IP addresses are not written to the database (only used transiently in rate limiter memory) ✓
- Raw passwords are never stored — only bcrypt hashes ✓
- Source code, repository paths, and prompt text are structurally excluded by PrivacyValidator ✓
- Raw refresh tokens are never stored — only SHA-256 hashes ✓

---

## 3. What can be simplified?

**Multiple file reads per request in `accounts_client.py`.**  
`get_account_state()` calls `get_valid_access_token()` which calls `_load_state()`, and then calls `get_license_status()` which calls `get_valid_access_token()` again, which calls `_load_state()` again. A single GET to `/api/accounts/state` from the browser triggers at least four disk reads of `accounts_state.json`. The state file should be loaded once per call and passed through, or held in a module-level cache with a short TTL (a few seconds). For a file under 1 KB on a local SSD this is inconsequential for performance, but it's unnecessary complexity.

**`get_account_state()` duplicates work.**  
`get_valid_access_token()` and `get_license_status()` both independently check token validity and potentially trigger a token refresh. If both trigger a refresh simultaneously (impossible in single-threaded Python but structurally confusing), they could produce inconsistent results.

**`AdminUserUpdate` conflates two different permission levels in one endpoint.**  
`PATCH /admin/users/{id}` accepts `status`, `role`, `beta_flag`, `plan`, `max_devices`, `expires_at`, and `admin_notes` in a single request body. The permission checks happen inside the handler based on specific field values. Setting `status=suspended` requires admin; setting `status=banned` requires superadmin; setting `role` requires superadmin. This is correct but fragile — a future developer adding a new field may forget to add the check. Splitting into `PATCH /admin/users/{id}/status` and `PATCH /admin/users/{id}/role` with route-level dependencies would make the permission model explicit.

**`EmailToken` model is dead code for beta.**  
The model is defined, the table is created, but it is never read or written anywhere in the service. Email verification is skipped for beta (correctly). The model should remain for future use but should be annotated as `# Not yet used — email verification deferred` rather than silently existing.

**Dashboard fires seven separate COUNT queries.**  
Each metric (total, active, beta, suspended, banned, active_devices, today_usage, feedback_pending) is a separate round-trip to the database. At beta scale this is a 1–2ms issue. It could be one CTE or consolidated into fewer queries, but this is not worth changing until the dashboard feels slow.

**The `non_negative` validator in `UsageEventRequest`** runs on seven fields. Fine — clarity over brevity is correct for a privacy-critical validator.

---

## 4. What would break at scale?

### At 20 users

Nothing breaks functionally. Two operational pain points:

**JWT secret instability** causes logged-out sessions on every restart. With 20 real users expecting persistence, a maintenance window that restarts the service silently logs everyone out. This creates support load and damages trust disproportionate to the actual problem.

**Thread-unsafe state file writes in `accounts_client.py`.**  
The desktop server uses `ThreadingHTTPServer`. Multiple concurrent browser requests (e.g., a component polling `/api/accounts/state` and a user clicking login simultaneously) will both call `_load_state()` / `_save_state()` on the same file without locking. On Windows, file writes are not atomic. A partial write to `accounts_state.json` corrupts the JSON and logs the user out until the file is manually deleted. At 20 users running for weeks, this race will eventually trigger.

### At 100 users

**In-memory rate limiter accumulates without pruning.**  
`_InMemoryStore._windows` is a `defaultdict(deque)` that grows as new keys are seen but never shrinks. The eviction only prunes timestamps within the deque for an existing key; it never removes keys for IPs or users that haven't been seen in weeks. At 100 users doing daily logins, this is ~100–200 keys with ~5–10 timestamps each — negligible. But it is a memory leak for a long-running process and will silently grow unbounded.

**Session table bloat becomes visible.**  
100 users × average 2 sessions per day × 30-day retention before expiry = ~6000 rows. The sessions table has no cleanup. The `refresh_hash` index makes lookup fast, but table size starts affecting disk and backup time.

**Dashboard query latency increases.**  
Seven sequential COUNT queries over 100+ users and their associated devices, sessions, and usage rows starts to add latency. The dashboard will feel slow without adding indexes beyond what the model currently defines.

**SQLite write serialisation.**  
100 users means concurrent analytics events and heartbeats arriving simultaneously. SQLite serialises writes even with WAL mode. At 100 users this is not a bottleneck (a single write takes microseconds) but it establishes the ceiling.

### At 1000 users

**SQLite is the hard limit.**  
SQLite WAL mode can handle thousands of reads concurrently, but concurrent writes serialise. At 1000 users with periodic analytics heartbeats, concurrent writes will queue behind each other. The service will appear slow intermittently. PostgreSQL is required before 1000 users.

**In-memory rate limiter is a security failure.**  
At 1000 users, a brief service restart (deploy, crash, OOM kill) clears all rate limit state. An attacker who can cause the service to restart — even by triggering a crash via a malformed request — gets a clean slate for brute-force attempts. Rate limiting must be moved to Redis or stored in the database before this scale.

**`AdminAuditLog` and `sessions` tables become operational liabilities.**  
With no cleanup, these tables grow at O(users × time). 1000 users × 365 days × 2 sessions/day = 730,000 session rows per year. The audit log grows similarly. Full table scans (e.g., `ORDER BY created_at DESC`) degrade without maintenance.

**`estimated_tokens_saved` aggregation.**  
The dashboard sums `estimated_tokens_saved` for today across all users. At 1000 users each saving ~50k tokens/day, this is a 50M BigInteger per day — fine arithmetically. But without an index on `UsageDaily.date`, this aggregation becomes a full-table scan as rows accumulate.

**Single-process FastAPI becomes a concurrency bottleneck.**  
The service runs as a single uvicorn worker. At 1000 users, simultaneous requests (login, license check, analytics) will queue. Multiple workers require PostgreSQL (SQLite with multiple writers causes locking errors) and a process-safe rate limiter.

---

## 5. What security risks remain?

**Severity: Critical**

**JWT secret regenerates on restart.** (config.py:17)  
Covered above. This is a reliability issue with security implications: if an admin forgets to set the env var, all users are logged out. An attacker who can force a service restart can invalidate all sessions. Fix: persist a generated secret to a protected local file on first run, or require the env var.

---

**Severity: High**

**Refresh token stored in plaintext on disk.**  
`accounts_state.json` contains the raw 64-character hex refresh token with 30-day validity. On Windows, this file sits in `%LOCALAPPDATA%\Atlas\desktop_data\` or `~\.jarvis_desktop\`. Default Windows file permissions make this readable by any process running as the same user, and by administrators. A local privilege escalation or a process with read access to `%LOCALAPPDATA%` can steal long-lived credentials. The access token has a 15-minute window; the refresh token is the real asset. Options: encrypt with OS credential store (Windows Credential Manager / macOS Keychain), or accept this as a known beta limitation and document it.

**`_token_payload()` does no signature verification.**  
The desktop client decodes the JWT payload using base64 without verifying the HMAC signature. This is used only to check the `exp` claim to decide whether to refresh. The actual authentication happens server-side, so this cannot be exploited to bypass auth. However, an attacker who can write `accounts_state.json` could insert a JWT with a future `exp` to indefinitely suppress the refresh call, causing the client to use a token the server has already rejected (e.g., after force-logout). This is a subtle confused deputy: the client trusts an unverified claim to decide whether to trust the server.

**Per-account brute force has no lockout.**  
Rate limiting is per source IP, not per email address. An attacker with access to multiple IPs (botnets, VPN exit nodes, cloud IPs) can distribute password attempts across IPs and never trigger the per-IP limit while still targeting a specific account. For a small beta with known users this risk is low, but it is a gap that must be addressed before public launch.

**`AdminUserUpdate` does not validate enum values.**  
`status` and `role` fields in `AdminUserUpdate` are `Optional[str]` with no Pydantic enum constraint. An admin can set `status` to any string value (e.g., `"approved"`, `"premium"`) that is not in `USER_STATUSES`. This will fail at the SQLAlchemy layer when committing to SQLite (enum validation), but the error message will be a 500 rather than a 422, and the behavior is database-backend-dependent. With PostgreSQL these would be native enums and fail at the DB level. Add `Literal["pending", "active", "beta", "suspended", "banned", "expired"]` constraints to the schema.

**A regular admin can reinstate a banned user.**  
`PATCH /admin/users/{id}` checks if `body.status == "banned"` before requiring superadmin, but does not check if the target user is currently banned before allowing a status change back to `"active"`. A regular admin can change a banned user's status to `"active"` or `"suspended"`. Only banning requires superadmin; un-banning does not. This is likely unintentional and should require the same privilege level.

---

**Severity: Medium**

**Email existence oracle via registration.**  
`POST /auth/register` returns HTTP 409 with `"Email already registered."` for a duplicate email. `POST /auth/login` returns HTTP 401 with `"Invalid email or password."` for both unknown email and wrong password. These are correctly asymmetric — registration 409 vs. login 401 — and the login response does not reveal whether the email exists. However, the registration endpoint itself is an oracle: an attacker can enumerate whether an email is registered without attempting a login at all, bypassing the login rate limiter. Registration rate limiting (10/hour/IP) mitigates this but does not eliminate it. Consider returning 200 on duplicate registration with a "check your email" message.

**No CSRF protection on accounts endpoints.**  
The accounts routes are served at `http://localhost:8777/api/accounts/*`. A malicious web page can make cross-origin requests to localhost if the user visits the page while Atlas is running. JSON POST requests require a preflight (which protects against simple form submissions), but the CORS configuration allows `allow_origins=["http://localhost:8777", "http://127.0.0.1:8777", ...]` with `allow_credentials=True`, which could be exploited if the attacker can load their page from one of those origins (unlikely in normal operation but possible via XSS on a local web page). For beta the risk is negligible; for production, add a CSRF token.

**`/docs` OpenAPI UI is exposed in production builds.**  
`main.py` sets `docs_url="/docs"`. On a local 127.0.0.1 service this is low risk. If the service is ever exposed beyond localhost (even on a LAN), the docs UI provides a complete interactive attack surface with no authentication. Set `docs_url=None` for production deployments.

**`time.monotonic()` in rate limiter, not `time.time()`.**  
The in-memory rate limiter uses `time.monotonic()` for the sliding window. This is process-relative and does not survive restarts, which means the window resets on restart. Additionally, `time.monotonic()` is not comparable across processes or after system sleep/hibernate. If the service is used on a laptop that sleeps and wakes, the monotonic clock may skip forward unpredictably, evicting rate limit state that should still be valid. `time.time()` (wall clock) is more appropriate here despite being settable by the system clock.

---

## 6. What GDPR/privacy risks remain?

**Structural gap: no account deletion.**  
GDPR Article 17 (right to erasure) requires the ability to delete a user's personal data on request. There is no `DELETE /user/me` endpoint, no admin-side user deletion, and no data cascade path. Emails, usage data, session history, feedback, and device records are permanent. This is not a theoretical concern — it is a legal requirement for any EU users. If Atlas is used in the EU (even one user), this is a compliance failure. Implement before any EU onboarding.

**No privacy notice consent at registration.**  
GDPR Article 7 requires freely given, specific, informed, and unambiguous consent. The register endpoint accepts email and password with no reference to a privacy policy or terms of service. There is no `accepted_terms: bool` field, no timestamp of consent, and no version tracking. Before EU users, add a `terms_version` field to User and require acceptance at registration.

**Email stored in audit log snapshots cannot be erased.**  
`AdminAuditLog.admin_email` and `AdminAuditLog.target_user_email` are point-in-time snapshots. They survive even if the corresponding User row is deleted. Audit log integrity (INSERT-only, immutable) conflicts directly with the right to erasure. This is a known tension in GDPR compliance. Policy options: pseudonymise email in audit logs at write time (store a hash instead of the address), or retain audit logs under the "legitimate interest" legal basis with a defined retention window. No current policy exists.

**No data retention policy for any table.**  
GDPR Article 5(1)(e) requires data not be kept longer than necessary for its purpose. Currently:
- `sessions`: retained indefinitely including revoked sessions
- `usage_daily`: retained indefinitely
- `admin_audit_log`: retained indefinitely (justifiable for audit purposes, but needs a policy)
- `feedback`: retained indefinitely

Each table needs a defined retention period and an automated cleanup process.

**`admin_notes` are inaccessible to the user.**  
GDPR Article 15 grants the right of access to all personal data held. `User.admin_notes` contains arbitrary text about the user written by administrators. Users cannot currently see this data. If admin notes contain personal information (they likely will: "user complained about X", "enrolled via referral from Y"), they are subject to Article 15 access requests and Article 17 erasure requests.

**`last_seen_at` and device activity timestamps are behavioral personal data.**  
These timestamps, linked to `user_id` and `device_id`, are personal data about online activity under GDPR. They must be included in any data subject access response and deleted on erasure requests.

**No data portability endpoint.**  
GDPR Article 20 requires a machine-readable export of data provided by the user in a format that can be transferred to another controller. There is no `GET /user/export` endpoint. For beta, this is acceptable as a known gap if EU users are not yet onboarded. It is required before any EU commercial use.

**`estimated_tokens_saved` is linked to user identity.**  
Even though this is a derived aggregate metric, it is linked to `user_id`. Under GDPR, any data linkable to an identified natural person is personal data. This needs to be included in access and erasure responses.

---

## 7. What should be changed before Stripe?

Stripe introduces a contractual relationship (users pay money), which raises the bar for correctness, reliability, and reversibility in ways the current beta does not require.

**Must have before first paid transaction:**

**Stable JWT secret.**  
A paying user whose session is invalidated by a service restart is a support ticket and a chargeback risk. The JWT secret must be stable across restarts. This is also required before beta at any meaningful scale.

**Email verification.**  
Stripe requires valid emails for payment receipts, refund notifications, and dispute communications. Unverified emails mean receipts bounce and disputes cannot be responded to. The `EmailToken` model exists; the endpoint and send logic do not.

**Password reset.**  
A paying user who forgets their password and cannot recover access will dispute the charge. The `EmailToken` model exists for this purpose; implement the endpoint before charging anyone.

**Account deletion with Stripe subscription cancellation.**  
If a user pays and then deletes their account, the Stripe subscription must also be cancelled. Without a deletion path, deleting a user's account while their subscription remains active creates a billing ghost: Stripe charges a card for a service the user cannot access.

**`stripe_customer_id` and `stripe_subscription_id` on License.**  
The current License model has `plan`, `status`, `expires_at`, and `max_devices`. None of these fields link back to Stripe. To handle subscription events (payment succeeded, payment failed, subscription cancelled), the service needs to look up the License by Stripe customer ID. Add these fields to the License table before processing any webhooks.

**Webhook endpoint and idempotency.**  
Stripe sends subscription lifecycle events (payment_succeeded, payment_failed, subscription_cancelled) that must update `license.status` and `license.expires_at`. The current service has no webhook endpoint. Stripe delivers webhooks with retry logic — the same event may arrive multiple times. The handler must be idempotent. This requires a `processed_webhook_ids` table or Stripe event ID deduplication.

**Subscription expiry enforcement.**  
`license.expires_at` exists and is checked in `users.py`. However, there is no background task that marks licenses as expired when `expires_at` passes. A user whose payment fails on day N but whose `expires_at` is day N+30 will continue to have `valid=True` for a month with no payment. Add a scheduled task (cron, Celery beat, or a background thread) to expire licenses whose `expires_at < utcnow()`.

**`status` field validation in `AdminUserUpdate`.**  
Before paying users exist, an admin accidentally setting `status` to an invalid string is a minor bug. After paying users exist, it could make a paid user's account non-functional in a way that triggers chargebacks.

**Offline grace interaction with payment failure.**  
Currently the 7-day offline grace allows continued use for 7 days when the service is unreachable. With paid plans, this grace period should not extend to cases where the user's payment has failed. The grace logic needs to distinguish "service unreachable" from "service reachable but license invalid." Currently it does not — `get_license_status()` applies the same 7-day window regardless of why the check failed.

---

## 8. What should be changed before public launch?

Public launch means untrusted users, volume, legal obligations, and no ability to manually intervene for every problem. The full list:

**Security:**
- Stabilise JWT secret (critical — listed twice because it must happen first)
- Move rate limiting to Redis; per-account lockout in addition to per-IP
- HTTPS between all components (reverse proxy with Let's Encrypt, minimum)
- Encrypt refresh token at rest (OS credential store or application-layer encryption)
- Remove `/docs` endpoint from production builds
- Add CSRF token requirement to state-changing account endpoints
- Validate enum fields in `AdminUserUpdate` at schema level
- Require superadmin to reinstate a banned user, not just to ban
- Implement account lockout after N failed login attempts per email address

**Data & GDPR:**
- Account deletion endpoint with cascade to all personal data
- Privacy policy acceptance at registration with version tracking
- Data export endpoint (GDPR Article 20)
- Pseudonymise or exclude email from `AdminAuditLog` snapshots
- Define and implement retention policies for sessions (30 days), usage_daily (90 days), audit_log (2 years with policy)
- User-accessible view of `admin_notes` or scrub PII from notes before storing
- Automated session cleanup job (prune revoked/expired sessions older than 30 days)

**Reliability:**
- PostgreSQL migration with Alembic schema migrations
- Multi-worker deployment (gunicorn with uvicorn workers)
- Redis-backed rate limiting
- Database connection pooling (pgBouncer or SQLAlchemy pool)
- Process supervision (systemd, supervisor, or Docker restart policy)
- Health check endpoint wired to load balancer
- Structured logging (JSON logs to stdout, not print/stderr)
- Alerts for: service down, error rate >1%, 401 spike (brute force indicator), DB slow queries

**Functional completeness:**
- Email verification flow (register → verify email → active status)
- Password reset flow (forgot password → email token → reset)
- Superadmin bootstrap endpoint (avoid requiring direct DB access)
- Admin console HTML UI (not just raw API endpoints)
- Feedback submission endpoint in accounts service (currently feedback goes through desktop API only)
- `POST /user/feedback` or equivalent for non-desktop clients

**Operational:**
- Separate dev / staging / production environments with separate DB instances and JWT secrets
- Database backup strategy (point-in-time recovery, tested restore)
- Runbook for: superadmin bootstrap, service restart without session loss, database restore, user deletion on GDPR request
- Dependency pinning lockfile (`requirements.txt` has `==` versions, which is good; add a lockfile for `.lib` contents)
- `.lib` vendored dependencies should be excluded from git or gitignored — they add ~1000 files of third-party code to the repository history

---

## Summary Table

| Item | Beta (5–20) | 100 users | 1000 users | Pre-Stripe | Pre-Launch |
|------|:-----------:|:---------:|:----------:|:----------:|:----------:|
| Stable JWT secret | **CRITICAL** | ✓ needed | ✓ needed | ✓ required | ✓ required |
| Thread-safe state file | Risky | ✓ needed | ✓ needed | ✓ required | ✓ required |
| Session cleanup job | OK | ✓ needed | ✓ needed | ✓ needed | ✓ required |
| Per-account lockout | OK | OK | ✓ needed | ✓ required | ✓ required |
| Redis rate limiter | OK | OK | ✓ needed | ✓ required | ✓ required |
| PostgreSQL | OK | OK | **CRITICAL** | ✓ required | ✓ required |
| Email verification | OK | OK | OK | **REQUIRED** | ✓ required |
| Password reset | OK | OK | OK | **REQUIRED** | ✓ required |
| Stripe fields + webhooks | — | — | — | **REQUIRED** | ✓ required |
| Account deletion | Legal risk | Legal risk | Legal risk | ✓ required | **REQUIRED** |
| GDPR consent at signup | Legal risk | Legal risk | Legal risk | ✓ required | **REQUIRED** |
| HTTPS | OK | OK | ✓ needed | ✓ required | **REQUIRED** |
| Encrypted token at rest | OK | OK | OK | OK | ✓ required |
| Audit log email policy | OK | OK | Legal risk | ✓ needed | **REQUIRED** |

---

## Verdict by Phase

**For 5 supervised beta users today:** Fix the JWT secret stability issue first. Everything else is acceptable with known limitations documented in the runbook.

**For 20 supervised beta users:** Also fix the thread-unsafe state file write race condition in `accounts_client.py`.

**For 100 users:** PostgreSQL migration is not yet required but session cleanup and Redis rate limiting become necessary. The JWT secret issue becomes a repeated support problem at this scale.

**For Stripe:** Email verification, password reset, account deletion, Stripe fields on License, and webhook handling are all hard requirements — not optional polish.

**For public launch:** The full list above. The two non-negotiables are HTTPS and account deletion (GDPR). Everything else has a workaround; those two do not.
