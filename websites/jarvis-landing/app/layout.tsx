import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SiteAnalytics } from "./_components/site-analytics";

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

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SiteAnalytics />
        {children}
      </body>
    </html>
  );
}
