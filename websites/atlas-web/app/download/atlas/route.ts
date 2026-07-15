import { NextResponse } from "next/server";
import { createReadStream, existsSync, statSync } from "node:fs";
import { Readable } from "node:stream";
import path from "node:path";
import { currentUser } from "@/app/_lib/auth";
import { DOWNLOAD_URL } from "@/app/_config";
import { store, newId } from "@/app/_lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function resolveLocalInstaller(): string | null {
  const env = process.env.ATLAS_INSTALLER_PATH;
  if (env && existsSync(env)) return env;
  const candidates = [
    path.join(process.cwd(), "..", "..", "packaging", "installer", "output", "Atlas_Setup.exe"),
    path.join(process.cwd(), "..", "..", "installer", "output", "Atlas_Setup.exe"),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

async function recordDownloadIfSignedIn(): Promise<void> {
  const user = await currentUser();
  if (!user) return;
  await store.update(user.id, { downloads: (user.downloads || 0) + 1 });
  await store.audit({
    id: newId(),
    at: new Date().toISOString(),
    actorId: user.id,
    actorEmail: user.email,
    action: "download_installer",
  });
}

export async function GET() {
  const hostedUrl =
    process.env.ATLAS_INSTALLER_URL ||
    (DOWNLOAD_URL && DOWNLOAD_URL !== "/download/atlas" ? DOWNLOAD_URL : undefined);
  if (hostedUrl) {
    await recordDownloadIfSignedIn();
    return NextResponse.redirect(hostedUrl, 302);
  }

  const file = resolveLocalInstaller();
  if (!file) {
    return NextResponse.json(
      {
        error: "installer_unavailable",
        message:
          "No installer is configured yet. Set NEXT_PUBLIC_DOWNLOAD_URL or ATLAS_INSTALLER_URL to the current GitHub Release asset, or set ATLAS_INSTALLER_PATH for local development.",
      },
      { status: 404 }
    );
  }

  await recordDownloadIfSignedIn();
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
