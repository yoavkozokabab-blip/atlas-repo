# GitHub Release — Click-by-Click (for Yoav)

Publish the Atlas installer as a GitHub Release so the website can link to a stable, versioned,
CDN-backed download URL. **Do this only after rebuilding the installer** (see
`reports/installer_rebuild_report.md` — the 06-15 build predates this session's fixes).

> ⚠️ Don't publish until you've decided the repo is OK to expose. If the repo is private, the
> release asset URL still works for anyone with the link, but the repo stays private.

---

## Option A — Web UI (no CLI)

1. Push the branch to GitHub.
2. Repo → **Releases** (right sidebar) → **Draft a new release**.
3. **Choose a tag** → type `v0.1.0-beta` → **Create new tag on publish**.
4. **Release title:** `Atlas 0.1.0-beta`.
5. **Describe this release** (notes):
   ```
   Atlas 0.1.0-beta — private beta (Windows).
   Local-first repository intelligence + persistent memory for AI coding agents.

   - Desktop app: scan, codebase map, context packs, what-breaks, change plans.
   - MCP server (experimental): Atlas.exe --mcp for Claude Desktop / Cursor / Codex.
   - Unsigned build: Windows SmartScreen may warn — More info → Run anyway.

   SHA256 in Atlas_Setup.exe.sha256.
   ```
6. **Attach binaries** — drag in both files:
   - `packaging\installer\output\Atlas_Setup.exe`
   - `packaging\installer\output\Atlas_Setup.exe.sha256`
7. Check **Set as a pre-release** (it's a beta). Click **Publish release**.
8. **Copy the asset URL:** on the published release, right-click **Atlas_Setup.exe** →
   **Copy link**. It looks like:
   ```
   https://github.com/<owner>/<repo>/releases/download/v0.1.0-beta/Atlas_Setup.exe
   ```

## Option B — `gh` CLI (faster)

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
gh release create v0.1.0-beta `
  "packaging\installer\output\Atlas_Setup.exe" `
  "packaging\installer\output\Atlas_Setup.exe.sha256" `
  --title "Atlas 0.1.0-beta" --prerelease `
  --notes "Atlas 0.1.0-beta private beta (Windows). Unsigned build; SHA256 in the .sha256 asset."
# Print the asset URL:
gh release view v0.1.0-beta --json assets --jq '.assets[].url'
```

## Then: point the website at it

In **Vercel → Settings → Environment Variables** set:
```
ATLAS_INSTALLER_URL = https://github.com/<owner>/<repo>/releases/download/v0.1.0-beta/Atlas_Setup.exe
```
**Redeploy.** Verify: signed-in, click Download → it should 302-redirect to the GitHub asset,
and the downloaded file's SHA256 must match the `.sha256` you published.

## Future releases
Bump `PRODUCT_VERSION`, rebuild, new tag `v0.1.1-beta`, upload, update `ATLAS_INSTALLER_URL`.
Full flow: `docs/RELEASE_PROCESS.md`.
