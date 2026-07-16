// Public, non-secret site configuration sourced from environment variables.
// The launch contact inbox is intentionally visible across public surfaces.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "yoavkozokabab@gmail.com";
export const HELLO_EMAIL = process.env.NEXT_PUBLIC_HELLO_EMAIL || "yoavkozokabab@gmail.com";
export const SECURITY_EMAIL = process.env.NEXT_PUBLIC_SECURITY_EMAIL || "yoavkozokabab@gmail.com";
export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yoavkozokabab-blip/atlas-repo";
export const GITHUB_RELEASE_URL =
  process.env.NEXT_PUBLIC_GITHUB_RELEASE_URL || `${GITHUB_URL}/releases/tag/v1.0.4`;
/** SHA256 of the published Atlas_Setup.exe — shown on /hn and /download. */
export const INSTALLER_SHA256 =
  process.env.NEXT_PUBLIC_INSTALLER_SHA256 ||
  "2A1EAA9EEC99311E44496DA04157AD1DB1F60C4373ECD5FFB33D52127CDFFF8A";
export const DOWNLOAD_URL =
  process.env.NEXT_PUBLIC_DOWNLOAD_URL ||
  process.env.ATLAS_INSTALLER_URL ||
  "https://github.com/yoavkozokabab-blip/atlas-repo/releases/download/v1.0.4/Atlas_Setup.exe";

/**
 * Paid plans are deliberately suspended for the v1.0.5 launch candidate.
 * This is a source-level safety interlock: no production environment variable
 * can make a checkout CTA live until a separately reviewed billing release
 * changes this constant and proves the corresponding lifecycle gates.
 */
export const PAID_PLANS_ENABLED = false;

/** Returns a mailto: link for the configured support email, or /contact if unset. */
export function supportMailto(subject?: string): string {
  if (!SUPPORT_EMAIL) return "/contact";
  const q = subject ? `?subject=${encodeURIComponent(subject)}` : "";
  return `mailto:${SUPPORT_EMAIL}${q}`;
}
