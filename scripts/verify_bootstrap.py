"""Bootstrap verification script for Phase 187.

Runs a complete superadmin bootstrap verification:
  1. Register admin email
  2. Run bootstrap_superadmins (simulates service startup with ATLAS_INITIAL_ADMINS)
  3. Verify superadmin role
  4. Verify all admin endpoints
  5. Verify prune is superadmin-only
  6. Verify bootstrap is no-op after env var removal
  7. Verify superadmin role persists in DB
"""
from __future__ import annotations

import os
import secrets
import sys

sys.path.insert(0, ".")
sys.path.insert(0, os.path.join(".", "accounts_service", ".lib"))

os.environ["ATLAS_ACCOUNTS_DB"] = "sqlite:///./test_bootstrap_verify.db"
os.environ["ATLAS_JWT_SECRET"] = "bootstrap-verify-secret-phase187-32bytes!!"
os.environ["ATLAS_INITIAL_ADMINS"] = "yoavkozokabab@gmail.com"

from accounts_service.config import INITIAL_ADMINS
from accounts_service.database import Base, SessionLocal, engine
from accounts_service.models import AdminAuditLog, User
from accounts_service.bootstrap import bootstrap_superadmins
from accounts_service.rate_limit import reset_rate_limit_store
from fastapi.testclient import TestClient
from accounts_service.main import app

ADMIN_EMAIL = "yoavkozokabab@gmail.com"
ADMIN_PASSWORD = "BetaAdmin2026!"
ADMIN_DEVICE = secrets.token_hex(16)

reset_rate_limit_store()
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)

def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" - {detail}" if detail else ""))
    if not condition:
        raise AssertionError(f"FAILED: {label}")

print("=" * 60)
print("ATLAS BOOTSTRAP VERIFICATION")
print(f"Admin email: {ADMIN_EMAIL}")
print(f"ATLAS_INITIAL_ADMINS: {INITIAL_ADMINS}")
print("=" * 60)

# -- Step 1: Register admin email ----------------------------------
print("\n-- Step 1: Admin user registers --")
reg = client.post("/auth/register", json={
    "email": ADMIN_EMAIL,
    "password": ADMIN_PASSWORD,
    "device_id": ADMIN_DEVICE,
    "app_version": "0.1.0-beta",
    "platform": "windows",
})
check("Registration succeeds", reg.status_code == 201, f"HTTP {reg.status_code}")
user_id = reg.json()["user"]["user_id"]
check("Initial role is user", reg.json()["user"]["role"] == "user")
print(f"  user_id: {user_id}")

# -- Step 2: Bootstrap runs (service restart) ----------------------
print("\n-- Step 2: Service restart - bootstrap_superadmins() --")
db = SessionLocal()
try:
    count = bootstrap_superadmins(db)
    user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    audit = db.query(AdminAuditLog).filter(AdminAuditLog.action == "bootstrap_superadmin").first()
finally:
    db.close()

check("One promotion made", count == 1, f"count={count}")
check("Role is now superadmin", user.role == "superadmin")
check("Audit log entry written", audit is not None)
check("Audit records correct transition",
      audit is not None and audit.metadata_["before_role"] == "user"
      and audit.metadata_["after_role"] == "superadmin")
print(f"  Audit: {audit.metadata_}")

# -- Step 3: Idempotency ------------------------------------------─
print("\n-- Step 3: Idempotency (second bootstrap run) --")
db = SessionLocal()
try:
    count2 = bootstrap_superadmins(db)
finally:
    db.close()
check("Second run returns 0", count2 == 0, f"count={count2}")

# -- Step 4: Login as superadmin ----------------------------------─
print("\n-- Step 4: Admin login --")
login = client.post("/auth/login", json={
    "email": ADMIN_EMAIL,
    "password": ADMIN_PASSWORD,
    "device_id": ADMIN_DEVICE,
    "app_version": "0.1.0-beta",
    "platform": "windows",
})
check("Login succeeds", login.status_code == 200, f"HTTP {login.status_code}")
admin_token = login.json()["access_token"]
auth_h = {"Authorization": f"Bearer {admin_token}"}

# -- Step 5: Admin endpoints --------------------------------------─
print("\n-- Step 5: Admin endpoint verification --")

r = client.get("/admin/dashboard", headers=auth_h)
check("GET /admin/dashboard", r.status_code == 200,
      f"HTTP {r.status_code} - total_users={r.json().get('total_users')}")

r = client.get("/admin/users", headers=auth_h)
check("GET /admin/users", r.status_code == 200,
      f"HTTP {r.status_code} - {len(r.json())} users")

