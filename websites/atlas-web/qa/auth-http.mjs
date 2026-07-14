import crypto from "node:crypto";
import assert from "node:assert/strict";

const base = process.env.ATLAS_QA_BASE_URL || "http://127.0.0.1:3031";
const secret = process.env.ATLAS_QA_AUTH_SECRET || "qa-only-stable-secret-with-more-than-32-bytes";
const password = "qa-password-2026";
const suffix = crypto.randomUUID().slice(0, 8);
const userEmail = `atlas-user-${suffix}@example.invalid`;
const adminEmail = "atlas-admin-qa@example.invalid";

function sessionCookie(response) {
  const setCookie = response.headers.get("set-cookie") || "";
  return setCookie.split(";", 1)[0];
}

async function json(path, { method = "GET", body, cookie } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    redirect: "manual",
  });
  const data = await response.json().catch(() => ({}));
  assert.match(response.headers.get("cache-control") || "", /no-store/);
  return { response, data, cookie: sessionCookie(response) };
}

function signedToken(sub, exp) {
  const payload = Buffer.from(JSON.stringify({ sub, exp })).toString("base64url");
  const signature = crypto.createHmac("sha256", secret).update(payload).digest("base64url");
  return `${payload}.${signature}`;
}

const signedOut = await json("/api/auth/session");
assert.equal(signedOut.response.status, 200);
assert.equal(signedOut.data.user, null);

const unauthorizedAdmin = await json("/api/admin/users");
assert.equal(unauthorizedAdmin.response.status, 403);

const registered = await json("/api/auth/register", {
  method: "POST",
  body: { email: userEmail, password },
});
assert.equal(registered.response.status, 201);
assert.ok(registered.cookie.startsWith("atlas_session="));
assert.equal(registered.data.user.email, userEmail);

const restored = await json("/api/auth/session", { cookie: registered.cookie });
assert.equal(restored.response.status, 200);
assert.equal(restored.data.user.email, userEmail);

const duplicate = await json("/api/auth/register", {
  method: "POST",
  body: { email: userEmail, password },
});
assert.equal(duplicate.response.status, 400);

const invalid = await json("/api/auth/login", {
  method: "POST",
  body: { email: userEmail, password: "incorrect-password" },
});
assert.equal(invalid.response.status, 401);
assert.equal(invalid.data.error, "Invalid email or password.");

const expired = signedToken(registered.data.user.id, Math.floor(Date.now() / 1000) - 60);
const expiredSession = await json("/api/auth/session", { cookie: `atlas_session=${expired}` });
assert.equal(expiredSession.response.status, 200);
assert.equal(expiredSession.data.user, null);

let admin = await json("/api/auth/register", {
  method: "POST",
  body: { email: adminEmail, password },
});
if (admin.response.status === 400) {
  admin = await json("/api/auth/login", { method: "POST", body: { email: adminEmail, password } });
}
assert.ok(admin.response.status === 200 || admin.response.status === 201);
const authorizedAdmin = await json("/api/admin/users", { cookie: admin.cookie });
assert.equal(authorizedAdmin.response.status, 200);
assert.ok(Array.isArray(authorizedAdmin.data.users));
assert.ok(authorizedAdmin.data.users.every((user) => !("passwordHash" in user)));

// Local file mode has no analytics backend; authorized access is proven before
// the route truthfully reports that aggregate analytics are unavailable.
const adminAnalytics = await json("/api/admin/analytics", { cookie: admin.cookie });
assert.equal(adminAnalytics.response.status, 503);
assert.equal(adminAnalytics.data.error, "account_service_unavailable");

const logout = await json("/api/auth/logout", { method: "POST", cookie: registered.cookie });
assert.equal(logout.response.status, 200);
assert.match(logout.response.headers.get("set-cookie") || "", /Max-Age=0/i);

console.log(JSON.stringify({
  signed_out: "PASS",
  signed_in_restore: "PASS",
  expired_session: "PASS",
  duplicate_email: "PASS",
  invalid_credentials: "PASS",
  unauthorized_admin: "PASS",
  authorized_admin: "PASS",
  local_analytics_unavailable: "PASS",
  logout_cookie_clear: "PASS",
}));
