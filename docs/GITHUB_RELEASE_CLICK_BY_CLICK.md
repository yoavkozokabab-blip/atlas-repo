# GitHub Release — Click-by-Click (for Yoav)

Publish the Atlas installer as a GitHub Release so the website can link to a stable, versioned,
CDN-backed download URL. Do this only after the clean-source installed-app release gate passes
and the downloaded production executable matches the verified installer SHA256.

> ⚠️ Don't publish until you've decided the repo is OK to expose. If the repo is private, the
> release asset URL still works for anyone with the link, but the repo stays private.

---

## Option A — Web UI (no CLI)

1. Push the branch to GitHub.
2. Repo → **Releases** (right sidebar) → **Draft a new release**.
3. **Choose a tag** → use the semantic version for the verified build. The tag must point to
   the exact source commit embedded in the installer.
4. **Release title:** `Atlas 1.0.0`.
5. **Describe this release** (notes):
   ```
   Atlas 1.0.0 — Windows.
   Local-first repository intelligence + persistent memory for AI coding agents.

   - Desktop app: scan, codebase map, context packs, what-breaks, change plans.
   - MCP server (experimental): Atlas.exe --mcp for Claude Desktop / Cursor / Codex.
   - Unsigned build: Windows SmartScreen may warn — More info → Run anyway.

   SHA256 and build commit in the release notes and `Atlas_Setup.exe.sha256`.
   ```
6. **Attach binaries** — drag in both files:
   - `packaging\installer\output\Atlas_Setup.exe`
   - `packaging\installer\output\Atlas_Setup.exe.sha256`
7. Click **Publish release**.
8. **Copy the asset URL:** on the published release, right-click **Atlas_Setup.exe** →
   **Copy link**. It looks like:
   ```
   https://github.com/<owner>/<repo>/releases/download/v1.0.0/Atlas_Setup.exe
   ```

## Option B — `gh` CLI (faster)

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
gh release create v1.0.0 `
  "packaging\installer\output\Atlas_Setup.exe" `
  "packaging\installer\output\Atlas_Setup.exe.sha256" `
  --title "Atlas 1.0.0" `
  --target <exact-verified-source-commit> `
  --notes "Atlas 1.0.0 (Windows). Unsigned build; SHA256 and build commit in the release notes."
# Print the asset URL:
gh release view v1.0.0 --json assets --jq '.assets[].url'
```

## Then: point the website at it

In **Vercel → Settings → Environment Variables** set:
```
ATLAS_INSTALLER_URL = https://github.com/<owner>/<repo>/releases/download/v1.0.0/Atlas_Setup.exe
```
**Redeploy.** Verify: anonymous and signed-in download paths 302-redirect to the GitHub asset,
and the downloaded file's SHA256 must match the `.sha256` you published.

## Future releases
Bump `PRODUCT_VERSION`, rebuild, new tag `v1.0.1`, upload, update `ATLAS_INSTALLER_URL`.
Full flow: `docs/RELEASE_PROCESS.md`.
