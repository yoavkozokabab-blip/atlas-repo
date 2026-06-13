# Atlas Live Launch Checklist

Generated: 2026-06-13

## Before Sharing A Paid Link

- [ ] Production health OK
- [ ] Admin login OK
- [ ] Waitlist insert OK
- [ ] Checkout OK
- [ ] Webhook OK
- [ ] License OK
- [ ] Desktop installer hash verified
- [ ] Support email ready
- [ ] Refund/cancel process known
- [ ] `local_jarvis/.env` removed from git history or exposure accepted and secrets rotated
- [ ] `SITE_URL` set to HTTPS production URL
- [ ] `PAYMENTS_MODE=live`
- [ ] Stripe live secret key starts with `sk_live_`
- [ ] Stripe webhook secret starts with `whsec_`
- [ ] Stripe live price id starts with `price_`
- [ ] Stripe live product id starts with `prod_`

## For Every User

Track:
- source
- email
- signup status
- payment status
- license status
- feedback status
- device count
- last seen
- support notes

## Emergency

- Disable checkout: set `PAYMENTS_MODE=disabled` and redeploy
- Suspend user: accounts admin status `suspended`
- Cancel paid access manually: license status `canceled`
- Revoke device: accounts admin revoke device action
- Force logout: accounts admin force logout action
- Rotate Stripe webhook secret in Stripe and Vercel env
- Rotate `ADMIN_API_SECRET`
- Rotate Supabase service role key
- Rotate Stripe secret key if exposed
- Roll back Vercel deployment

