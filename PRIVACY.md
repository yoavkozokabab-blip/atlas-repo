# Atlas Privacy Policy (DRAFT)

> **Status: DRAFT — beta. Requires legal review before publishing.**
> Effective date: _[set on publish]_
> Contact: _[support email — owner to set before publishing; `useatlas.dev` email not yet verified as controlled]_

## Summary

Atlas is **local-first**. The engine that scans your code runs **on your machine**, and
**your source code is not uploaded to Atlas servers** to provide the product. This was
checked by source inspection of the desktop and MCP server (see *Verification* below).

## 1. Data we collect

- **Account data (website):** email and a scrypt-hashed password; subscription/plan
  status. Stored in Supabase. *(scrypt: VERIFIED — `app/_lib/auth.ts`.)*
- **Website request logs:** standard logs (IP, user-agent, timestamps) via our host,
  Vercel. *(Retention: NEEDS OWNER CONFIRMATION.)*
- **Local data (desktop / MCP):** repository indexes, logs, and usage analytics are
  written to your local Atlas data directory and are **not transmitted**. *(Local-only
  analytics: VERIFIED — `analytics.py` writes a local file; no remote endpoint.)*
- **Payments:** none today. Payments are **not enabled** in this beta. If enabled later,
  Stripe would process them and we would not store card numbers. *(Stripe live: NOT
  ENABLED — do not treat as active.)*

## 2. What stays on your machine

Source code, scans/indexes, generated context packs, MCP traffic (local stdio), and
desktop logs/analytics. *(VERIFIED by inspection: no source-upload path found; account
auth payloads exclude source code, file paths, and prompt text — `accounts_client.py`.)*

## 3. What is sent to Atlas servers

Only your account credentials/token to authenticate and manage your account, and standard
website request logs. **Your source code is not sent.**

> Important: when you connect Atlas to an AI agent (Claude, Cursor, Codex), that agent
> receives the context Atlas returns and is then governed by **that vendor's** privacy
> policy. Atlas does not control your agent vendor.

## 4. Third-party processors

- **Supabase** — account database.
- **Vercel** — website hosting and request logs.
- **Stripe** — payments (only if/when enabled later).
- **Email provider** — _[NEEDS OWNER CONFIRMATION: which provider, if any]_.

## 5. Retention

Account data is retained while your account is active and deleted within _[30]_ days of
account deletion. Local data persists until you delete it or uninstall.

## 6. Deletion

Request deletion via account settings or the contact email. We delete account data from
Supabase and instruct processors to delete. *(End-to-end deletion path: NEEDS OWNER
CONFIRMATION it is wired before publishing.)*

## 7. Your rights

Access, correction, deletion, export, and objection as applicable under GDPR/CCPA.
*(Jurisdiction coverage: requires legal review.)*

## 8. Security

Passwords are scrypt-hashed and compared in constant time. Atlas's local-first design
minimizes server-side exposure of your code. This is **beta** software — see *Beta
limitations*. We make **no claim of any third-party security certification.**

## 9. Beta limitations

- Windows only; macOS/Linux not supported yet.
- The installer is **unsigned** in beta — Windows SmartScreen may warn.
- No third-party security certification.

## Verification status (for maintainers)

- Local-first / no code upload: **VERIFIED by inspection** (commit `69556ceeb`).
- scrypt password hashing: **VERIFIED**.
- Local-only analytics: **VERIFIED**.
- Support email / domain control: **NEEDS OWNER CONFIRMATION**.
- Vercel log retention, email provider, deletion wiring: **NEEDS OWNER CONFIRMATION**.
- Stripe/payments: **NOT ENABLED**.
