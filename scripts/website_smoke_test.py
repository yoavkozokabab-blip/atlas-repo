"""Live website smoke test for the Atlas site (use after deploy).

Usage:
  BASE_URL=https://atlas-repo-wu76.vercel.app py -3 scripts/website_smoke_test.py
  py -3 scripts/website_smoke_test.py http://127.0.0.1:3000

Checks each page's status, response time, and a required text marker, plus
/api/health JSON. Optional, flag-gated:
  SMOKE_ALLOW_WRITE=1            -> register a random throwaway account
  SMOKE_EMAIL + SMOKE_PASSWORD  -> attempt a login with supplied creds
Secrets are never logged (passwords/keys redacted). Exit 0 = all required pass.
"""
import json
import os
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "http://127.0.0.1:3000")).rstrip("/")

PAGES = [
    ("/", "Atlas"),
    ("/login", "password"),
    ("/download", "SmartScreen"),
    ("/pricing", "beta"),
    ("/contact", "ontact"),
    ("/privacy", "rivacy"),
    ("/terms", "erms"),
]


def req(method, path, body=None, headers=None, timeout=20):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    h = {"Accept": "*/*"}
    if data:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, round((time.time() - t0) * 1000), resp.read().decode("utf-8", "replace"), resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, round((time.time() - t0) * 1000), (e.read().decode("utf-8", "replace") if e.fp else ""), url
    except Exception as e:
        return 0, round((time.time() - t0) * 1000), f"{type(e).__name__}: {e}", url


def main():
    print(f"BASE_URL = {BASE}")
    results, ok_all = [], True

    for path, marker in PAGES:
        status, ms, body, _ = req("GET", path)
        text_ok = marker.lower() in body.lower()
        passed = status == 200 and text_ok
        ok_all = ok_all and passed
        results.append({"check": f"GET {path}", "status": status, "ms": ms, "text_ok": text_ok, "passed": passed})
        print(f"  [{'PASS' if passed else 'FAIL'}] GET {path:12s} {status} {ms}ms text:{'ok' if text_ok else 'MISSING'}")

    # /api/health (JSON)
    status, ms, body, _ = req("GET", "/api/health")
    try:
        h = json.loads(body)
    except Exception:
        h = {}
    health_ok = status == 200 and h.get("ok") is True
    sb = h.get("supabase") or {}
    print(f"  [{'PASS' if health_ok else 'FAIL'}] GET /api/health {status} {ms}ms "
          f"backend={h.get('backend')} persistence={h.get('persistence')} "
          f"hostname={sb.get('hostname')} validation_passed={sb.get('validation_passed')}")
    results.append({"check": "GET /api/health", "status": status, "ms": ms, "passed": health_ok,
                    "backend": h.get("backend"), "persistence": h.get("persistence"),
                    "hostname": sb.get("hostname"), "validation_passed": sb.get("validation_passed")})
    ok_all = ok_all and health_ok

    # Optional write: register a throwaway account
    if os.environ.get("SMOKE_ALLOW_WRITE") == "1":
        email = f"smoke+{int(time.time())}@example.com"
        status, ms, body, _ = req("POST", "/api/auth/register", {"email": email, "password": "smoke-pass-12345"})
        passed = status in (200, 201)
        print(f"  [{'PASS' if passed else 'FAIL'}] POST /api/auth/register {status} {ms}ms (throwaway {email})")
        results.append({"check": "POST /api/auth/register", "status": status, "ms": ms, "passed": passed})
        ok_all = ok_all and passed

    # Optional login with supplied creds (never logged)
    if os.environ.get("SMOKE_EMAIL") and os.environ.get("SMOKE_PASSWORD"):
        status, ms, body, _ = req("POST", "/api/auth/login",
                                  {"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]})
        passed = status == 200
        print(f"  [{'PASS' if passed else 'FAIL'}] POST /api/auth/login {status} {ms}ms (creds from env, redacted)")
        results.append({"check": "POST /api/auth/login", "status": status, "ms": ms, "passed": passed})
        ok_all = ok_all and passed

    # Download redirect (only meaningful when authed + ATLAS_INSTALLER_URL set; anon -> /login)
    status, ms, body, loc = req("GET", "/download/atlas")
    print(f"  [info] GET /download/atlas {status} {ms}ms (302 to installer when authed + ATLAS_INSTALLER_URL set; else -> /login)")
    results.append({"check": "GET /download/atlas", "status": status, "ms": ms, "passed": None})

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "reports", "pre_beta_fix", "website_smoke_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"base_url": BASE, "ok": ok_all, "results": results}, open(out, "w"), indent=2)
    print(("\nWEBSITE SMOKE PASSED" if ok_all else "\nWEBSITE SMOKE FAILED") + f" — saved {out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
