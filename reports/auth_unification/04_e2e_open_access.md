# 04 — End-to-End Open Access Proof

**Date:** 2026-06-20. Goal: a brand-new user is usable immediately, **no approval anywhere**.

## Worst-case proof (invite mode + empty allowlist — previously blocked everyone)
Ran the website with `BETA_MODE=invite` and `BETA_ALLOWLIST=` (empty) — the exact config that previously produced "waiting for approval" — and registered a fresh, non-allowlisted user:
```
POST /api/auth/desktop/register {new email}  →  ok:true,  approved:true,  message:null
POST /api/auth/desktop/login    {same}        →  ok:true,  token issued
GET  /api/auth/desktop/me  (Bearer)           →  approved:true,  message:null
```
**Before this change:** that same flow returned `approved:false` + "Your account isn't approved for the Atlas beta yet." **After:** `approved:true`, no message — regardless of `BETA_MODE`/`BETA_ALLOWLIST`. (auth.ts `betaApproved` now returns `u.status !== "suspended"`.)

## Desktop side
`jarvis_desktop/accounts_client.py` `_web_license_from_result` reads `approved` (default True). With the website always returning `approved:true`, the desktop license = **valid (`beta_active`)** → no pending dashboard, no second approval. The desktop's "Beta access pending" UI (keyed on `status:"pending"`, which the website never returns) does not trigger.

## MCP
No auth gate in `mcp_server/runtime.py` — once the agent spawns `Atlas.exe --mcp`, all tools work. (Independently proven: frozen-exe answered "where is auth implemented?" → `src/requests/auth.py` #1 in <2s.)

## Full path, now open
```
Register (web / desktop)  →  public.users row, status="active"
   ↓
Login                     →  succeeds (blocked only if suspended); token issued
   ↓
Download + Install        →  installer (owner ops: release + ATLAS_INSTALLER_URL)
   ↓
Desktop Login             →  /api/auth/desktop/login → token; entitlement approved:true
   ↓
Desktop Session           →  /api/auth/desktop/me → approved:true, license valid
   ↓
Atlas usable (MCP)        →  no auth gate; tools respond
```
**No approval, no allowlist, no waitlist gate, no admin action** at any step.

## What was verified vs not
- **Verified here:** the open-access auth behavior (register/login/me, worst-case invite config) + website `tsc`/`build` + MCP smoke.
- **Owner-confirmed (not runnable here):** live production (needs the correct Supabase env + `useatlas.dev`), clean-machine install, real Claude Desktop UI. These are ops, not approval.
