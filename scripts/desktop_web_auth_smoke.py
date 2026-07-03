"""Phase 186A desktop identity smoke test (website mode).

Drives atlas_desktop.accounts_client against a running website (ATLAS_WEB_URL)
to prove the desktop authenticates against the SAME store as the website.

Env required:
  ATLAS_AUTH_MODE=website
  ATLAS_WEB_URL=http://127.0.0.1:3111   (a running `next dev`)
  ATLAS_DESKTOP_DATA=<temp dir>         (isolate test state)
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.environ["ATLAS_WEB_URL"].rstrip("/")
EMAIL = f"desktop.smoke.{int(time.time())}@example.com"
PW = "hunter2hunter2"
fails = []


def check(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        fails.append(name)


def web_post(path, body):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


from atlas_desktop import accounts_client as ac  # noqa: E402

print(f"mode={ac.auth_mode()} web_base={ac.web_base()}")
check("desktop is in website auth mode", ac.auth_mode() == "website")
check("no local accounts service dependency (is_service_running True w/o spawn)",
      ac.is_service_running() is True)

# 1) WEBSITE SIGNUP (as if the user signed up on the site)
status, reg = web_post("/api/auth/desktop/register", {"email": EMAIL, "password": PW, "name": "Smoke"})
check("website signup succeeds", status == 201 and reg.get("ok"))

# 2) DESKTOP LOGIN against the same store
res = ac.login(EMAIL, PW, app_version="0.1.0-beta", platform="test")
check("desktop login ok", bool(res.get("ok")))
check("desktop cached a token", bool(ac.get_valid_access_token()))

# 3) /me returns the SAME user
vs = ac.verify_session()
same = (vs.get("user") or {}).get("email") == EMAIL
check("verify_session authenticated", vs.get("authenticated") is True)
check("/me returns the same user (email matches website signup)", same)

# 4) license = valid free beta
lic = ac.get_license_status()
check("license valid for free beta", lic.get("valid") is True and lic.get("beta") is True)

# 5) tampered token rejected at the authority
tok = ac.get_valid_access_token()
bad = ac._call("GET", "/api/auth/desktop/me", access_token=(tok + "x"), base=ac.web_base())
check("tampered bearer token rejected (401)", bad.get("_http_status") == 401)

# 6) logout clears the token
ac.logout()
check("logout cleared the cached token", ac.get_valid_access_token() is None)
vs2 = ac.verify_session()
check("verify_session after logout = not authenticated", vs2.get("authenticated") is False)

# 7) wrong password → generic anti-enumeration error (no token issued)
bad_login = ac.login(EMAIL, "WRONGWRONG", app_version="0.1.0-beta", platform="test")
check("wrong password rejected", not bad_login.get("ok"))
check("generic error message (anti-enumeration)",
      "invalid email or password" in str(bad_login.get("detail", "")).lower())

print("\nSMOKE " + ("PASSED" if not fails else f"FAILED: {fails}"))
sys.exit(1 if fails else 0)
