# Atlas — Release Process

Goal: publish a new Atlas build (installer + website pointer) in **under 10 minutes**.

There are two installer setups in the repo. **Use the canonical one:**

| Path | Status |
|---|---|
| `packaging/installer/` (`Atlas.iss` + `installer_build.ps1`) | ✅ **canonical** — refreshes staging, auto-generates version, this is what the website serves |
| `installer/` (`jarvis.iss`) | ⚠️ legacy (Phase 150) — do not use; bundles a stale top-level `staging/` |

The website download route resolves `packaging/installer/output/Atlas_Setup.exe` first, so that
is the artifact that ships.

---

## Prerequisites (one-time)

- Python 3.10+ (`py -3`).
- PyInstaller deps: `py -3 -m pip install --target .phase152_packaging_lib pyinstaller PyYAML`
- **Inno Setup 6** (`ISCC.exe`) on PATH or at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.
- `gh` CLI authenticated (`gh auth login`) for GitHub Release upload.

## Step 1 — Bump the version (30s)

Single source of truth: `jarvis_desktop/product_info.py` → `PRODUCT_VERSION`.
Everything else (installer version, build_info, `generated_version.iss`, website
`NEXT_PUBLIC_ATLAS_VERSION`) derives from it. Edit it, e.g. `0.1.1-beta`.

## Step 2 — Build the installer (5–7 min)

```powershell
.\packaging\installer\installer_build.ps1
```

This single script: regenerates `generated_version.iss` from `product_info.py`, runs the
PyInstaller build (`build_atlas_exe.ps1 -Clean` → `dist\Atlas` incl. the bundled accounts
service and the frozen MCP server), **refreshes `packaging\installer\staging\` from
`dist\Atlas`**, and compiles `Atlas.iss` → `packaging\installer\output\Atlas_Setup.exe`.

Flags: `-SkipPackage` (reuse existing `dist\Atlas`), `-SkipCompile` (stage only).

## Step 3 — Checksum (10s)

```powershell
$exe = "packaging\installer\output\Atlas_Setup.exe"
(Get-FileHash $exe -Algorithm SHA256).Hash.ToLower() + "  Atlas_Setup.exe" |
  Out-File "$exe.sha256" -Encoding ascii
Get-Content "$exe.sha256"
```

## Step 4 — Smoke check the build (30s)

```powershell
py -3 run_atlas.py --self-test          # launcher/dirs/shortcuts READY
py scripts\mcp_smoke_test.py            # MCP 12/12 green
```

(Full clean-machine install verification: see `reports/atlas_install_verification.md`.)

## Step 5 — Publish to GitHub Releases (1–2 min)

```powershell
$v = "v0.1.1-beta"
gh release create $v `
  "packaging\installer\output\Atlas_Setup.exe" `
  "packaging\installer\output\Atlas_Setup.exe.sha256" `
  --title "Atlas $v" --notes "See CHANGELOG."
# Stable asset URL:
#   https://github.com/<owner>/<repo>/releases/download/v0.1.1-beta/Atlas_Setup.exe
```

GitHub Releases gives a stable, versioned, CDN-backed URL and free download analytics
(release asset download counts). Alternatives: Supabase Storage or any CDN — same idea.

## Step 6 — Point the website at the new asset (1 min)

In **Vercel → Settings → Environment Variables** set (and redeploy):

```
ATLAS_INSTALLER_URL = https://github.com/<owner>/<repo>/releases/download/v0.1.1-beta/Atlas_Setup.exe
NEXT_PUBLIC_ATLAS_VERSION = 0.1.1-beta
```

The `/download/atlas` route 302-redirects to `ATLAS_INSTALLER_URL` (it never streams the
binary through the function). No code change, no localhost/local-file assumption.

## Step 7 — Verify production (30s)

```bash
curl -sI https://<domain>/download/atlas      # 302 -> the GitHub asset (when signed in)
curl -s  https://<domain>/api/health          # backend:"supabase", persistence:"ok"
```

Confirm the version on `/download` matches, and the checksum on the release matches Step 3.

---

## Checklist (copy per release)

- [ ] Bump `PRODUCT_VERSION` in `product_info.py`
- [ ] `installer_build.ps1` → `Atlas_Setup.exe`
- [ ] Generate `.sha256`
- [ ] `--self-test` + `mcp_smoke_test.py` green
- [ ] `gh release create` (exe + sha256)
- [ ] Set `ATLAS_INSTALLER_URL` + `NEXT_PUBLIC_ATLAS_VERSION` in Vercel, redeploy
- [ ] `/download/atlas` 302s to the asset; `/api/health` ok; checksum matches
