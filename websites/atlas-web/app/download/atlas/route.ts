import { NextResponse } from "next/server";
import { createReadStream, existsSync, statSync } from "node:fs";
import { Readable } from "node:stream";
import path from "node:path";
import { currentUser } from "@/app/_lib/auth";
import { store, newId } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Delivers the real Atlas Windows installer.
 *
 * Production (serverless): set ATLAS_INSTALLER_URL to a stable hosted asset
 * (GitHub Release / Supabase Storage / CDN). The route 302-redirects there — a
 * 42 MB binary is never streamed through the serverless function. See
 * docs/RELEASE_PROCESS.md.
 *
 * Local dev: if ATLAS_INSTALLER_PATH or a built repo artifact exists, the file is
 * streamed directly so the Download button works end-to-end without hosting.
 */
function resolveLocalInstaller(): string | null {
  const env = process.env.ATLAS_INSTALLER_PATH;
  if (env && existsSync(env)) return env;
  const candidates = [
    path.join(process.cwd(), "..", "..", "packaging", "installer", "output", "Atlas_Setup.exe"),
    path.join(process.cwd(), "..", "..", "installer", "output", "Atlas_Setup.exe"),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

async function recordDownload(userId: string, email: string, downloads: number): Promise<void> {
  await store.update(userId, { downloads: (downloads || 0) + 1 });
  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: userId,
    actorEmail: email,
    action: "download_installer",
  });
}

export async function GET(req: Request) {
  // Login-gated: anonymous users are sent to sign in, preserving intent.
  const user = await currentUser();
  if (!user) {
    return NextResponse.redirect(new URL("/login?next=/download", req.url), 302);
  }

  // Production: redirect to the hosted artifact (stable, versioned, CDN-friendly).
  const hostedUrl = process.env.ATLAS_INSTALLER_URL;
  if (hostedUrl) {
    await recordDownload(user.id, user.email, user.downloads);
    return NextResponse.redirect(hostedUrl, 302);
  }

  // Dev fallback: stream a locally built installer.
  const file = resolveLocalInstaller();
  if (!file) {
    return NextResponse.json(
      {
        error: "installer_unavailable",
        message:
          "No installer available. Set ATLAS_INSTALLER_URL to the hosted release asset (production), " +
          "or build one with packaging/pyinstaller/build_atlas_exe.ps1 / set ATLAS_INSTALLER_PATH (local).",
      },
      { status: 404 }
    );
  }
  await recordDownload(user.id, user.email, user.downloads);

  const size = statSync(file).size;
  const webStream = Readable.toWeb(createReadStream(file)) as ReadableStream;
  return new NextResponse(webStream, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": 'attachment; filename="Atlas_Setup.exe"',
      "Content-Length": String(size),
      "Cache-Control": "no-store",
    },
  });
}
