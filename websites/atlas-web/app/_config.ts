// Public, non-secret site configuration sourced from environment variables.
// The launch contact inbox is intentionally visible across public surfaces.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "yoavkozokabab@gmail.com";
export const HELLO_EMAIL = process.env.NEXT_PUBLIC_HELLO_EMAIL || "yoavkozokabab@gmail.com";
export const SECURITY_EMAIL = process.env.NEXT_PUBLIC_SECURITY_EMAIL || "yoavkozokabab@gmail.com";
export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yoavkozokabab-blip/atlas-repo";
export const GITHUB_RELEASE_URL =
  process.env.NEXT_PUBLIC_GITHUB_RELEASE_URL || `${GITHUB_URL}/releases/tag/v1.0.3`;
/** SHA256 of the published Atlas_Setup.exe — shown on /hn and /download. */
export const INSTALLER_SHA256 =
  process.env.NEXT_PUBLIC_INSTALLER_SHA256 ||
  "93E1EB1F08B39BEB4CFE7A10529D522BFA973EBE124C6C4BAC1952BD13EB1888";
export const DOWNLOAD_URL =
  process.env.NEXT_PUBLIC_DOWNLOAD_URL ||
  process.env.ATLAS_INSTALLER_URL ||
  "https://github.com/yoavkozokabab-blip/atlas-repo/releases/download/v1.0.3/Atlas_Setup.exe";

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
