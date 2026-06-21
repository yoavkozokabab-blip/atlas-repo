# Atlas Button / Link Audit

**Date:** 2026-06-20 · Every visible button/link, classified. Crawled rendered HTML + cross-referenced handlers in `app/_components/client.tsx` and `_components/site.tsx`. **No live Vercel URL** — audited the deployed code locally.

Legend: **Works** · **Broken** · **Misleading** · **Placeholder** · **Disabled (intentional)** · **Unknown**

## Header (nav, every page)
| Element | Target / action | Class |
|---|---|---|
| Sign in | `/login` | Works |
| Download / Download for Windows | `/download` | Works |
| (nav) Features/Pricing/Docs/FAQ/Contact | `/features` `/pricing` `/docs` `/faq` `/contact` | Works (all 200) |

## Hero
| Element | Target | Class |
|---|---|---|
| Download | `/download` | Works |
| See it work | `#see-it-work` | Works (anchor id exists on page) |
| (waitlist) Join | `#waitlist` | Works (anchor id exists; `WaitlistForm` present) |

## Pricing (teaser + /pricing)
| Element | Target | Class |
|---|---|---|
| Download free / Download | `/download` | Works |
| Join the beta | `/download` | Works |
| Contact sales (Team) | `/contact` | Works |
| ~~Start 7-day trial / $29~~ | — | **Not rendered** (paid hidden via `PAID_PLANS_ENABLED` off) — correctly absent |

## Download page
| Element | Target / action | Class |
|---|---|---|
| Create a free account to download (anon) | `/login?next=/download` | Works (login-gated by design) |
| Download (authed) | `/download/atlas` → 302 `ATLAS_INSTALLER_URL` | Works if URL set; **Disabled/degraded** ("No installer available") if unset — honest |

## Login / signup form (`client.tsx`)
| Element | Action | Class |
|---|---|---|
| Sign in / Create account (submit) | `POST /api/auth/login`/`register` | Works (surfaces errors, disables while busy) |
| Forgot password | `POST /api/auth/forgot` | Works (always generic response — anti-enumeration) |
| Mode toggle (login/signup) | local state | Works |

## Account / billing
| Element | Action | Class |
|---|---|---|
| Logout | `POST /api/auth/logout` → `/` | Works |
| Download Atlas (account) | `/account/downloads` | Works |
| Billing (free beta) | shows "Free beta — nothing will ever be charged" | Works (no checkout button rendered) |
| `CheckoutButton` / `ManageBillingButton` / cancel/renew | `/api/checkout` etc. | **Not reachable in free beta** (account/billing renders the free-beta branch; `/checkout/plan/*` redirects to `/pricing`). If it were reached, `/api/checkout`→403 and the button would no-op — but it is intentionally not rendered. |

## Footer (every page)
| Element | Target | Class |
|---|---|---|
| Features/Pricing/Docs/FAQ/Contact/Privacy/Terms/Download | `/features` … `/terms` | Works (all 200) |
| Support email (mailto) | `mailto:<NEXT_PUBLIC_SUPPORT_EMAIL>` | Works **iff the env email is correct** — currently a personal Gmail whose spelling differs from the owner's known address (see QA #1). Verify before launch. |

## Contact page
| Element | Target | Class |
|---|---|---|
| Support / Billing / Security / Feedback / Partnerships / macOS-Linux | `mailto:<support>?subject=…` | Works (depends on correct env email) |

## Summary
- **Broken:** 0 · **Misleading:** 0 · **Placeholder/dead (`href="#"`):** 0 (grep confirmed none) · **Fake UI:** 0.
- **Conditional:** download asset link (degrades honestly if `ATLAS_INSTALLER_URL` unset); all `mailto:` links depend on a correct `NEXT_PUBLIC_SUPPORT_EMAIL`.
- **Intentionally absent:** all paid/checkout buttons (free beta).
- **Verdict:** the button/link surface is clean and honest. The only real risk is the **support email value** (env/config), not a code defect.
