# IDENTITY MIGRATION PLAN (Phase 186A)

**Date:** 2026-06-20 · **Rule honored:** *do not destroy user data.*

## 1. How much data is actually at risk?

Audited reality: the desktop `accounts_service` has only **local/test SQLite databases** in the repo (`test_accounts_*.db`, `test_phase199.db`, etc.). There is **no evidence of a production user population** — Atlas has not publicly launched. The website Supabase store is **not yet provisioned**, so it holds nothing either.

**Conclusion:** this is almost certainly a **green-field cutover, not a data migration.** The plan below is the safe procedure *if* any real local accounts exist; in the likely case they don't, step 0 confirms it and you skip to a clean provision.

## 2. The hard constraint: incompatible password hashes

- Desktop `accounts_service`: **bcrypt** (`security.py` + `.lib/bcrypt`).
- Website / Supabase canonical: **scrypt** (`auth.ts:10`).

You **cannot** rehash a bcrypt password into scrypt (the plaintext is gone). So any migrated account must either:
- **(A) Dual-scheme verify** — temporarily teach the canonical `verifyPassword` to also accept a `bcrypt$...` stored hash, and **upgrade to scrypt on next successful login** (verify with bcrypt → rehash with scrypt → overwrite). Zero user friction. *Recommended if real users exist.*
- **(B) Forced reset** — import accounts without a usable hash, mark them `must_reset`, and require a password-reset email on first login. Simpler, but friction.

## 3. Procedure

### Step 0 — Confirm scope (do first)
```
# Are there any non-test users in any local accounts DB?
py -3 - <<'PY'
import sqlite3, glob
for db in glob.glob("test_accounts_*.db") + glob.glob("**/accounts*.db", recursive=True):
    try:
        n = sqlite3.connect(db).execute("select count(*) from users").fetchone()[0]
        print(db, n)
    except Exception as e:
        print(db, "skip", e)
PY
```
If every count is 0 / only seeded test rows → **no migration needed.** Provision Supabase fresh (migrations `0001`+`0002`+`0003`) and proceed with `identity_architecture.md`.

### Step 1 — Back up (never destroy)
Copy every `*.db` to `backups/identity_premigration_<date>/`. Commit nothing binary; store outside git.

### Step 2 — Export
For each real user export: `email, password_hash (bcrypt), role, status, plan, created_at, last_seen_at`, and license → `plan`. Emit JSON.

### Step 3 — Transform → website schema
Map to `public.users` columns (`0001_init.sql`): `password_hash` carried **as bcrypt** with its scheme prefix (`bcrypt$...`) for path (A); `plan`/`plan_status` from the License; `downloads=0`.

### Step 4 — Load
Upsert into Supabase `users` via PostgREST (service role), `Prefer: resolution=merge-duplicates` on `email`. Idempotent — safe to re-run.

### Step 5 — Enable dual-scheme verify (path A only)
In `auth.ts verifyPassword`, branch on the stored scheme: `bcrypt$` → bcrypt compare (add a tiny bcrypt verify; Node has none built-in, so either use a WASM bcrypt or path (B)). On success in `loginUser`, rehash with scrypt and `store.update`. Remove this branch once all users have logged in once.

> Note: Node has no built-in bcrypt. If you don't want a new dependency, use **path (B) forced reset** instead — it needs no bcrypt in the website.

### Step 6 — Verify
- Count parity: source users == Supabase users.
- Spot-check 3 accounts: login on web, then desktop `/me`, both return the same identity + plan.
- Confirm suspended/expired states carried over.

### Step 7 — Decommission
Stop spawning `accounts_service` in production (`accounts_service_runner.py`). Keep the code + backups. Delete the abandoned `~/jarvis_landing/api/`.

## 4. Rollback
Migration is additive and idempotent; Supabase rows can be dropped and re-imported from the JSON export. Local DBs are untouched (backed up in Step 1). No destructive step exists before Step 7, and Step 7 only stops a process — it deletes no user data.

## 5. PASS / FAIL / BLOCKED
| Task | Status |
|---|---|
| Migration designed, non-destructive | **PASS** |
| Hash-incompatibility handled | **PASS** (paths A/B documented) |
| Executed | **BLOCKED / likely N/A** — no Supabase project provisioned; no evidence of real users to migrate. |
