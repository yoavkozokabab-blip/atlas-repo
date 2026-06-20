// Public, non-secret site configuration sourced from environment variables.
// The support email is intentionally NOT hardcoded in source — set
// NEXT_PUBLIC_SUPPORT_EMAIL in .env.local (gitignored) for local dev and in your
// host's environment for production. See .env.example.
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "";

/**
 * Paid plans visibility (Phase 186A free-beta).
 * OFF by default → the site shows an honest free-invite-beta with NO checkout,
 * no prices to pay, and no fake trial. Flip to "1" (NEXT_PUBLIC_PAID_PLANS=1)
 * only once real Stripe billing is wired and you intend to charge.
 */
export const PAID_PLANS_ENABLED = process.env.NEXT_PUBLIC_PAID_PLANS === "1";

/** Returns a mailto: link for the configured support email, or /contact if unset. */
export function supportMailto(subject?: string): string {
  if (!SUPPORT_EMAIL) return "/contact";
  const q = subject ? `?subject=${encodeURIComponent(subject)}` : "";
  return `mailto:${SUPPORT_EMAIL}${q}`;
}
