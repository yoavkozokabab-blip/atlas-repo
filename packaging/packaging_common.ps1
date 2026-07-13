# Shared path resolution and build guards for Atlas packaging scripts.

function Get-PackagingScriptDir {
    if ($PSScriptRoot) { return $PSScriptRoot }
    if ($PSCommandPath) { return (Split-Path -Parent $PSCommandPath) }
    throw @"
Cannot resolve packaging script directory (`$PSScriptRoot is null).
Run the script directly, for example:
  .\packaging\pyinstaller\build_atlas_exe.ps1
  .\packaging\installer\installer_build.ps1
"@
}

function Get-RepoRootFrom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptDir,
        [int]$LevelsUp = 2
    )
    if (-not $ScriptDir) {
        throw "Get-RepoRootFrom: ScriptDir is null."
    }
    $dir = $ScriptDir
    for ($i = 0; $i -lt $LevelsUp; $i++) {
        $parent = Split-Path -Parent $dir
        if (-not $parent) {
            throw "Cannot walk up $LevelsUp level(s) from script dir '$ScriptDir' (stopped at '$dir')."
        }
        $dir = $parent
    }
    $resolved = Resolve-Path -LiteralPath $dir -ErrorAction Stop
    return $resolved.Path
}

function Join-PathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Base,
        [Parameter(Mandatory = $true)]
        [string]$Child
    )
    if ([string]::IsNullOrWhiteSpace($Base)) {
        throw "Join-PathSafe: base path is null or empty (child: $Child)."
    }
    return (Join-Path $Base $Child)
}

function Assert-AtlasRc1BuildRoot {
    param([Parameter(Mandatory = $true)][string]$Root)
    $leaf = Split-Path -Leaf $Root
    if ($leaf -ne "atlas-rc1-clean") {
        throw @"
Installer must be built from C:\J.A.R.V.I.S\atlas-rc1-clean only.
Current repo root: $Root
Do not build from local_jarvis or any other tree.
"@
    }
    $index = Join-Path $Root "atlas_desktop\static\index.html"
    if (-not (Test-Path -LiteralPath $index)) {
        throw "Missing atlas_desktop static UI at $index"
    }
}

function Find-StagedIndexHtml {
    param([Parameter(Mandatory = $true)][string]$StagingRoot)
    $direct = Join-Path $StagingRoot "_internal\atlas_desktop\static\index.html"
    if (Test-Path -LiteralPath $direct) { return $direct }
    $found = Get-ChildItem -Path $StagingRoot -Recurse -Filter "index.html" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "atlas_desktop\\static\\index\.html$" } |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Test-HnLaunchUxPayload {
    param([Parameter(Mandatory = $true)][string]$IndexPath)
    $html = Get-Content -LiteralPath $IndexPath -Raw -ErrorAction Stop
    $issues = @()
    if ($html -notmatch 'data-view="ask"[^>]*>Ask</button>') { $issues += "nav missing Ask" }
    if ($html -notmatch 'data-view="center"[^>]*>Graph</button>') { $issues += "nav missing Graph" }
    foreach ($view in @("memory", "files", "agents", "diagnostics", "settings")) {
        if ($html -notmatch ('id="view-' + $view + '"')) { $issues += "workspace missing $view" }
    }
    if ($html -match ">Repository Context<") { $issues += "nav still has Repository Context (old UI)" }
    if ($html -notmatch "Load sample repository") { $issues += "home missing Load sample repository" }
    if ($html -notmatch "Atlas v1\.0\.0 launch build") { $issues += "missing launch build marker" }
    return $issues
}

function Find-InnoSetupCompiler {
    param([string]$Root)
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($Root) {
        $candidates.Add((Join-Path $Root ".phase152_inno\ISCC.exe"))
        $candidates.Add((Join-Path $Root ".phase150_inno\ISCC.exe"))
    }
    $pf86 = ${env:ProgramFiles(x86)}
    if ($pf86) { $candidates.Add((Join-Path $pf86 "Inno Setup 6\ISCC.exe")) }
    if ($env:ProgramFiles) { $candidates.Add((Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")) }
    $candidates.Add("ISCC.exe")
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path -ErrorAction SilentlyContinue)) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }
    return $null
}
