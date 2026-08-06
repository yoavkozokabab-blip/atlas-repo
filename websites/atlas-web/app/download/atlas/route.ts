import { NextResponse } from "next/server";
import crypto from "node:crypto";
import { createReadStream, existsSync, statSync } from "node:fs";
import { Readable } from "node:stream";
import path from "node:path";
import { currentUser } from "@/app/_lib/auth";
import { CURRENT_WINDOWS_RELEASE } from "@/app/_config";
import { store, newId, recordAnalyticsEvent } from "@/app/_lib/store";
import { buildAnalyticsRow } from "@/app/_lib/analytics-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function resolveLocalInstaller(): string | null {
  const env = process.env.ATLAS_INSTALLER_PATH;
  if (env && existsSync(env)) return env;
  // Local development only, never a user-facing name: the installer build
  // emits the versioned filename, and the historical un-versioned name is
  // still probed so an older local build keeps working. dev-fallback-legacy-name
  const names = [CURRENT_WINDOWS_RELEASE.filename, "Atlas_Setup.exe"];
  const candidates = names.flatMap((name) => [
    path.join(process.cwd(), "..", "..", "packaging", "installer", "output", name),
    path.join(process.cwd(), "..", "..", "installer", "output", name),
  ]);
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

async function recordInstallerResponseStarted(req: Request): Promise<void> {
  try {
    await recordAnalyticsEvent(buildAnalyticsRow({
      eventName: "installer_download_started",
      source: "server",
      route: "/download/atlas",
      deduplicationKey: crypto.randomUUID(),
      request: req,
    }));
  } catch {
    // Download behavior must not depend on analytics availability.
  }
}

export async function GET(req: Request) {
  // The redirect target and the version/checksum the download page renders
  // come from the same object, so they cannot describe different files.
  const { downloadUrl } = CURRENT_WINDOWS_RELEASE;
  const hostedUrl = downloadUrl && downloadUrl !== "/download/atlas" ? downloadUrl : undefined;
  if (hostedUrl) {
    await Promise.all([recordDownloadIfSignedIn(), recordInstallerResponseStarted(req)]);
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

  await Promise.all([recordDownloadIfSignedIn(), recordInstallerResponseStarted(req)]);
  const size = statSync(file).size;
  const webStream = Readable.toWeb(createReadStream(file)) as ReadableStream;
  return new NextResponse(webStream, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${CURRENT_WINDOWS_RELEASE.filename}"`,
      "Content-Length": String(size),
      "Cache-Control": "no-store",
    },
  });
}
