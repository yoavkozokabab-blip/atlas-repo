# TASK 6 — Website Smoke Test

**Date:** 2026-06-20. New script `scripts/website_smoke_test.py` (stdlib only; no deps, no secrets logged).

## Usage
```
BASE_URL=https://useatlas.dev py -3 scripts/website_smoke_test.py     # live (after deploy)
py -3 scripts/website_smoke_test.py http://127.0.0.1:3000             # local
# optional, flag-gated:
SMOKE_ALLOW_WRITE=1 ...           # register a throwaway account
SMOKE_EMAIL=.. SMOKE_PASSWORD=..  # attempt login (creds read from env, never logged)
```
Checks `/ /login /download /pricing /contact /privacy /terms` (status + response time + a required text marker) and `/api/health` (JSON: backend/persistence/hostname/validation_passed). Saves `reports/pre_beta_fix/website_smoke_result.json`. Exit 0 = all required pass.

## Local run (dev server, file store) — **PASSED**
```
GET /            200  text:ok
GET /login       200  text:ok
GET /download    200  text:ok
GET /pricing     200  text:ok
GET /contact     200  text:ok
GET /privacy     200  text:ok
GET /terms       200  text:ok
GET /api/health  200  backend=file persistence=ephemeral validation_passed=False
POST /api/auth/register 201  (throwaway)
WEBSITE SMOKE PASSED
```
(Local dev uses the file store, so `validation_passed=false` / `persistence=ephemeral` — expected. Against correctly-configured prod, expect `backend=supabase`, `persistence=ok`, `validation_passed=true`, and `hostname=wggjguqcxmskhjznexum.supabase.co`.)

## Run against production after the owner's env fix
`BASE_URL=https://useatlas.dev py -3 scripts/website_smoke_test.py` — all pages 200 and `/api/health` `persistence:"ok"` with the correct hostname confirms the deployment is healthy. This is **BLOCKED until the owner fixes Vercel env + domain** (no live URL today).
