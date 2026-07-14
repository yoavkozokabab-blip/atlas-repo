import type { MetadataRoute } from "next";

const BASE = (process.env.NEXT_PUBLIC_APP_URL || "https://atlas-repo-wu76.vercel.app").replace(/\/+$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const pages: Array<[path: string, priority: number]> = [
    ["/", 1],
    ["/hn", 0.9],
    ["/features", 0.9],
    ["/download", 0.9],
    ["/docs", 0.8],
    ["/pricing", 0.7],
    ["/compare", 0.7],
    ["/benchmarks", 0.6],
    ["/changelog", 0.6],
    ["/roadmap", 0.6],
    ["/faq", 0.6],
    ["/contact", 0.5],
    ["/security", 0.4],
    ["/privacy", 0.3],
    ["/terms", 0.3],
    ["/eula", 0.2],
    ["/refund", 0.2],
    ["/cancellation", 0.2],
  ];
  return pages.map(([path, priority]) => ({
    url: `${BASE}${path}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority,
  }));
}
