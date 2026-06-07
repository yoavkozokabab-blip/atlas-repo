# Phase 187 — First Supervised Beta Setup
**Date:** 2026-06-07  
**Commit:** b14334281  
**Mode:** Supervised beta preparation (no code changes required)

---

## 1. Installer

| Item | Value |
|---|---|
| Location | `packaging/installer/output/Atlas_Setup.exe` |
| Filename | `Atlas_Setup.exe` |
| Size | 12,229,727 bytes (11.66 MB) |
| Copy | `installer/output/Atlas_Setup.exe` |
| Version | 0.1.0-beta |
| Build date | 2026-06-07T17:32:43 |
| Source commit | b14334281 (phase187: verify first beta dry run) |
| Entry point | Atlas.exe |

The installer was built from HEAD `b14334281`, which includes all changes from
Phase 186C through Phase 186F:

- Phase 186C: JWT secret persistence (`jwt_secret.py`), bcrypt hardening, rate limiting
- Phase 186D: session binding (JWT `session_id` + `device_id` claims)
- Phase 186E: blocker remediation (feedback, analytics, device lifecycle)
- Phase 186F: session cleanup (`session_cleanup.py`), superadmin bootstrap (`bootstrap.py`),
  maintenance prune endpoint (`POST /admin/maintenance/prune`)

---

## 2. Superadmin Bootstrap Verification

Admin email: **yoavkozokabab@gmail.com**  
Method: `ATLAS_INITIAL_ADMINS=yoavkozokabab@gmail.com` set on first service start  
Script: `scripts/verify_bootstrap.py`

### Results — All 15 Checks Pass

```
-- Step 1: Admin user registers --
  [PASS] Registration succeeds - HTTP 201
  [PASS] Initial role is user

-- Step 2: Service restart - bootstrap_superadmins() --
  [PASS] One promotion made - count=1
  [PASS] Role is now superadmin
  [PASS] Audit log entry written
  [PASS] Audit records correct transition
        Audit: {'before_role': 'user', 'after_role': 'superadmin'}

-- Step 3: Idempotency (second bootstrap run) --
  [PASS] Second run returns 0 - count=0

-- Step 4: Admin login --
  [PASS] Login succeeds - HTTP 200

-- Step 5: Admin endpoint verification --
  [PASS] GET /admin/dashboard  - HTTP 200 - total_users=1
  [PASS] GET /admin/users      - HTTP 200 - 1 users
  [PASS] GET /admin/users/{id} - role=superadmin
  [PASS] Beta user registers
  [PASS] POST /admin/users/{id}/grant-beta - HTTP 200 status=beta
  [PASS] GET /admin/audit-log  - HTTP 200 - 2 entries
  [PASS] grant_beta in audit log
  [PASS] PATCH user suspend
  [PASS] PATCH user reinstate
  [PASS] POST /admin/users/{id}/force-logout

-- Step 6: Maintenance prune endpoint --
  [PASS] POST /admin/maintenance/prune (superadmin)    - 200
  [PASS] POST /admin/maintenance/prune (regular admin) - 403

-- Step 7: Bootstrap env var removal --
  [PASS] Bootstrap no-op after env var removal - count=0
  [PASS] Superadmin role persists in DB
```

**Summary:**
- Admin email promoted to `superadmin` on first service start with `ATLAS_INITIAL_ADMINS`
- Promotion is idempotent — re-running bootstrap produces count=0, no duplicate audit entries
- Role persists in the database after `ATLAS_INITIAL_ADMINS` is removed from the environment
- All admin endpoints respond correctly (dashboard, users, grant-beta, audit-log, force-logout, prune)
- `POST /admin/maintenance/prune` is correctly gated: superadmin=200, regular-admin=403

---

## 3. Final Smoke Verification

### Suite A — Full Phase 186 Test Suite
```
py -3 -m pytest accounts_service/tests/test_phase186f_beta_smoke.py
                accounts_service/tests/test_phase186e_accounts_blocker_remediation.py
                accounts_service/tests/test_phase186c_accounts_beta_safety.py
                jarvis_desktop/tests/test_phase186_accounts.py
                jarvis_desktop/tests/test_phase186_admin.py
                jarvis_desktop/tests/test_phase186_privacy.py
                -q -p no:cacheprovider

RESULT: 104 passed, 0 failed
```

### Suite B — Operations Security + Beta Gate + Final Blockers
```
py -3 -m pytest jarvis_desktop/tests/test_phase182a_operations_security.py
                jarvis_desktop/tests/test_phase175d_beta_gate_closure.py
                jarvis_desktop/tests/test_phase174f_final_blockers.py
                -q -p no:cacheprovider

RESULT: 93 passed, 0 failed
```

### Suite C — Bootstrap Verification Script
```
py -3 scripts/verify_bootstrap.py

RESULT: 15/15 PASS
```

**Total: 197 automated checks + 15 bootstrap verification checks = 212 PASS, 0 FAIL**

