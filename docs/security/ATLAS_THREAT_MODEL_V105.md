# Atlas v1.0.5 threat model

**Status:** implementation baseline, 2026-07-17. This document describes
defense in depth, not a claim that Atlas cannot be compromised. Security
controls are release gates only when the referenced test or installed-artifact
evidence exists.

## Assets and trust boundaries

| Asset | Primary boundary | Required protection |
|---|---|---|
| Repository source, paths, graph, and scan cache | Desktop UI ↔ loopback API ↔ filesystem | Loopback-only service, origin/host checks, canonical path containment, bounded reads, no code execution |
| Accounts, sessions, entitlements, and admin data | Browser/desktop ↔ website API ↔ Supabase | Server-side identity, short-lived signed credentials, CSRF/origin checks, ownership and role checks, RLS/service-role isolation |
| Analytics | Browser/desktop ↔ ingestion ↔ Supabase | Event/property allowlists, payload/rate bounds, idempotency, no raw IP or repository data |
| MCP configuration and requests | MCP client ↔ stdio server ↔ active repository | JSON-RPC/schema limits, path containment, session isolation, bounded responses, stderr-only diagnostics |
| Future Paddle identifiers and subscription state | Website ↔ provider ↔ webhook ↔ entitlement state | Disabled-by-default provider, verified raw-body webhook, replay ledger, ordered authoritative state transitions |
| Installer, update metadata, and build outputs | Build system ↔ GitHub/Vercel ↔ end-user | Clean provenance, embedded commit, SHA-256, artifact inventory, future code signing and authenticated update manifest |

## Threat register

| Threat actor / path | Likelihood | Impact | Mitigation and verification | Remaining risk |
|---|---:|---:|---|---|
| Remote unauthenticated attacker probes website APIs | Medium | High | Route inventory, strict input/body bounds, rate limits, generic auth errors, security headers and negative API tests | Availability attacks and hosting-layer abuse remain possible |
| Credential stuffing or session theft | Medium | High | Scrypt passwords, HttpOnly/Secure/SameSite cookies, login rate limits, session rotation/invalidation, no URL tokens | User endpoint compromise and phishing cannot be eliminated |
| Cookie-authenticated cross-site request | Medium | High | Origin/referer CSRF gate on every state-changing website route; no credentialed wildcard CORS | Older browsers or missing headers require conservative rejection |
| Authenticated user attempts IDOR/admin escalation | Medium | High | Server-derived identity, `requireAdmin`, ownership checks, no client role/plan input, RLS and negative tests | A compromised admin account retains authorized power |
| Malicious webpage targets localhost / DNS rebinding | Medium | Critical | Bind loopback only, strict Host+Origin equality, no wildcard CORS, runtime token for privileged API calls, hostile-origin tests | Malicious local processes share the host trust boundary |
| Attacker-controlled repository abuses scan | High | High | Canonical root checks, symlink/junction policy, file/depth/time/size bounds, no imports/scripts, sanitized display text, malicious fixtures | TOCTOU and platform filesystem edge cases need installed-platform testing |
| Command injection via paths/config/client input | Medium | High | No shell interpolation, argument arrays, validated executable/argument allowlists, bounded subprocess output/timeouts | Trusted user-installed agent binaries remain a supply-chain dependency |
| Malformed or hostile MCP client | Medium | High | Strict JSON-RPC limits/method allowlist, active-repository-only access, session cleanup, fuzz tests, no client identity authorization | Local clients can still request capabilities intentionally exposed to them |
| Analytics exfiltration or ingestion abuse | Medium | Medium | Allowlisted names/properties, caps, rate limit, idempotency, local opt-out, server-derived user identity | Aggregate metadata can still reveal product usage patterns |
| Compromised dependency/build artifact | Medium | Critical | Lockfiles, audits, SBOM/provenance, clean detached builds, artifact hash and installer content audits | No substitute for signing and vendor response processes |
| Modified installer/reverse engineering | High | High | No embedded secrets, minimal package, integrity diagnostics, future code signing and authenticated update manifest | Local desktop software cannot be made reverse-engineering-proof |
| Free-plan bypass/reinstall/clock changes | High | Medium | Server-authoritative account quotas, signed bounded offline cache, installation identity, anti-replay checks | Offline/guest limits can only be made harder, not piracy-proof |
| Webhook replay/out-of-order provider event | Medium | Critical | Disabled provider now; future signature/timestamp verification, idempotency ledger, monotonic entitlement state machine | Provider delivery and reconciliation outages require operational response |

## Control mapping

| Control family | Atlas controls | OWASP reference |
|---|---|---|
| Authentication/session | Password KDF, generic errors, rate limits, secure cookie, rotation, invalidation | ASVS V2, V3; Desktop App Security: authentication/credential storage |
| Authorization | Server identity, owner checks, admin gate, RLS, entitlement service | ASVS V4; Desktop App Security: authorization |
| Input/API | Schemas, content type/body/depth limits, stable errors, output encoding | ASVS V5, V13; Desktop App Security: input validation |
| Browser | CSP, anti-framing, HSTS, CSRF, CORS/origin validation | ASVS V3, V14; Desktop App Security: webview/network exposure |
| Files/processes | Path containment, scan bounds, no repository execution, argument-array subprocesses | ASVS V5, V12; Desktop App Security: filesystem/process execution |
| Data/privacy | RLS, grants, service-role isolation, analytics minimization/retention | ASVS V8, V9; Desktop App Security: data protection |
| Supply chain/release | Dependency audit, clean build provenance, hashes, signing roadmap | ASVS V10, V14; Desktop App Security: update/code integrity |

## Explicit non-go claims

- Atlas does **not** claim repository scanning is safe against every kernel or
  filesystem exploit; it prevents the application-level attacks listed here.
- Atlas does **not** claim local binaries, guest quotas, or obfuscation are
  piracy-proof.
- Atlas does **not** enable or trust Paddle checkout redirects. A verified
  webhook/reconciliation path is required before any paid entitlement.
- A release remains blocked until the installed artifact, migration sandbox,
  headers, and hostile-origin evidence match the committed implementation.
