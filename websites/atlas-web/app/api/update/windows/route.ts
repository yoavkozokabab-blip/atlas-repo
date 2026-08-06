import { CURRENT_WINDOWS_RELEASE, GITHUB_RELEASE_URL } from "@/app/_config";

export const runtime = "nodejs";

/**
 * Minimal update manifest for the Windows desktop build.
 *
 * Deliberately a plain, unauthenticated GET with no request body: the desktop
 * sends no installation id, machine identifier, repository information or
 * current version, so this endpoint cannot be used to profile installs. The
 * client compares the returned version against its own and, if newer, offers
 * to open `downloadUrl` in the browser. Atlas never downloads or executes an
 * update itself.
 *
 * Served from CURRENT_WINDOWS_RELEASE so the manifest, the download page and
 * the redirect can never describe different artifacts.
 */
export async function GET() {
  const release = CURRENT_WINDOWS_RELEASE;
  return Response.json(
    {
      latestVersion: release.version,
      // `version` is an alias: product_info.check_for_update() accepts either.
      version: release.version,
      filename: release.filename,
      downloadUrl: release.downloadUrl,
      sha256: release.sha256,
      sizeBytes: release.sizeBytes,
      platform: release.platform,
      signed: release.signed,
      mandatory: false,
      release_notes_url: GITHUB_RELEASE_URL,
    },
    {
      status: 200,
      headers: {
        // Short cache: an update must become visible quickly, but a burst of
        // clients starting at once must not hit the origin every time.
        "Cache-Control": "public, max-age=300, s-maxage=300",
      },
    },
  );
}
