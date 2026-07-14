import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MESSAGE =
  "The latest Atlas desktop build is undergoing final installed-app verification. Downloads will reopen when the verified installer is ready.";

const HEADERS = {
  "Cache-Control": "no-store",
  "Retry-After": "3600",
};

export async function GET() {
  return NextResponse.json(
    {
      error: "installer_temporarily_unavailable",
      message: MESSAGE,
    },
    { status: 503, headers: HEADERS }
  );
}

export async function HEAD() {
  return new NextResponse(null, { status: 503, headers: HEADERS });
}
