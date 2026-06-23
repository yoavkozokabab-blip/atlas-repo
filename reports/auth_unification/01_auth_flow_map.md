# 01 — Auth Flow Map (production path)

**Date:** 2026-06-20. Production identity = the **website (Next.js + Supabase)**. The packaged/frozen desktop authenticates against it (single identity).

| Step | File | Function | Endpoint | DB table | Token source |
|---|---|---|---|---|---|
| **Register (web)** | `app/api/auth/register/route.ts` → `app/_lib/auth.ts` | `registerUser` | `POST /api/auth/register` | Supabase `public.users` (via `store.create`) | sets httpOnly cookie via `setSession`→`createToken` (HMAC `AUTH_SECRET`) |
| **Login (web)** | `app/api/auth/login/route.ts` → `auth.ts` | `loginUser` | `POST /api/auth/login` | `public.users` (read) | httpOnly cookie (`createToken`) |
| **Session (web)** | `app/_lib/auth.ts` | `currentUser` / `verifyToken` | `GET /api/auth/session` | `public.users` (getById) | reads `atlas_session` httpOnly cookie |
| **Register (desktop)** | `app/api/auth/desktop/register/route.ts` → `auth.ts` | `registerUser` + `entitlement` | `POST /api/auth/desktop/register` | `public.users` | returns Bearer token (`createToken`) + entitlement |
| **Desktop Login** | `app/api/auth/desktop/login/route.ts`; client `jarvis_desktop/accounts_client.py` | `loginUser` (web) / `_web_login` (client) | `POST /api/auth/desktop/login` | `public.users` | Bearer token cached in signed `accounts_state.json` |
| **Desktop Session** | `jarvis_desktop/accounts_client.py` | `verify_session` / `get_valid_access_token` / `_web_license_status` | `GET /api/auth/desktop/me` | `public.users` (via web) | Bearer token (no refresh; re-login on expiry) |
| **MCP Access** | `jarvis_desktop/mcp_server/runtime.py` | `serve_stdio` / `call_tool` | stdio (spawned by the agent) | none (read-only repo scan) | **none — MCP has NO auth gate** |

**Key facts (code-grounded):**
- One identity store for the production path: **Supabase `public.users`** (web + desktop both go through it).
- Desktop token = the SAME HMAC-signed token the website issues (`createToken`, `AUTH_SECRET`); the desktop is a bearer-token client of the website.
- **MCP usage requires no login** — once the agent spawns `Atlas.exe --mcp`, all 18 tools run locally with no account check.
- `loginUser`/`currentUser` block only `status === "suspended"`. There is **no "pending" status** on the website (`AccountStatus = "active" | "suspended"`).
