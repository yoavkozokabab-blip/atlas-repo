# GitHub Release — Asset Manifest (Ops Phase / Step 6)

**Date:** 2026-06-16

## ⚠️ Status: the artifact below is STALE — rebuild before releasing

The current installer predates this session's fixes (`--mcp`, serverInfo version, uninstall
cleanup). **Do not publish it.** Rebuild per `reports/installer_rebuild_report.md`, then
update this manifest with the new size/hash/timestamp before creating the release.

## Current (pre-rebuild) artifact

| Field | Value |
|---|---|
| Filename | `Atlas_Setup.exe` |
| Local path | `packaging/installer/output/Atlas_Setup.exe` (canonical) |
| Copy | `installer/output/Atlas_Setup.exe` (byte-identical) |
| Size | 44,026,121 bytes (~42.0 MB) |
| SHA256 | `b98ca5e5edbdd2aa6a64930211ce867dcb442e0cf1f5a994dabd756491d6cbc6` |
| Build timestamp | 2026-06-15 20:47:16 +0300 |
| Built from commit | `2846b2d57` (⚠️ before HEAD `f5b6ce922`) |
| Version | 0.1.0-beta |
| Checksum file | `packaging/installer/output/Atlas_Setup.exe.sha256` + `installer/output/Atlas_Setup.exe.sha256` |

## Assets to upload (after rebuild)

| File | Purpose |
|---|---|
| `Atlas_Setup.exe` | the installer |
| `Atlas_Setup.exe.sha256` | integrity check users/CI can verify |

## Manifest template to fill after rebuild

```
Filename:        Atlas_Setup.exe
Size:            <bytes> (~<MB> MB)
SHA256:          <new hash from Get-FileHash>
Build timestamp: <date>
Built from:      <git short HEAD — must be current, not 2846b2d57>
Version:         0.1.0-beta
Release tag:     v0.1.0-beta
Asset URL:       https://github.com/<owner>/<repo>/releases/download/v0.1.0-beta/Atlas_Setup.exe
```

Set `ATLAS_INSTALLER_URL` in Vercel to the Asset URL and redeploy.
