import type { Metadata, Viewport } from "next";
import "./globals.css";

const TITLE = "Atlas — Local-first repository intelligence for AI engineering";
const DESC =
  "Atlas maps your codebase locally into architecture, a dependency graph, risk and impact — then exports evidence-backed context so Claude, Codex and Cursor start with the structure instead of re-reading files. Your code never leaves your machine.";

export const metadata: Metadata = {
  metadataBase: new URL("https://atlas-repo-chi.vercel.app"),
  title: TITLE,
  description: DESC,
  applicationName: "Atlas",
  keywords: [
    "repository intelligence",
    "AI coding context",
    "dependency graph",
    "Claude",
    "Codex",
    "Cursor",
    "local-first developer tools"
  ],
  openGraph: {
    type: "website",
    url: "https://atlas-repo-chi.vercel.app",
    siteName: "Atlas",
    title: TITLE,
    description: DESC
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC
  },
  robots: { index: true, follow: true }
};

export const viewport: Viewport = {
  themeColor: "#0B0F14",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1
};

// Launch analytics stub: aggregate event names only (page_view, download_click,
// hn_page_view, pricing_view, pro_cta_click, docs_click). No repository data,
// no prompts, no personal data — just the event name and pathname. Entirely
// inert unless NEXT_PUBLIC_ANALYTICS_URL points at a collector endpoint.
const ANALYTICS_URL = process.env.NEXT_PUBLIC_ANALYTICS_URL || "";
const ANALYTICS_SNIPPET = `(function(){var u=${JSON.stringify(ANALYTICS_URL)};if(!u||!navigator.sendBeacon)return;var send=function(e){try{navigator.sendBeacon(u,JSON.stringify({event:e,path:location.pathname,ts:Date.now()}))}catch(_){}};send(location.pathname==="/hn"?"hn_page_view":location.pathname==="/pricing"?"pricing_view":"page_view");document.addEventListener("click",function(ev){var el=ev.target&&ev.target.closest&&ev.target.closest("[data-evt]");if(el)send(el.getAttribute("data-evt"))},true);})();`;

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {children}
        {ANALYTICS_URL ? (
          <script dangerouslySetInnerHTML={{ __html: ANALYTICS_SNIPPET }} />
        ) : null}
      </body>
    </html>
  );
}
