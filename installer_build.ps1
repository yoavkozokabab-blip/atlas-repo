# JARVIS Desktop — Windows installer build script (Phase 112)
# Usage: .\installer_build.ps1 [-SkipCompile]

param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Staging = Join-Path $Root "staging"
$InstallerDir = Join-Path $Root "installer"
$OutputDir = Join-Path $InstallerDir "output"
$AssetsDir = Join-Path $InstallerDir "assets"

Write-Host "JARVIS Desktop installer build" -ForegroundColor Cyan

if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Path $Staging, $OutputDir, $AssetsDir -Force | Out-Null

# Minimal icon placeholder (16x16 ICO) if not present
$IconPath = Join-Path $AssetsDir "jarvis.ico"
if (-not (Test-Path $IconPath)) {
    $iconScript = @'
import struct, pathlib
path = pathlib.Path(r"ICONPATH")
# Tiny valid ICO: 16x16 32bpp cyan/violet gradient block
w, h = 16, 16
pixels = bytearray()
for y in range(h):
    for x in range(w):
        t = x / max(w - 1, 1)
        r = int(62 + t * 92)
        g = int(240 - t * 40)
        b = int(255 - t * 80)
        pixels.extend([b, g, r, 255])
and_mask = bytes([0x00, 0x00] * w * h)
bmp = struct.pack("<IIIHHIIIIII", 40, w, h * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0) + bytes(pixels) + and_mask
icon_dir = struct.pack("<HHH", 0, 1, 1)
entry = struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32, len(bmp), 22)
path.write_bytes(icon_dir + entry + bmp)
print("Created icon:", path)
'@.Replace('ICONPATH', $IconPath.Replace('\', '\\'))
    $tmp = Join-Path $env:TEMP "jarvis_icon_gen.py"
    Set-Content -Path $tmp -Value $iconScript -Encoding UTF8
    py $tmp
}

# Stage application files
$CopyItems = @(
    "jarvis_desktop",
    "builder_core",
    "run_jarvis_desktop.py",
    "run_jarvis_desktop.bat"
)
foreach ($item in $CopyItems) {
    $src = Join-Path $Root $item
    if (-not (Test-Path $src)) { throw "Missing staging source: $src" }
    Copy-Item $src (Join-Path $Staging $item) -Recurse -Force
}

# Launcher
$Launcher = @'
@echo off
cd /d "%~dp0"
py -3 run_jarvis_desktop.py %*
'@
Set-Content -Path (Join-Path $Staging "JARVIS Desktop.bat") -Value $Launcher -Encoding ASCII

New-Item -ItemType Directory -Path (Join-Path $Staging "assets") -Force | Out-Null
Copy-Item $IconPath (Join-Path $Staging "assets\jarvis.ico") -Force

# Generate demo packs if needed
$gen = Join-Path $Staging "jarvis_desktop\demo\generate_demo_packs.py"
if (Test-Path $gen) { py $gen }

Write-Host "Staging complete: $Staging" -ForegroundColor Green

if ($SkipCompile) {
    Write-Host "SkipCompile set - staging only." -ForegroundColor Yellow
    exit 0
}

$Iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "Inno Setup (ISCC.exe) not found. Staging is ready; install Inno Setup 6 and re-run." -ForegroundColor Yellow
    Write-Host "Manual: ISCC.exe installer\jarvis.iss"
    exit 2
}

& $Iscc (Join-Path $InstallerDir "jarvis.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

$exe = Join-Path $OutputDir "JARVIS_Setup.exe"
if (Test-Path $exe) {
    Write-Host "Built: $exe" -ForegroundColor Green
} else {
    throw "Expected output not found: $exe"
}
