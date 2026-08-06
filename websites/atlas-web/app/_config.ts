// Public, non-secret site configuration sourced from environment variables.
// The launch contact inbox is intentionally visible across public surfaces.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "yoavkozokabab@gmail.com";
export const HELLO_EMAIL = process.env.NEXT_PUBLIC_HELLO_EMAIL || "yoavkozokabab@gmail.com";
export const SECURITY_EMAIL = process.env.NEXT_PUBLIC_SECURITY_EMAIL || "yoavkozokabab@gmail.com";
export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yoavkozokabab-blip/atlas-repo";

/**
 * THE single source of truth for the published Windows artifact.
 *
 * Version, tag, filename, download URL, checksum and byte size must always
 * describe ONE file. They previously lived in four places and drifted: the
 * page showed one version while the redirect served an older release, the
 * checksum belonged to that older release, and the size was a hardcoded
 * literal matching neither. Every download surface now reads this object.
 *
 * When cutting a release, change `version`/`tag` and paste the values the
 * installer build printed into `sha256`/`sizeBytes`. `release-config.test.mjs`
 * fails if they are left at the placeholder, if they disagree with each other,
 * or if a retired version string reappears anywhere.
 */
const RELEASE_VERSION = "1.0.6-beta.1";
const RELEASE_TAG = `v${RELEASE_VERSION}`;
const RELEASE_FILENAME = `Atlas-Setup-${RELEASE_VERSION}.exe`;

export const CURRENT_WINDOWS_RELEASE = {
  version: RELEASE_VERSION,
  tag: RELEASE_TAG,
  filename: RELEASE_FILENAME,
  downloadUrl:
    process.env.NEXT_PUBLIC_DOWNLOAD_URL ||
    process.env.ATLAS_INSTALLER_URL ||
    `${GITHUB_URL}/releases/download/${RELEASE_TAG}/${RELEASE_FILENAME}`,
  releaseUrl: process.env.NEXT_PUBLIC_GITHUB_RELEASE_URL || `${GITHUB_URL}/releases/tag/${RELEASE_TAG}`,
  // Sentinels, not plausible values. A wrong-but-realistic hash is precisely
  // the defect this object exists to prevent, so an unfilled release fails
  // loudly in the gate instead of shipping a checksum that verifies nothing.
  sha256: (process.env.NEXT_PUBLIC_INSTALLER_SHA256 || "PENDING_RELEASE_BUILD").toUpperCase(),
  sizeBytes: Number(process.env.NEXT_PUBLIC_INSTALLER_SIZE_BYTES || 0),
  /** Windows-only, unsigned. Stated on every download surface — do not drop. */
  platform: "Windows",
  signed: false,
} as const;

/** Human-readable size derived from bytes. Never hardcode a size string. */
export function releaseSizeLabel(bytes: number = CURRENT_WINDOWS_RELEASE.sizeBytes): string {
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

// Legacy names kept so existing imports keep working. All derive from the
// single object above — none of them may be assigned independently.
export const GITHUB_RELEASE_URL = CURRENT_WINDOWS_RELEASE.releaseUrl;
/** SHA256 of the published installer — shown on /hn and /download. */
export const INSTALLER_SHA256 = CURRENT_WINDOWS_RELEASE.sha256;
export const DOWNLOAD_URL = CURRENT_WINDOWS_RELEASE.downloadUrl;

/**
 * Paid plans are deliberately suspended for the beta.
 * This is a source-level safety interlock: no production environment variable
 * can make a checkout CTA live until a separately reviewed billing release
 * changes this constant and proves the corresponding lifecycle gates.
 */
export const PAID_PLANS_ENABLED = false;

/**
 * Repository Q&A is disabled in the shipping desktop build
 * (`release-manifest` ask_enabled=false), so it is not included in this beta.
 * The site must not advertise it while that is true — see /pricing and /docs.
 */
export const ASK_ENABLED = false;

/** Returns a mailto: link for the configured support email, or /contact if unset. */
export function supportMailto(subject?: string): string {
  if (!SUPPORT_EMAIL) return "/contact";
  const q = subject ? `?subject=${encodeURIComponent(subject)}` : "";
  return `mailto:${SUPPORT_EMAIL}${q}`;
}
