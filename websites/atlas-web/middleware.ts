import { NextRequest, NextResponse } from "next/server";

const CANONICAL_ORIGIN = "https://atlas-repo-wu76.vercel.app";
const DOWNLOAD_MESSAGE =
  "The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready.";

const INERT_HEADERS = {
  "Cache-Control": "no-store",
  "X-Atlas-Legacy-Project": "inert",
};

export function middleware(request: NextRequest) {
  if (process.env.ATLAS_LEGACY_PROJECT_MODE !== "true") {
    return NextResponse.next();
  }

  const { pathname, search } = request.nextUrl;

  if (pathname === "/download/atlas") {
    if (request.method === "HEAD") {
      return new NextResponse(null, {
        status: 503,
        headers: { ...INERT_HEADERS, "Retry-After": "3600" },
      });
    }
    return NextResponse.json(
      {
        error: "installer_temporarily_unavailable",
        message: DOWNLOAD_MESSAGE,
      },
      {
        status: 503,
        headers: { ...INERT_HEADERS, "Retry-After": "3600" },
      }
    );
  }

  if (pathname.startsWith("/api/") || !["GET", "HEAD"].includes(request.method)) {
    return NextResponse.json(
      {
        error: "legacy_project_retired",
        message: "This legacy Atlas endpoint is disabled. Use the canonical Atlas website.",
        canonical: CANONICAL_ORIGIN,
      },
      { status: 410, headers: INERT_HEADERS }
    );
  }

  return NextResponse.redirect(new URL(`${pathname}${search}`, CANONICAL_ORIGIN), 308);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
