import { ENV } from "./config";
import { privateJson } from "./http";

/**
 * Reject cross-site browser writes before reading a cookie-authenticated body.
 * Requests without browser fetch metadata are permitted for controlled native
 * clients and server-to-server jobs; browser requests must prove the canonical
 * application origin through Origin or Referer.
 */
export function isTrustedBrowserWrite(req: Request): boolean {
  const expected = new URL(ENV.appUrl).origin;
  const origin = req.headers.get("origin");
  if (origin) return origin === expected;
  const referer = req.headers.get("referer");
  if (referer) {
    try {
      return new URL(referer).origin === expected;
    } catch {
      return false;
    }
  }
  // Browser fetch metadata makes a missing Origin/Referer suspicious. Direct
  // native/server requests have neither and are authenticated separately.
  return !req.headers.has("sec-fetch-site");
}

export function csrfRejected() {
  return privateJson({ ok: false, error: "origin_validation_failed" }, { status: 403 });
}
