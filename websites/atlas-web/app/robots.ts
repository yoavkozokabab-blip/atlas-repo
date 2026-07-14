import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Account, admin and API surfaces are private/no-value for crawlers.
        disallow: ["/account", "/admin", "/api/", "/billing/", "/checkout/"],
      },
    ],
    sitemap: `${(process.env.NEXT_PUBLIC_APP_URL || "https://atlas-repo-wu76.vercel.app").replace(/\/+$/, "")}/sitemap.xml`,
  };
}
