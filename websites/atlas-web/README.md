# Atlas Website

Next.js website for Atlas, local-first memory and context for AI coding agents.

## Stack

- Next.js App Router
- React + TypeScript
- CSS-only motion for low JavaScript overhead
- `next/image` optimized hero asset
- Persisted account, email update, analytics, and download routes

## Run Locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Production Build

```bash
npm run build
npm run start
```

## Structure

```text
app/page.tsx              Landing page sections
app/globals.css           Visual system, layout, animation, responsiveness
app/api/.../route.ts      Account, signup, analytics, and download endpoints
```

## Design Notes

- Dark luxury palette with graphite, platinum, cyan, blue, green, and gold accents.
- Hero uses a generated bitmap asset with CSS overlays, not a gradient-only placeholder.
- Animations use transform and opacity, and respect `prefers-reduced-motion`.
- Cards use an 8px radius to keep the interface crisp and premium.
- Layout is responsive across desktop, tablet, and mobile.

## Email Signups

The signup endpoint validates email and writes through the shared store. Production
uses Supabase; local development uses an isolated JSON file under:

```text
.data/atlas-web.json
```

See `docs/SUPABASE_SETUP.md` for schema, environment, and verification steps. Production
refuses local-file writes so a missing Supabase configuration cannot silently lose signups.
