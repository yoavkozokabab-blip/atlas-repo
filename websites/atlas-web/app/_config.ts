// Public, non-secret site configuration sourced from environment variables.
// The support email is sourced from NEXT_PUBLIC_SUPPORT_EMAIL (set it in
// .env.local for local dev and in your host's environment for production). A
// neutral shared support address is used as the fallback so we never expose a
// maintainer's personal inbox. See .env.example.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@useatlas.dev";
export const HELLO_EMAIL = process.env.NEXT_PUBLIC_HELLO_EMAIL || "hello@useatlas.dev";
export const SECURITY_EMAIL = process.env.NEXT_PUBLIC_SECURITY_EMAIL || "security@useatlas.dev";
export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/useatlas";

/**
 * Paid plan visibility.
 * ON by default for the launch pricing page: Free is available, Pro shows its
 * 7-day trial, and Team remains contact-only. Set NEXT_PUBLIC_PAID_PLANS=0 only
 * for local demos that should hide checkout actions. Live payments still require
 * the server-side Paddle path to be deliberately wired.
 */
export const PAID_PLANS_ENABLED = process.env.NEXT_PUBLIC_PAID_PLANS !== "0";

/** Returns a mailto: link for the configured support email, or /contact if unset. */
export function supportMailto(subject?: string): string {
  if (!SUPPORT_EMAIL) return "/contact";
  const q = subject ? `?subject=${encodeURIComponent(subject)}` : "";
  return `mailto:${SUPPORT_EMAIL}${q}`;
}
