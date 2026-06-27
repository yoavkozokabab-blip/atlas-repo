# Atlas Website

Next.js website for Atlas, local-first memory and context for AI coding agents.

## Stack

- Next.js App Router
- React + TypeScript
- CSS-only motion for low JavaScript overhead
- `next/image` optimized hero asset
- Small server route for email update signups

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
app/api/.../route.ts      Email signup POST endpoint
public/jarvis-hero.png    Generated hero background asset
```

## Design Notes

- Dark luxury palette with graphite, platinum, cyan, blue, green, and gold accents.
- Hero uses a generated bitmap asset with CSS overlays, not a gradient-only placeholder.
- Animations use transform and opacity, and respect `prefers-reduced-motion`.
- Cards use an 8px radius to keep the interface crisp and premium.
- Layout is responsive across desktop, tablet, and mobile.

## Email Signups

The signup endpoint validates email and appends JSONL records to:

```text
.email-signups/submissions.jsonl
```

For hosted production, connect the signup route to your email platform,
CRM, database, or queue before launch.
