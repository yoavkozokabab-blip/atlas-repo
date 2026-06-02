import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://jarvis.local"),
  title: "JARVIS - Personal AI Operating System",
  description:
    "A premium personal AI operating system for voice, tools, research, memory, and automation.",
  openGraph: {
    title: "JARVIS - Personal AI Operating System",
    description:
      "Voice-native intelligence, local tools, durable memory, and automation in one elegant operating layer.",
    images: [
      {
        url: "/jarvis-hero.png",
        width: 1536,
        height: 864,
        alt: "Futuristic JARVIS AI operating system interface"
      }
    ]
  }
};

export const viewport: Viewport = {
  themeColor: "#050608",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
