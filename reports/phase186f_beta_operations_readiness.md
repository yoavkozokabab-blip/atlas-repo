# Phase 186F — Beta Operations Readiness

Mode: operations-readiness hardening
Prerequisite: Phase 186E closed, commit `791a0e245`
Verdict entering this phase: Accounts GO / 5 users GO / 20 users GO

---

## 1. JWT Secret Provisioning Runbook

### What was already in place (Phase 186C)

`accounts_service/jwt_secret.py` implements a persist-on-create pattern:

1. If `ATLAS_AUTH_JWT_SECRET` (or `ATLAS_JWT_SECRET`) is set in the environment,
   that value is used unconditionally.
2. Otherwise the service looks for a persisted secret file at
   `{ATLAS_ACCOUNTS_DATA_DIR}/auth/jwt_secret`.
   - If the file exists and is non-empty, it is read and returned.
   - If not, a 32-byte cryptographically random hex secret is generated,
     written to the file with mode `0o600` (owner-read-only), and returned.

This means **the service never generates a different secret across restarts**
as long as the data directory is stable — the critical instability noted in
Phase 186B is closed.

### Creation

**New deployment (no existing secret):**

```bash
# Set a stable data directory before first run:
export ATLAS_ACCOUNTS_DATA_DIR=/var/lib/atlas-accounts

# Start the service — jwt_secret.py creates the file automatically:
python -m accounts_service.main
# The file is created at: /var/lib/atlas-accounts/auth/jwt_secret
```

**Explicit creation (operator-generated):**

```bash
export ATLAS_AUTH_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
# Then persist it in your secrets manager or .env file.
```

### Storage

| Scenario | Where the secret lives |
|---|---|
| Local beta (developer machine) | `~/.jarvis_desktop/auth/jwt_secret` (created automatically) |
| Production (Linux service) | `$ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret` — restrict to service user (`chmod 600`, `chown atlas-svc`) |
| CI / test | `ATLAS_JWT_SECRET=test-secret-do-not-use` env var in test setup |

### Environment variable

The service accepts two env var names (checked in order):

```
ATLAS_AUTH_JWT_SECRET   # preferred — explicit auth secret
ATLAS_JWT_SECRET        # legacy alias accepted
```

Set exactly one. If both are set, `ATLAS_AUTH_JWT_SECRET` wins.

### Local beta setup (developer machine)

1. Install and start the accounts service once — the secret file is created
   automatically at `~/.jarvis_desktop/auth/jwt_secret` (or `%LOCALAPPDATA%\Atlas\desktop_data\auth\jwt_secret` on Windows).
2. No manual steps required. The service will use the same secret on every restart.
3. To override (e.g. when sharing a dev DB with teammates), set:
   ```
   ATLAS_AUTH_JWT_SECRET=<shared-secret-from-password-manager>
   ```

### Backup and restore

```bash
# Backup
cp $ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret ~/atlas-jwt-secret.bak
# (Store the backup in a password manager / encrypted volume — not plain disk)

# Restore
cp ~/atlas-jwt-secret.bak $ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret
chmod 600 $ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret
```

If the secret file is lost and no backup exists:
- All existing access tokens become invalid immediately (15-min TTL, so impact is brief).
- All existing refresh tokens become invalid — users must log in again.
- The service auto-generates a new secret on next startup.
- Communicate a "please log in again" notice to users.

### Rotation

Rotation invalidates all refresh tokens (30-day TTL) immediately and all
access tokens within 15 minutes. Only rotate if you suspect compromise.

```bash
# 1. Generate new secret
NEW=$(python -c "import secrets; print(secrets.token_hex(32))")

# 2. Stop service (or rolling-restart if load-balanced)
systemctl stop atlas-accounts

# 3. Replace secret file
echo "$NEW" > $ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret
chmod 600 $ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret

# 4. Restart
systemctl start atlas-accounts

# 5. All users will need to log in again. Post a notice if appropriate.
```

---

## 2. Session Cleanup Job

### Problem

The `sessions` and `email_tokens` tables accumulate rows indefinitely:
- Every login/refresh creates a `Session` row (even revoked/rotated ones).
- Every email-verification or password-reset creates an `EmailToken` row.
- Neither table had any pruning mechanism before Phase 186F.

### Implementation (`accounts_service/session_cleanup.py`)

Two pruning functions, composed into `prune_all`:

| Function | What it deletes |
|---|---|
| `prune_sessions(db)` | Sessions with `expires_at ≤ now` (expired); sessions with `revoked_at ≤ now − 7 days` that are not yet expired (old revoked, past audit-retention window) |
| `prune_email_tokens(db)` | Email tokens with `expires_at ≤ now` OR `used_at IS NOT NULL` |
| `prune_all(db)` | Calls both, then commits. Safe to call repeatedly (idempotent). |

