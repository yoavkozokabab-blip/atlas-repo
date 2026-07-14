import type { Metadata, Viewport } from "next";
import { Space_Grotesk } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import AnalyticsClient from "./_components/AnalyticsClient";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const TITLE = "Atlas — Persistent repo memory for Claude Code, Cursor, and Codex";
const DESC =
  "Atlas indexes your repository locally into a dependency graph and evidence store, then serves it to Claude Code, Cursor, and Codex over MCP. Scans persist across fresh agent sessions and are validated against the live repo. Indexing never leaves your machine.";

export const metadata: Metadata = {
  metadataBase: new URL("https://atlas-repo-wu76.vercel.app"),
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
    url: "https://atlas-repo-wu76.vercel.app",
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
  themeColor: "#070908",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body>
        <a href="#main-content" className="skip-link">Skip to content</a>
        <AnalyticsClient />
        {children}
      </body>
    </html>
  );
}