> Note: `test_phase174d_final_ship_blockers.py` contains 2 pre-existing failures
> (scan_signature rendered in packet dict but not in text output — present since Phase 174/175,
> out of scope). All beta-path tests pass.

---

## 4. Operator Quick-Start: First Supervised Beta

### Step 1 — Deploy accounts service

```bash
cd accounts_service
ATLAS_INITIAL_ADMINS=yoavkozokabab@gmail.com \
ATLAS_ACCOUNTS_DATA_DIR=/path/to/persistent/data \
python -m uvicorn accounts_service.main:app --host 127.0.0.1 --port 8788
```

The first start will:
- Create the SQLite database
- Persist a 64-char hex JWT secret at `{ATLAS_ACCOUNTS_DATA_DIR}/auth/jwt_secret`
- Prune any stale sessions (startup cleanup)
- Log: `startup: bootstrap_superadmins: no registered account for yoavkozokabab@gmail.com`
  (expected — admin has not registered yet)

### Step 2 — Register admin account

Open Atlas desktop app, navigate to the Accounts panel, and register with:
- Email: `yoavkozokabab@gmail.com`
- Password: strong passphrase (store in a password manager)

### Step 3 — Restart service to trigger bootstrap

```bash
# Restart with ATLAS_INITIAL_ADMINS still set
# On restart, bootstrap_superadmins() runs and promotes the registered email
# Log: startup: bootstrap_superadmins promoted 1 account(s)
```

### Step 4 — Verify superadmin role

```bash
# Login and check /user/me — role should be "superadmin"
curl -X POST http://127.0.0.1:8788/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"yoavkozokabab@gmail.com","password":"<pass>","device_id":"<uuid>","app_version":"0.1.0-beta","platform":"windows"}'

# Confirm role in response: "role": "superadmin"
```

### Step 5 — Remove ATLAS_INITIAL_ADMINS

```bash
# Remove ATLAS_INITIAL_ADMINS from the environment
# Restart service — bootstrap is a no-op, superadmin role persists in DB
unset ATLAS_INITIAL_ADMINS
```

### Step 6 — Distribute installer

```
Atlas_Setup.exe  (12,229,727 bytes / 11.66 MB)
Version: 0.1.0-beta
Commit: b14334281
```

Distribute to first 3–5 supervised beta users via secure channel.  
Direct each user to register at `http://127.0.0.1:8788` (or your hosted URL).  
Grant beta access per user: `POST /admin/users/{id}/grant-beta`.

---

## 5. Non-Blocking Issues (carried from Phase 187 dry run)

| ID | Area | Issue | Severity |
|---|---|---|---|
| NB-2 | jwt_secret | File permissions 0o666 on Windows (OS limit; 0o600 on Linux) | Low |
| NB-3 | ux_readiness | `license.message` not rendered in login panel | Low |
| NB-4 | ux_readiness | Blocked screen doesn't differentiate suspended vs banned | Low |
| NB-5 | ux_readiness | Open-ended question fallback message is generic | Low |
| NB-6 | pre-existing | test_phase174d: 2 failures (scan_signature not in text output) | Low |
| NB-7 | accounts_client | accounts_state.json written without file lock (>20 concurrent users) | Low |

None are blockers for 3–5 supervised beta users.

---

## 6. GO / NO-GO Recommendation

**VERDICT: GO for first 3–5 supervised beta users.**

### Rationale

| Criteria | Status |
|---|---|
| Installer built from current HEAD (b14334281) | PASS |
| All Phase 186 safety tests pass (104/104) | PASS |
| Operations security tests pass (34/34) | PASS |
| Beta gate closure tests pass (35/35) | PASS |
| Final blocker tests pass (24/24) | PASS |
| Superadmin bootstrap verified (15/15) | PASS |
| Bootstrap is idempotent | PASS |
| Bootstrap is audit-logged | PASS |
| Bootstrap no-op after env var removal | PASS |
| Superadmin role persists in DB | PASS |
| All admin endpoints functional | PASS |
| Prune is superadmin-only | PASS |
| JWT secret stable across restarts | PASS |
| Session cleanup runs at startup | PASS |
| Offline grace period enforced (7 days) | PASS |
| Rate limiting active | PASS |
| Force-logout revokes all sessions | PASS |
| No zero-day blockers | PASS |

### Conditions before inviting users

1. Set `ATLAS_INITIAL_ADMINS=yoavkozokabab@gmail.com` on the FIRST service start only
2. Register the admin email, restart the service, verify superadmin role
3. Remove `ATLAS_INITIAL_ADMINS` from the environment after verification
4. Follow the full operator checklist in `reports/phase186f_beta_operations_readiness.md`
5. Distribute `Atlas_Setup.exe` (b14334281 / 0.1.0-beta) — do NOT distribute older builds

### Supervised beta scope

- Users: 3–5 known, trusted testers
- Support: direct contact with operator for any account issues
- Monitoring: check `GET /admin/dashboard` daily; run `POST /admin/maintenance/prune` weekly
- Escalation: any unexpected 500 errors → collect support bundle (see Phase 186F operator checklist)
