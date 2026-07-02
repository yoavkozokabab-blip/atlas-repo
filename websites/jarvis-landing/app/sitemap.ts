import type { MetadataRoute } from "next";

const BASE = "https://useatlas.dev";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const pages: Array<[path: string, priority: number]> = [
    ["/", 1],
    ["/features", 0.9],
    ["/download", 0.9],
    ["/docs", 0.8],
    ["/pricing", 0.7],
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