r = client.get(f"/admin/users/{user_id}", headers=auth_h)
check("GET /admin/users/{id} - role=superadmin",
      r.status_code == 200 and r.json()["role"] == "superadmin")

# Register a beta candidate
beta_dev = secrets.token_hex(16)
beta_reg = client.post("/auth/register", json={
    # RFC 6761 reserved TLD: never routes, never collides with a real domain.
    "email": f"beta_{secrets.token_hex(4)}@example.invalid",
    "password": "Beta1234!",
    "device_id": beta_dev,
    "app_version": "0.1.0-beta",
    "platform": "windows",
})
check("Beta user registers", beta_reg.status_code == 201)
beta_id = beta_reg.json()["user"]["user_id"]

# Grant beta
r = client.post(f"/admin/users/{beta_id}/grant-beta", headers=auth_h)
check("POST /admin/users/{id}/grant-beta",
      r.status_code == 200 and r.json()["status"] == "beta",
      f"HTTP {r.status_code} status={r.json().get('status')}")

# Audit log
r = client.get("/admin/audit-log", headers=auth_h)
check("GET /admin/audit-log", r.status_code == 200,
      f"HTTP {r.status_code} - {len(r.json())} entries")
actions = [e["action"] for e in r.json()]
check("grant_beta in audit log", "grant_beta" in actions, f"actions={actions}")

# Suspend and reinstate
r = client.patch(f"/admin/users/{beta_id}", json={"status": "suspended"}, headers=auth_h)
check("PATCH user suspend", r.status_code == 200)
r = client.patch(f"/admin/users/{beta_id}", json={"status": "beta"}, headers=auth_h)
check("PATCH user reinstate", r.status_code == 200)

# Force logout
r = client.post(f"/admin/users/{beta_id}/force-logout", headers=auth_h)
check("POST /admin/users/{id}/force-logout", r.status_code == 204)

# -- Step 6: Maintenance prune (superadmin-only) ------------------─
print("\n-- Step 6: Maintenance prune endpoint --")

r = client.post("/admin/maintenance/prune", headers=auth_h)
check("POST /admin/maintenance/prune (superadmin) - 200",
      r.status_code == 200, f"HTTP {r.status_code} - {r.json().get('pruned')}")

# Regular admin is denied
reg_dev2 = secrets.token_hex(16)
reg2 = client.post("/auth/register", json={
    "email": f"regadmin_{secrets.token_hex(4)}@test.com",
    "password": "Admin1234!",
    "device_id": reg_dev2,
    "app_version": "0.1.0-beta",
    "platform": "windows",
})
reg2_id = reg2.json()["user"]["user_id"]
reg2_email = reg2.json()["user"]["email"]
db = SessionLocal()
try:
    db.query(User).filter(User.user_id == reg2_id).update({"role": "admin"})
    db.commit()
finally:
    db.close()
login2 = client.post("/auth/login", json={
    "email": reg2_email,
    "password": "Admin1234!",
    "device_id": reg_dev2,
    "app_version": "0.1.0-beta",
    "platform": "windows",
})
regular_auth = {"Authorization": f"Bearer {login2.json()['access_token']}"}
r2 = client.post("/admin/maintenance/prune", headers=regular_auth)
check("POST /admin/maintenance/prune (regular admin) - 403",
      r2.status_code == 403, f"HTTP {r2.status_code}")

# -- Step 7: Env var removal --------------------------------------─
print("\n-- Step 7: Bootstrap env var removal --")
import accounts_service.bootstrap as bs_mod
bs_mod.INITIAL_ADMINS = []  # simulates env var removed
db = SessionLocal()
try:
    count_after = bs_mod.bootstrap_superadmins(db)
    user_after = db.query(User).filter(User.email == ADMIN_EMAIL).first()
finally:
    db.close()
check("Bootstrap no-op after env var removal", count_after == 0, f"count={count_after}")
check("Superadmin role persists in DB", user_after.role == "superadmin")

# -- Cleanup ------------------------------------------------------─
Base.metadata.drop_all(bind=engine)
try:
    os.unlink("test_bootstrap_verify.db")
except OSError:
    pass

print("\n" + "=" * 60)
print("BOOTSTRAP VERIFICATION: ALL CHECKS PASS")
print("=" * 60)
print(f"\n  Admin email:         {ADMIN_EMAIL}")
print(f"  Promoted to:         superadmin")
print(f"  Audit logged:        bootstrap_superadmin")
print(f"  Admin endpoints:     OK (dashboard, users, grant-beta, audit-log, prune)")
print(f"  Prune access control: superadmin=200 / regular-admin=403")
print(f"  After env removal:   bootstrap no-op, superadmin role persists")
