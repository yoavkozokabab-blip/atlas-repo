// Public, non-secret site configuration sourced from environment variables.
// The support email is sourced from NEXT_PUBLIC_SUPPORT_EMAIL (set it in
// .env.local for local dev and in your host's environment for production). A
// neutral shared support address is used as the fallback so we never expose a
// maintainer's personal inbox. See .env.example.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "atlas.repo.support@gmail.com";

/**
 * Paid plans visibility.
 * OFF by default → the site shows free download copy with no checkout,
 * no prices to pay and no fake trial. Flip to "1" (NEXT_PUBLIC_PAID_PLANS=1)
 * only once real Stripe billing is wired and you intend to charge.
 */
export const PAID_PLANS_ENABLED = process.env.NEXT_PUBLIC_PAID_PLANS === "1";

/** Returns a mailto: link for the configured support email, or /contact if unset. */
export function supportMailto(subject?: string): string {
  if (!SUPPORT_EMAIL) return "/contact";
  const q = subject ? `?subject=${encodeURIComponent(subject)}` : "";
  return `mailto:${SUPPORT_EMAIL}${q}`;
}
