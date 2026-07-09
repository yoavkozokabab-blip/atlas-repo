// Public, non-secret site configuration sourced from environment variables.
// The launch contact inbox is intentionally visible across public surfaces.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "yoavkozokabab@gmail.com";
export const HELLO_EMAIL = process.env.NEXT_PUBLIC_HELLO_EMAIL || "yoavkozokabab@gmail.com";
export const SECURITY_EMAIL = process.env.NEXT_PUBLIC_SECURITY_EMAIL || "yoavkozokabab@gmail.com";
export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/useatlas";
export const DOWNLOAD_URL =
  process.env.NEXT_PUBLIC_DOWNLOAD_URL ||
  process.env.ATLAS_INSTALLER_URL ||
  "/download/atlas";

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