**Safety invariants:**
- Active sessions (`revoked_at IS NULL AND expires_at > now`) are never touched.
- Revoked sessions are retained for 7 days for audit-trail purposes before deletion.
- `prune_all` always commits its own transaction.

### Wiring

`prune_all` is called from `_startup()` in `main.py` so stale rows are removed
on every service restart without requiring a separate cron job (appropriate for
beta / single-server deployment).

### Manual operator trigger

A superadmin-only endpoint was added:

```
POST /admin/maintenance/prune
Authorization: Bearer <superadmin-access-token>
```

Response:
```json
{
  "pruned": {
    "sessions_expired": 12,
    "sessions_revoked_old": 3,
    "email_tokens": 5
  }
}
```

Every call is recorded in `AdminAuditLog` with action `maintenance_prune`.

---

## 3. Superadmin Bootstrap

### Problem

`ATLAS_INITIAL_ADMINS` was parsed in `config.py` but never wired to startup
logic — there was no way to create the first superadmin without direct DB access.

### Implementation (`accounts_service/bootstrap.py`)

`bootstrap_superadmins(db)`:

1. Reads `INITIAL_ADMINS` from config (sourced from `ATLAS_INITIAL_ADMINS` env var).
2. For each email in the list, finds the user in DB (case-insensitive).
3. If the user exists and is not already `superadmin`, promotes them and writes
   an `AdminAuditLog` entry (`action: bootstrap_superadmin`).
4. If the user does not yet exist, logs a message and skips (promotion will
   happen on the next restart after they register).
5. Returns the count of promotions made.

**Idempotency:** Running multiple times is safe — it only upgrades roles, never
downgrades, never fails, never creates users.

**No API surface:** `bootstrap_superadmins` is only called from `_startup()`.
There is no HTTP endpoint that can trigger it.

### How to use

**Before inviting beta users:**

```bash
# Set env var to your own (already-registered) email:
export ATLAS_INITIAL_ADMINS="you@example.com"

# Restart the service:
systemctl restart atlas-accounts
# → your account is now superadmin.
```

**After promotion is confirmed:**

```bash
# Remove the env var to reduce attack surface:
unset ATLAS_INITIAL_ADMINS
# (or remove from .env file / secrets manager)
```

The promotion persists in the DB — removing the env var does not undo it.

### Granting additional admins after bootstrap

Use the superadmin account through the admin API:

```bash
# Get user list to find user_id:
GET /admin/users?q=email@example.com

# Promote to admin (can manage users but cannot ban or change roles):
PATCH /admin/users/{user_id}  {"role": "admin"}

# Promote to superadmin (can ban, unban, change any role):
PATCH /admin/users/{user_id}  {"role": "superadmin"}
```

---

## 4. End-to-End Smoke Test

**File:** `accounts_service/tests/test_phase186f_beta_smoke.py`

**24 tests covering:**

| Class | Tests |
|---|---|
| `TestJwtSecretProvisioning` | env var priority, ATLAS_AUTH_JWT_SECRET priority, stable across calls, file created |
| `TestSessionCleanup` | expired sessions pruned, active sessions not pruned, recent revoke retained, old revoke pruned, email tokens pruned, idempotent |
| `TestSuperadminBootstrap` | promotes registered user, writes audit log, idempotent on existing superadmin, skips unknown email, no-op on empty list |
| `TestFullBetaLifecycle` | register + license check, grant/revoke beta, force-logout, device revocation, suspend/unsuspend, ban requires superadmin, audit log, prune endpoint, prune requires superadmin |

**Run:**
```
py -3 -m pytest accounts_service/tests/test_phase186f_beta_smoke.py -q -p no:cacheprovider
```
Result: 24 passed, 0 failed.

---

## 5. Operator Checklist

### Before inviting the first beta users

- [ ] Confirm `ATLAS_JWT_SECRET` or `ATLAS_AUTH_JWT_SECRET` is set, OR that
      `$ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret` exists and is non-empty.
- [ ] Confirm the secret file has `chmod 600` and is owned by the service user.
- [ ] Confirm a backup of the secret file exists in a password manager.
- [ ] Set `ATLAS_INITIAL_ADMINS=<your-email>`, restart the service, and verify
      your account shows `role: superadmin` in the admin dashboard.
