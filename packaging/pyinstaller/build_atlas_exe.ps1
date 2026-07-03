# Atlas Desktop — PyInstaller one-folder build (Phase 152)
# Usage:
#   .\packaging\pyinstaller\build_atlas_exe.ps1
#   .\packaging\pyinstaller\build_atlas_exe.ps1 -Clean
#
# First-time deps (workspace-local, no global pip required for Atlas runtime):
#   py -3 -m pip install --target .phase152_packaging_lib pyinstaller PyYAML

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$Root = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Spec = Join-Path $ScriptDir "atlas.spec"
$PackagingLib = Join-Path $Root ".phase152_packaging_lib"
$DistDir = Join-Path $Root "dist"
$WorkDir = Join-Path $Root "build\pyinstaller"
$AtlasExe = Join-Path $DistDir "Atlas\Atlas.exe"
$InstallerDir = Join-Path $Root "packaging\installer"

function Write-BuildInfo {
    $version = "1.0.0"
    $productFile = Join-Path $Root "atlas_desktop\product_info.py"
    if (Test-Path $productFile) {
        $m = Select-String -Path $productFile -Pattern 'PRODUCT_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($m) { $version = $m.Matches[0].Groups[1].Value }
    }
    $commit = ""
    try {
        Push-Location $Root
        $commit = (git rev-parse --short HEAD 2>$null)
    } catch { }
    finally { Pop-Location }
    $info = @{
        product = "ATLAS"
        version = $version
        build_date = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
        commit = $commit
        entry = "Atlas.exe"
    }
    $out = Join-Path $InstallerDir "build_info.json"
    New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
    $json = $info | ConvertTo-Json
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($out, $json, $utf8)
    Write-Host "Build info: $out" -ForegroundColor DarkGray
}

function Ensure-Icon {
    $assets = Join-Path $InstallerDir "assets"
    $icon = Join-Path $assets "atlas.ico"
    New-Item -ItemType Directory -Path $assets -Force | Out-Null
    if (Test-Path $icon) { return }
    $iconScript = @'
import struct, pathlib
path = pathlib.Path(r"ICONPATH")
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
'@.Replace('ICONPATH', $icon.Replace('\', '\\'))
    $tmp = Join-Path $env:TEMP "atlas_icon_gen.py"
    Set-Content -Path $tmp -Value $iconScript -Encoding UTF8
    py -3 $tmp
}

Write-Host "Atlas PyInstaller build (Phase 152)" -ForegroundColor Cyan
Write-BuildInfo
Ensure-Icon

if (-not (Test-Path $Spec)) {
    throw "Missing spec: $Spec"
}
if (-not (Test-Path (Join-Path $PackagingLib "PyInstaller"))) {
    throw "Install build deps: py -3 -m pip install --target .phase152_packaging_lib pyinstaller PyYAML"
}

if ($Clean) {
    foreach ($path in @((Join-Path $DistDir "Atlas"), $WorkDir)) {
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
}

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = if ($oldPythonPath) { "$PackagingLib;$oldPythonPath" } else { $PackagingLib }
    Push-Location $Root
    & py -3 -m PyInstaller.__main__ --noconfirm --clean --distpath $DistDir --workpath $WorkDir $Spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
} finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}

if (-not (Test-Path $AtlasExe)) {
    throw "Expected executable not built: $AtlasExe"
}
$item = Get-Item -LiteralPath $AtlasExe
$exeMb = [Math]::Round($item.Length / 1048576, 2)
Write-Host ("Built: {0} ({1} MB)" -f $AtlasExe, $exeMb) -ForegroundColor Green

# Phase 192 — build the frozen Atlas Accounts Service (AtlasAccounts.exe) and
# bundle it inside the Atlas folder under accounts\ so Atlas.exe can launch it.
$AccountsSpec = Join-Path $ScriptDir "accounts.spec"
$AccountsLib = Join-Path $Root "accounts_service\.lib"
$AccountsDist = Join-Path $DistDir "AtlasAccounts"
$AccountsWork = Join-Path $Root "build\pyinstaller_accounts"
if (Test-Path $AccountsSpec) {
    $oldPP = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = ($PackagingLib, $AccountsLib, $Root, $oldPP | Where-Object { $_ }) -join ';'
        Push-Location $Root
        & py -3 -m PyInstaller.__main__ --noconfirm --clean --distpath $DistDir --workpath $AccountsWork $AccountsSpec
        if ($LASTEXITCODE -ne 0) { throw "Accounts PyInstaller failed with exit code $LASTEXITCODE" }
    } finally {
        $env:PYTHONPATH = $oldPP
        Pop-Location
    }
    $AccountsExe = Join-Path $AccountsDist "AtlasAccounts.exe"
    if (-not (Test-Path $AccountsExe)) { throw "Expected accounts executable not built: $AccountsExe" }
    # Copy the accounts one-folder bundle into dist\Atlas\accounts\ (shipped together).
    $AccountsTarget = Join-Path $DistAtlas "accounts"
    if (Test-Path $AccountsTarget) { Remove-Item -LiteralPath $AccountsTarget -Recurse -Force }
    New-Item -ItemType Directory -Path $AccountsTarget -Force | Out-Null
    Copy-Item -Path (Join-Path $AccountsDist "*") -Destination $AccountsTarget -Recurse -Force
    $accMb = [Math]::Round((Get-Item (Join-Path $AccountsTarget "AtlasAccounts.exe")).Length / 1048576, 2)
    Write-Host ("Bundled accounts service: {0}\AtlasAccounts.exe ({1} MB)" -f $AccountsTarget, $accMb) -ForegroundColor Green
}
