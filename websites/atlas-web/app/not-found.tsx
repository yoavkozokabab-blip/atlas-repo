import Link from "next/link";
import InstallerWaitState from "./_components/InstallerWaitState";
import { SiteNav, SiteFooter } from "./_components/site";

// App Router 404 page. Providing this (plus global-error.tsx) makes Next render
// the 404/500 through the App Router instead of the legacy Pages-Router error
// pages, which pulled in the old document module and broke prerendering on a
// clean Vercel build.
export const metadata = {
  title: "Page not found — Atlas",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <>
      <SiteNav />
      <main>
        <section className="page-head">
          <div className="container">
            <p className="eyebrow">404</p>
            <h1 className="page-title">Page not found</h1>
            <p className="lead" style={{ marginTop: 18 }}>
              The page you&apos;re looking for doesn&apos;t exist or has moved.
            </p>
            <div style={{ marginTop: 26, display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Link className="btn btn-primary" href="/">Back to home</Link>
              <InstallerWaitState />
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