- [ ] Remove `ATLAS_INITIAL_ADMINS` from the environment after confirmation.
- [ ] Open `GET /admin/dashboard` and verify all counters are at 0.
- [ ] Run the smoke test suite: `py -3 -m pytest accounts_service/tests/test_phase186f_beta_smoke.py -q`.
- [ ] Confirm `/health` returns `{"status": "ok"}`.
- [ ] Register a test account, verify it appears in the admin user list as `status: active`.
- [ ] Confirm the test account cannot access `/admin/dashboard` (403).

### Approving a beta user

1. Ask the user to register and share their email with you.
2. Find their `user_id`:
   ```
   GET /admin/users?q=<their-email>
   ```
3. Grant beta access:
   ```
   POST /admin/users/{user_id}/grant-beta
   ```
4. Verify the response shows `beta_flag: true`, `status: beta`, plan `beta`.
5. Inform the user they can now log in and access beta features.

### Revoking a beta user

```
POST /admin/users/{user_id}/revoke-beta
```
- Reverts to `status: active`, plan `free`, `max_devices: 1`.
- Does NOT log them out — their session remains valid until expiry.
- To immediately cut access, also run:
  ```
  POST /admin/users/{user_id}/force-logout
  ```

### Collecting a support bundle

Support bundles are collected from the **desktop app** (not the accounts service).
The desktop support bundle (`GET /api/support/bundle` on port 8777) redacts:
- All tokens (access_token, refresh_token patterns)
- API keys matching known patterns
- File paths and source code

The accounts service has no support bundle endpoint. To manually inspect a
user's state, use the admin API:
```
GET /admin/users/{user_id}         # profile, status, role
GET /admin/users?q=<email>         # find by email
GET /admin/audit-log               # last 100 admin actions
```

### JWT secret rotation

Only rotate if you suspect the secret has been compromised. Rotation forces
all users to log in again (30-day refresh window, 15-min access window).

1. Generate a new secret: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Stop the service.
3. Replace `$ATLAS_ACCOUNTS_DATA_DIR/auth/jwt_secret` with the new value.
4. Update your password-manager backup.
5. Start the service.
6. Notify users that re-login is required.

### Investigating an account bug

```bash
# 1. Find the user
GET /admin/users?q=<email>

# 2. Check their device list
GET /admin/users/{user_id}   # devices are included

# 3. Check audit log for recent admin actions affecting them
GET /admin/audit-log         # filter by eye for target_user_id

# 4. Check their license
GET /admin/users/{user_id}   # license is included in response
```

Common issues:
- `status: pending` — user registered but never activated (normal for Phase 186
  since activation is auto; check if registration completed).
- `status: suspended` — admin action. Check audit log.
- `status: banned` — superadmin action. Check audit log.
- License `valid: false` — check `expires_at` and `status` fields.
- Device `status: revoked` — check audit log for `revoke_device` action.

### Investigating a login or device issue

**User reports "cannot log in" (correct password):**

1. Check `GET /admin/users?q=<email>` — status field.
2. If `suspended` or `banned`, check audit log for the action.
3. If `active` but still can't log in, check for device revocation:
   the `devices` array in the user response shows each device's status.
4. If device is `revoked`, either un-revoke it (not yet implemented — direct
   DB edit required for beta) or ask the user to clear the desktop cache and
   log in with a new device_id (delete `~/.jarvis_desktop/accounts_state.json`).

**User reports "stuck offline / grace expired":**

1. Confirm the accounts service is reachable (health endpoint).
2. Ask the user to delete `~/.jarvis_desktop/accounts_state.json` and log in again.
3. If the service is running but returning 401, the JWT secret may have changed —
   verify the secret file is intact.

**User reports "device limit reached":**

1. Check `GET /admin/users/{user_id}` — `devices` array.
2. Revoke a stale device:
   ```
   DELETE /admin/users/{user_id}/devices/{device_id}
   ```
3. Or increase the license device limit:
   ```
   PATCH /admin/users/{user_id}  {"max_devices": 2}
   ```

---

## Summary of Changes

| Area | Status | Files |
|---|---|---|
| JWT secret provisioning | Already implemented (Phase 186C) | `accounts_service/jwt_secret.py` |
| Session cleanup | Implemented | `accounts_service/session_cleanup.py`, `accounts_service/main.py`, `accounts_service/routers/admin.py` |
| Superadmin bootstrap | Implemented | `accounts_service/bootstrap.py`, `accounts_service/main.py` |
| Smoke test | Implemented (24 tests) | `accounts_service/tests/test_phase186f_beta_smoke.py` |
| Operator checklist | Documented | This report |

## Test Results

- Phase 186F smoke: 24 passed, 0 failed
- Full Phase 186 suite (186C + 186E + 186F + desktop): 104 passed, 0 failed
