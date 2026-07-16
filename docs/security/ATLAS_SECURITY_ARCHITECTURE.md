# Atlas security architecture v1.0.5

## Authority model

- The website derives the acting account from a signed HttpOnly session or a
  desktop bearer credential. Request bodies never select a user, role, or
  entitlement.
- Admin authorization is server-side. Browser JavaScript may render state but
  is not an authority boundary.
- Supabase service-role access is limited to server routes. Browser roles have
  no raw analytics access; RLS and grants must remain restrictive.
- The desktop UI talks only to its active loopback runtime. The runtime is not
  a LAN service and must reject untrusted Host/Origin combinations.
- Repository contents are untrusted input, never executable configuration.

## Website route inventory standard

Every route is recorded and tested with: method, authentication/role,
ownership constraint, rate-limit key, accepted schema, response schema, and
sensitive fields. Sensitive routes include auth, account deletion, admin,
analytics administration, checkout/billing, desktop bearer auth, and webhook
processing. A route without an explicit owner/role rule is treated as public
read-only or is a defect.

## Security headers baseline

The v1.0.5 website target is an enforced, explicit CSP with no `unsafe-eval`,
anti-framing through `frame-ancestors 'none'`, `nosniff`, strict referrer and
permissions policies, HSTS in production, and compatible COOP/CORP headers.
Paddle origins are absent while billing is disabled. Header verification must
run against preview before production deployment.

## Entitlement authority

The entitlement service is the single policy source. It returns only safe
feature state (`plan`, `limit`, `used`, `remaining`, `reset_at`, source, and
last-sync time). A website/desktop client cannot self-declare Pro. Offline
state may preserve bounded Free functionality but must fail closed for paid
features.

## Local service authority

Local API calls require loopback peer, exact loopback Host and Origin, and the
current runtime authority. Privileged state-changing calls additionally need a
per-runtime capability token delivered only to the trusted desktop surface.
The implementation must not use wildcard CORS, bind `0.0.0.0`, or accept
external Host headers.
