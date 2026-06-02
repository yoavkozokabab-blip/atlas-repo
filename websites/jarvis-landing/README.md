# JARVIS Landing Page

Premium Next.js landing page for JARVIS, the Personal AI Operating System.

## Stack

- Next.js App Router
- React + TypeScript
- CSS-only motion for low JavaScript overhead
- `next/image` optimized hero asset
- Small server route for waitlist submissions

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
app/api/waitlist/route.ts Waitlist POST endpoint
public/jarvis-hero.png    Generated hero background asset
```

## Design Notes

- Dark luxury palette with graphite, platinum, cyan, blue, green, and gold accents.
- Hero uses a generated bitmap asset with CSS overlays, not a gradient-only placeholder.
- Animations use transform and opacity, and respect `prefers-reduced-motion`.
- Cards use an 8px radius to keep the interface crisp and premium.
- Layout is responsive across desktop, tablet, and mobile.

## Waitlist

The waitlist endpoint validates email and appends JSONL records to:

```text
.waitlist/submissions.jsonl
```

For hosted production, connect `app/api/waitlist/route.ts` to your email platform,
CRM, database, or queue before launch.
